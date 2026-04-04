"""Tests for SuggestedRole/SuggestedRoles models and the suggest_roles tool."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

def test_suggested_roles_model_valid():
    from src.models import SuggestedRoles
    data = {
        "seniority_level": "Mid-level",
        "roles": [
            {"title": "UX Designer", "reasoning": "3 years Figma experience"},
            {"title": "Product Designer", "reasoning": "interaction design background"},
        ]
    }
    result = SuggestedRoles.model_validate(data)
    assert len(result.roles) == 2
    assert result.roles[0].title == "UX Designer"
    assert result.roles[0].reasoning == "3 years Figma experience"
    assert result.seniority_level == "Mid-level"


def test_suggested_roles_model_rejects_missing_title():
    from src.models import SuggestedRoles
    with pytest.raises(ValidationError):
        SuggestedRoles.model_validate({"seniority_level": "Mid-level", "roles": [{"reasoning": "no title here"}]})


def test_suggested_roles_model_empty_roles_list():
    from src.models import SuggestedRoles
    result = SuggestedRoles.model_validate({"seniority_level": "Entry-level", "roles": []})
    assert result.roles == []


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

def test_suggest_roles_prompt_exists_and_is_string():
    from src.prompts import SUGGEST_ROLES_PROMPT
    assert isinstance(SUGGEST_ROLES_PROMPT, str)
    assert len(SUGGEST_ROLES_PROMPT) > 50


def test_search_subagent_prompt_mentions_multiple_roles():
    from src.prompts import SEARCH_SUBAGENT_SYSTEM_PROMPT
    assert "multiple" in SEARCH_SUBAGENT_SYSTEM_PROMPT.lower() or \
           "roles" in SEARCH_SUBAGENT_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# suggest_roles tool
# ---------------------------------------------------------------------------

def test_suggest_roles_returns_formatted_string(tmp_path):
    """Tool returns a numbered list of titles with reasoning."""
    import yaml
    from src.models import SuggestedRoles, SuggestedRole

    resume = {"basics": {"name": "Jane", "location": "Remote"}, "work": []}
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(resume))

    config = {
        "paths": {"resume_yaml": str(resume_path)},
        "llm": {"temperature": 0.3, "max_retries": 3, "model": "m", "parser_model": "m"},
    }
    mock_result = SuggestedRoles(
        seniority_level="Mid-level",
        roles=[
            SuggestedRole(title="UX Designer", reasoning="3 years Figma experience"),
            SuggestedRole(title="Product Designer", reasoning="interaction design background"),
        ]
    )

    with patch("src.tools.suggest_roles._call_with_retry", return_value=mock_result):
        from src.tools.suggest_roles import create_suggest_roles_tool
        tool = create_suggest_roles_tool(config, MagicMock(), ["parser-model"])
        result = tool.invoke({})

    assert "1. UX Designer" in result
    assert "3 years Figma experience" in result
    assert "2. Product Designer" in result
    assert "Mid-level" in result


def test_suggest_roles_returns_message_for_empty_roles(tmp_path):
    """Tool returns a clear message when LLM returns an empty roles list."""
    import yaml
    from src.models import SuggestedRoles

    resume = {"basics": {"name": "Jane"}}
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(resume))

    config = {
        "paths": {"resume_yaml": str(resume_path)},
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "m", "parser_model": "m"},
    }
    empty_result = SuggestedRoles(seniority_level="Unknown", roles=[])

    with patch("src.tools.suggest_roles._call_with_retry", return_value=empty_result):
        from src.tools.suggest_roles import create_suggest_roles_tool
        tool = create_suggest_roles_tool(config, MagicMock(), ["parser-model"])
        result = tool.invoke({})

    assert "No role suggestions" in result


def test_suggest_roles_handles_llm_error(tmp_path):
    """Tool returns a plain error string instead of raising when LLM fails."""
    import yaml

    resume = {"basics": {"name": "Jane"}}
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(resume))

    config = {
        "paths": {"resume_yaml": str(resume_path)},
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "m", "parser_model": "m"},
    }

    with patch("src.tools.suggest_roles._call_with_retry", side_effect=RuntimeError("LLM down")):
        from src.tools.suggest_roles import create_suggest_roles_tool
        tool = create_suggest_roles_tool(config, MagicMock(), ["parser-model"])
        result = tool.invoke({})

    assert "Failed to suggest roles" in result
    assert "LLM down" in result


# ---------------------------------------------------------------------------
# Agent wiring
# ---------------------------------------------------------------------------

def test_build_agent_includes_suggest_roles_tool():
    """build_agent should include suggest_roles in the tool list."""
    import os

    config = {
        "provider": "local",
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "llama3.2:latest",
                "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": "resume.yaml", "template_yaml": "template.yaml",
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    resume = {"basics": {"name": "Test User", "location": "Remote"}}

    with patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.create_deep_agent") as mock_create, \
         patch("src.agent.create_search_tool", return_value=MagicMock(name="search_jobs")), \
         patch("src.agent.create_generate_batch_tool", return_value=MagicMock(name="generate_batch")), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_suggest_roles_tool", return_value=MagicMock(name="suggest_roles")) as mock_suggest, \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test"}):
        from src.agent import build_agent
        build_agent(config, resume, "local", "")

    mock_create.assert_called_once()
    tools_passed = mock_create.call_args.kwargs["tools"]
    assert mock_suggest.return_value in tools_passed
