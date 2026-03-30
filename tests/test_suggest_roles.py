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
