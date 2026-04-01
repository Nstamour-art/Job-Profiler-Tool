"""
Tavily-powered job search tool for the job search agent.

Creates a search sub-agent (via Deep Agents) with only the Tavily tool.
The sub-agent makes multiple targeted searches, deduplicates results, and
returns a compact JSON job list. Its context is discarded after each call.
"""

from __future__ import annotations

from langchain_core.tools import tool as lc_tool
from deepagents import create_deep_agent

from src.prompts import SEARCH_SUBAGENT_SYSTEM_PROMPT


def create_search_tool(agent_model, tavily_api_key: str, max_jobs: int = 10, parser_model=None):
    """Return a search_jobs LangChain tool that uses a Tavily search sub-agent.

    The search sub-agent uses parser_model (a lightweight model) when provided,
    falling back to agent_model. Heavy reasoning is not needed for search.
    """
    from langchain_tavily import TavilySearch  # pylint: disable=import-outside-toplevel

    tavily = TavilySearch(max_results=30, tavily_api_key=tavily_api_key)
    system_prompt = SEARCH_SUBAGENT_SYSTEM_PROMPT.replace("{max_jobs}", str(max_jobs))
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
            return result["messages"][-1].content
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Search failed: {exc}"

    return search_jobs
