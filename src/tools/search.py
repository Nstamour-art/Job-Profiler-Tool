"""
Tavily-powered job search tool for the job search agent.

Creates a search sub-agent (via Deep Agents) with only the Tavily tool.
The sub-agent makes multiple targeted searches, deduplicates results, and
returns a compact JSON job list. After results arrive, URLs are validated
and surviving jobs are logged to Sheets as "Seen" before being returned.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import json_repair
from langchain_core.tools import tool as lc_tool
from deepagents import create_deep_agent

from src.prompts import SEARCH_SUBAGENT_SYSTEM_PROMPT
from src.validator import validate_job_links
from src.sheets import bulk_upsert_job_rows

if TYPE_CHECKING:
    from src.providers import BaseProvider


def create_search_tool(
    agent_model,
    tavily_api_key: str,
    max_jobs: int = 10,
    parser_model=None,
    config: dict | None = None,
    provider: "BaseProvider | None" = None,
    parser_models: list[str] | None = None,
):
    """Return a search_jobs LangChain tool that uses a Tavily search sub-agent.

    Fetches max_jobs + search_buffer results, validates each URL, logs valid
    jobs to Sheets as Seen, then returns up to max_jobs valid results.
    """
    from langchain_tavily import TavilySearch  # pylint: disable=import-outside-toplevel

    cfg = config or {}
    search_buffer = cfg.get("agent", {}).get("search_buffer", 5)
    fetch_count = max_jobs + search_buffer

    tavily = TavilySearch(max_results=30, tavily_api_key=tavily_api_key)
    system_prompt = SEARCH_SUBAGENT_SYSTEM_PROMPT.replace("{max_jobs}", str(fetch_count))
    search_model = parser_model if parser_model is not None else agent_model

    @lc_tool
    def search_jobs(preferences_summary: str) -> str:
        """Search the web for job listings matching the candidate's preferences.

        Args:
            preferences_summary: A summary of the candidate's target roles, location,
                salary range, and key skills.

        Returns:
            A JSON string with a 'jobs' list. Each job has: title, company, url,
            location, salary.
        """
        try:
            sub_agent = create_deep_agent(
                model=search_model,
                tools=[tavily],
                system_prompt=system_prompt,
            )
            result = sub_agent.invoke({
                "messages": [{"role": "user", "content": preferences_summary}]
            })
            raw = result["messages"][-1].content

            # Parse JSON from sub-agent (repair if malformed)
            parsed = json_repair.repair_json(raw, return_objects=True)
            if not isinstance(parsed, dict):
                return raw  # couldn't parse — return raw for agent to handle
            jobs = parsed.get("jobs", [])
            total_fetched = len(jobs)

            # Validate links (requires provider + parser_models)
            if provider is not None and parser_models:
                jobs = validate_job_links(jobs, cfg, provider, parser_models, max_jobs)
            else:
                jobs = jobs[:max_jobs]

            # Log validated jobs as Seen (silently skip if Sheets not configured)
            sheets_cfg = cfg.get("google_sheets")
            if sheets_cfg and jobs:
                from src.models import JobRow  # pylint: disable=import-outside-toplevel
                job_rows = [
                    JobRow(
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        url=job.get("url", ""),
                        status="Seen",
                        date_found=date.today().isoformat(),
                    )
                    for job in jobs
                ]
                try:
                    bulk_upsert_job_rows(config=cfg, job_rows=job_rows)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass  # sheet failure must never abort search

            return json.dumps({
                "jobs": jobs,
                "validated_count": len(jobs),
                "fetched_count": total_fetched,
            })
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Search failed: {exc}"

    return search_jobs
