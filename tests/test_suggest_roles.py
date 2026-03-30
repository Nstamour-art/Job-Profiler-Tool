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
        "roles": [
            {"title": "UX Designer", "reasoning": "3 years Figma experience"},
            {"title": "Product Designer", "reasoning": "interaction design background"},
        ]
    }
    result = SuggestedRoles.model_validate(data)
    assert len(result.roles) == 2
    assert result.roles[0].title == "UX Designer"
    assert result.roles[0].reasoning == "3 years Figma experience"


def test_suggested_roles_model_rejects_missing_title():
    from src.models import SuggestedRoles
    with pytest.raises(ValidationError):
        SuggestedRoles.model_validate({"roles": [{"reasoning": "no title here"}]})


def test_suggested_roles_model_empty_roles_list():
    from src.models import SuggestedRoles
    result = SuggestedRoles.model_validate({"roles": []})
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
