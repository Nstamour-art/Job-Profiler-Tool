"""
Google Sheet logging tool for the job search agent.

Provides a LangChain tool that appends found jobs to the configured sheet.
Fails gracefully if the sheet is not configured.
"""

from __future__ import annotations

from datetime import date

from langchain_core.tools import tool

from src.sheets import append_job_row


def create_sheet_log_tool(config: dict):
    """Return a log_job_to_sheet LangChain tool bound to config."""

    @tool
    def log_job_to_sheet(title: str, company: str, url: str, status: str = "Seen") -> str:
        """Log a found job to the Google Sheet.

        Args:
            title: Job title.
            company: Company name.
            url: Job posting URL.
            status: Row status — 'Seen' when found, 'Generated' after documents are made.

        Returns:
            Confirmation string or error message.
        """
        try:
            from src.models import JobRow  # pylint: disable=import-outside-toplevel
            job_row = JobRow(
                title=title,
                company=company,
                url=url,
                status=status,
                date_found=date.today().isoformat(),
            )
            append_job_row(config=config, job_row=job_row)
            return f"Logged '{title}' at {company} to sheet (Status: {status})."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Sheet logging failed: {exc}"

    return log_job_to_sheet
