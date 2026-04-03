"""
Document generation tool for the job search agent.

Wraps the existing process_job pipeline. The tool boundary provides context
isolation — the main agent only sees the short return string, never the full
resume YAML or job description.
"""

from __future__ import annotations

import time

from langchain_core.tools import tool as lc_tool

from src.pipeline import process_job
from src.providers import BaseProvider


def create_generate_batch_tool(
    config: dict,
    resume: dict,
    provider: BaseProvider,
    models: list[str],
    parser_models: list[str],
):
    """Return a generate_batch LangChain tool that processes jobs in paced batches.

    Reads batch_size and batch_delay_seconds from config.agent. Defaults to 3
    and 15 respectively. Sleeps between batches (not after the last batch) to
    avoid API rate limiting.
    """
    batch_size = config.get("agent", {}).get("batch_size", 3)
    batch_delay = config.get("agent", {}).get("batch_delay_seconds", 15)

    @lc_tool
    def generate_batch(jobs: list[dict]) -> str:
        """Generate tailored resumes and cover letters for one or more job postings.

        Processes jobs in batches with a configurable pause between batches to
        avoid API rate limiting. Use this for ALL document generation — pass all
        selected jobs at once.

        Args:
            jobs: List of job dicts. Each must have 'url', 'title', and 'company'.

        Returns:
            A status line per job: ✓ on success, ✗ on failure.
        """
        if not jobs:
            return "No jobs provided to generate documents for."

        from src.models import JobOptions, ProviderSuite  # pylint: disable=import-outside-toplevel

        ps = ProviderSuite(
            provider=provider,
            models=models,
            parser_models=parser_models,
            name="",
        )
        lines = []
        batches = [jobs[i:i + batch_size] for i in range(0, len(jobs), batch_size)]

        for batch_idx, batch in enumerate(batches):
            for job_input in batch:
                url = job_input.get("url", "")
                title = job_input.get("title", job_input.get("job_title", "Unknown"))
                company = job_input.get("company", "Unknown")
                job = {
                    "url": url,
                    "job_title": title,
                    "company": company,
                    "status": "",
                    "details": "",
                    "row": None,
                }
                try:
                    folder, _, resume_json, sheet_outcome = process_job(
                        job, config, resume, provider_suite=ps, options=JobOptions()
                    )
                    priority_msg = ""
                    if resume_json is not None:
                        priority_msg = (
                            f" Priority: {resume_json.priority}/10"
                            f" — {resume_json.priority_reasoning}"
                        )
                    warning_msg = (
                        f" ⚠️ {sheet_outcome.message}" if not sheet_outcome.success else ""
                    )
                    lines.append(
                        f"✓ {company} ({title}) — saved to {folder}.{priority_msg}{warning_msg}"
                    )
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    lines.append(f"✗ {company} ({title}) — failed: {exc}")

            if batch_idx < len(batches) - 1:
                time.sleep(batch_delay)

        return "\n".join(lines)

    return generate_batch
