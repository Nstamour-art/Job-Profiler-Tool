"""Job detail lookup tool — fetch and summarise a specific job posting on demand."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import TYPE_CHECKING

from langchain_core.tools import tool as lc_tool

from src.validator import _fetch_snippet
from src.llm import _call_with_retry
from src.prompts import JOB_SUMMARY_SYSTEM_PROMPT

if TYPE_CHECKING:
    from src.providers import BaseProvider

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_url(url: str) -> str | None:
    """Return a cleaned URL, or an error message string if the URL is unsafe.

    Checks:
    - Non-empty after stripping whitespace
    - Scheme must be http or https
    - Resolved IP must not be loopback, private, or link-local (SSRF guard)

    Returns ``None`` when the URL is safe to fetch, or a human-readable error
    string that the tool can return directly to the caller.
    """
    if not url:
        return "No URL provided."

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return f"Invalid URL scheme '{parsed.scheme}': only http and https are allowed."

    hostname = parsed.hostname
    if not hostname:
        return "Invalid URL: no hostname found."

    try:
        addr = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError):
        return f"Could not resolve hostname '{hostname}'."

    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return f"Access to '{hostname}' is not allowed."

    return None


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
        url = url.strip()
        url_error = _validate_url(url)
        if url_error is not None:
            return url_error

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
