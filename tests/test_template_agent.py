# tests/test_template_agent.py
import yaml
import pytest
from unittest.mock import patch, MagicMock

from src.themes import CLASSIC, MODERN, CREATIVE, MINIMAL, ThemeConfig


@pytest.fixture
def sample_config():
    return {
        "llm": {"temperature": 0.3, "max_retries": 1,
                "model": "llama3.2:latest", "parser_model": "llama3.2:latest"},
        "paths": {"template_yaml": "/tmp/test_template.yaml"},
    }


def test_wizard_picks_classic_no_customization(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("builtins.input", side_effect=["1", "", "yes"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.name == "classic"
    saved = yaml.safe_load(open(template_path, encoding="utf-8"))
    assert saved["theme"] == "classic"


def test_wizard_picks_modern_no_customization(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("builtins.input", side_effect=["2", "", "yes"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.name == "modern"


def test_wizard_applies_body_pt_override(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    from src.themes import TemplateOverrides
    mock_overrides = TemplateOverrides(body_pt=12.0)

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("src.template_agent._extract_overrides", return_value=mock_overrides), \
         patch("builtins.input", side_effect=["2", "bigger body text", "yes"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.body_pt == 12.0
    saved = yaml.safe_load(open(template_path, encoding="utf-8"))
    assert saved["overrides"]["body_pt"] == 12.0


def test_wizard_skip_keeps_base_theme(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    from src.themes import TemplateOverrides
    mock_overrides = TemplateOverrides(body_pt=12.0)

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("src.template_agent._extract_overrides", return_value=mock_overrides), \
         patch("builtins.input", side_effect=["2", "bigger body text", "skip"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.body_pt == MODERN.body_pt  # overrides discarded


def test_wizard_invalid_menu_input_loops(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("builtins.input", side_effect=["0", "5", "abc", "3", "", "yes"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.name == "creative"


def test_wizard_extraction_failure_falls_back_to_base(sample_config, tmp_path):
    template_path = str(tmp_path / "template.yaml")
    sample_config["paths"]["template_yaml"] = template_path

    with patch("src.template_agent.get_provider", return_value=MagicMock()), \
         patch("src.template_agent.resolve_models", return_value=(["m"], ["m"])), \
         patch("src.template_agent._extract_overrides", side_effect=ValueError("bad json")), \
         patch("builtins.input", side_effect=["1", "something", "yes"]):
        from src.template_agent import run_template_wizard
        result = run_template_wizard(sample_config, "local")

    assert result.name == "classic"
    assert result.body_pt == CLASSIC.body_pt
