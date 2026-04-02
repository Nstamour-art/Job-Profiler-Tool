"""
Document generation tool for the job search agent.

Wraps the existing process_job pipeline. The tool boundary provides context
isolation — the main agent only sees the short return string, never the full
resume YAML or job description.
"""

from __future__ import annotations

from langchain_core.tools import tool as lc_tool

from src.models import Outcome
from src.pipeline import process_job
from src.providers import BaseProvider


def create_generate_tool(
    config: dict,
    resume: dict,
    provider: BaseProvider,
    models: list[str],
    parser_models: list[str],
):
    """Return a generate_documents LangChain tool bound to the current session's pipeline."""

    @lc_tool
    def generate_documents(url: str, job_title: str, company: str) -> str:
        """Generate a tailored resume and cover letter for a specific job posting.

        Args:
            url: The job posting URL.
            job_title: Job title (used for file naming and context).
            company: Company name (used for file naming and context).

        Returns:
            A short summary of what was generated, including priority score.
        """
        job = {
            "url": url,
            "job_title": job_title,
            "company": company,
            "status": "",
            "details": "",
            "row": None,
        }
        try:
            from src.models import JobOptions, ProviderSuite  # pylint: disable=import-outside-toplevel
            ps = ProviderSuite(provider=provider, models=models, parser_models=parser_models, name="")
            folder, _, resume_json, sheet_outcome = process_job(
                job, config, resume, provider_suite=ps, options=JobOptions()
            )
            priority_msg = ""
            if resume_json is not None:
                priority_msg = (
                    f" Priority: {resume_json.priority}/10 "
                    f"— {resume_json.priority_reasoning}"
                )
            warning_msg = f" ⚠️ {sheet_outcome.message}" if not sheet_outcome.success else ""
            return (
                f"Generated documents for {company} ({job_title}). "
                f"Saved to {folder}.{priority_msg}{warning_msg}"
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Failed to generate documents for {company} ({job_title}): {exc}"

    return generate_documents
