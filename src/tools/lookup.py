"""Job detail lookup tool — fetch and summarise a specific job posting on demand."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import tool as lc_tool

from src.validator import _fetch_snippet
from src.llm import _call_with_retry
from src.prompts import JOB_SUMMARY_SYSTEM_PROMPT

if TYPE_CHECKING:
    from src.providers import BaseProvider


def create_lookup_tool(
    config: dict,
    provider: "BaseProvider",
    parser_models: list[str],
):
    """Return a lookup_job_details LangChain tool bound to the given provider."""

    @lc_tool
    def lookup_job_details(url: str, title: str, company: str) -> str:
        """Fetch and summarise a specific job posting in plain English.

        Call this when the user asks for more detail about a job — e.g. "what does
        this role involve?" or "tell me more about job 3" — before deciding whether
        to generate documents.

        Args:
            url: The direct URL of the job posting.
            title: Job title as returned by search_jobs.
            company: Company name as returned by search_jobs.

        Returns:
            A 3-5 sentence plain-English summary, or an error string on failure.
        """
        if not url:
            return "No URL provided."

        snippet = _fetch_snippet(url)
        if snippet is None:
            return (
                f"Could not fetch details for {url} — "
                "the page may require authentication or a JavaScript-heavy render."
            )

        prompt = (
            f"Role: {title} at {company}\n\n"
            f"--- BEGIN UNTRUSTED CONTENT ---\n{snippet}\n--- END UNTRUSTED CONTENT ---"
        )

        try:
            from src.models import JobSummary  # pylint: disable=import-outside-toplevel
            result = _call_with_retry(
                JobSummary,
                provider,
                config["llm"],
                JOB_SUMMARY_SYSTEM_PROMPT,
                prompt,
                parser_models,
            )
            return result.summary
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Could not summarize job details: {exc}"

    return lookup_job_details
