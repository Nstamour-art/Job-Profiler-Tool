"""
suggest_roles tool — derives job title suggestions from the candidate's resume
using the parser LLM.
"""
from __future__ import annotations

import yaml
from langchain_core.tools import tool as lc_tool

from src.llm import _call_with_retry
from src.models import SuggestedRoles
from src.prompts import SUGGEST_ROLES_PROMPT


def create_suggest_roles_tool(config: dict, provider, parser_models: list[str]):
    """Return a suggest_roles LangChain tool bound to this session's config."""

    @lc_tool
    def suggest_roles() -> str:
        """Suggest job titles the candidate is qualified for based on their resume.

        Returns a numbered list of role titles with one-line reasoning for each.
        Call this only when the candidate says they don't have a specific role in mind.
        """
        try:
            resume_path = config["paths"]["resume_yaml"]
            with open(resume_path, encoding="utf-8") as f:
                resume = yaml.safe_load(f)
            resume_str = yaml.dump(resume, allow_unicode=True)

            result = _call_with_retry(
                SuggestedRoles,
                provider,
                config["llm"],
                SUGGEST_ROLES_PROMPT,
                resume_str,
                parser_models,
            )
            lines = [
                f"{i + 1}. {role.title} — {role.reasoning}"
                for i, role in enumerate(result.roles)
            ]
            if not lines:
                return "No role suggestions could be inferred from the resume."
            header = f"Inferred seniority: {result.seniority_level}\n"
            return header + "\n".join(lines)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Failed to suggest roles: {exc}"

    return suggest_roles
