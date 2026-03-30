"""Tests for src/setup_wizard.py — provider utilities and ensure_provider_ready."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# _ollama_reachable
# ---------------------------------------------------------------------------

def test_ollama_reachable_returns_true_when_server_up():
    with patch("urllib.request.urlopen"):
        from src.setup_wizard import _ollama_reachable
        assert _ollama_reachable() is True


def test_ollama_reachable_returns_false_when_server_down():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        from src.setup_wizard import _ollama_reachable
        assert _ollama_reachable() is False


# ---------------------------------------------------------------------------
# _append_env
# ---------------------------------------------------------------------------

def test_append_env_creates_file(tmp_path):
    env_path = tmp_path / ".env"
    from src.setup_wizard import _append_env
    _append_env("TEST_KEY", "abc123", str(env_path))
    assert "TEST_KEY=abc123" in env_path.read_text()


def test_append_env_updates_existing_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("TEST_KEY=old\nOTHER=x\n")
    from src.setup_wizard import _append_env
    _append_env("TEST_KEY", "new", str(env_path))
    content = env_path.read_text()
    assert "TEST_KEY=new" in content
    assert "TEST_KEY=old" not in content
    assert "OTHER=x" in content


def test_append_env_preserves_other_keys(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-abc\nGEMINI_API_KEY=gk-xyz\n")
    from src.setup_wizard import _append_env
    _append_env("ANTHROPIC_API_KEY", "ak-new", str(env_path))
    content = env_path.read_text()
    assert "OPENAI_API_KEY=sk-abc" in content
    assert "GEMINI_API_KEY=gk-xyz" in content
    assert "ANTHROPIC_API_KEY=ak-new" in content


# ---------------------------------------------------------------------------
# ensure_provider_ready
# ---------------------------------------------------------------------------

def test_ensure_provider_ready_local_reachable_does_nothing():
    with patch("src.setup_wizard._ollama_reachable", return_value=True):
        from src.setup_wizard import ensure_provider_ready
        ensure_provider_ready("local", {})  # must not raise


def test_ensure_provider_ready_local_unreachable_raises_system_exit():
    with patch("src.setup_wizard._ollama_reachable", return_value=False):
        from src.setup_wizard import ensure_provider_ready
        with pytest.raises(SystemExit):
            ensure_provider_ready("local", {})


def test_ensure_provider_ready_gemini_with_key_does_nothing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from src.setup_wizard import ensure_provider_ready
    ensure_provider_ready("gemini", {})  # must not raise


def test_ensure_provider_ready_gemini_missing_key_calls_prompt(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("src.setup_wizard._prompt_for_api_key") as mock_prompt:
        from src.setup_wizard import ensure_provider_ready
        ensure_provider_ready("gemini", {})
        mock_prompt.assert_called_once_with("gemini", "GEMINI_API_KEY", ".env")


# ---------------------------------------------------------------------------
# run_setup_wizard
# ---------------------------------------------------------------------------

import yaml


def test_run_setup_wizard_local_writes_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    inputs = ["1", "no"]  # select local, skip google sheets
    with patch("src.setup_wizard._ollama_reachable", return_value=True), \
         patch("builtins.input", side_effect=inputs):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["provider"] == "local"
    saved = yaml.safe_load(config_path.read_text())
    assert saved["provider"] == "local"
    assert "llm" in saved
    assert "paths" in saved


def test_run_setup_wizard_gemini_prompts_for_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    inputs = ["4", "no"]  # select gemini, skip google sheets
    with patch("builtins.input", side_effect=inputs), \
         patch("src.setup_wizard._prompt_for_api_key", return_value="test-key") as mock_prompt:
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["provider"] == "gemini"
    mock_prompt.assert_called_once_with("gemini", "GEMINI_API_KEY", str(env_path))


def test_run_setup_wizard_invalid_choice_loops(tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    inputs = ["9", "x", "2", "no"]  # two bad choices, then openai, skip sheets
    with patch("builtins.input", side_effect=inputs), \
         patch("src.setup_wizard._prompt_for_api_key", return_value="sk-test"):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["provider"] == "openai"


def test_run_setup_wizard_google_sheets_yes(tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    # local, sheets=yes, spreadsheet id, worksheet name, default creds path (Enter)
    inputs = ["1", "yes", "abc123spreadsheetid", "Jobs", ""]
    with patch("src.setup_wizard._ollama_reachable", return_value=True), \
         patch("builtins.input", side_effect=inputs):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["google_sheets"]["spreadsheet_id"] == "abc123spreadsheetid"
    assert result["google_sheets"]["worksheet_name"] == "Jobs"
    assert "columns" in result["google_sheets"]


def test_run_setup_wizard_google_sheets_no(tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    inputs = ["1", "no"]
    with patch("src.setup_wizard._ollama_reachable", return_value=True), \
         patch("builtins.input", side_effect=inputs):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert "google_sheets" not in result


def test_run_setup_wizard_google_sheets_default_worksheet(tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    inputs = ["1", "yes", "sheetid", "", ""]  # Enter = default worksheet "Sheet1"
    with patch("src.setup_wizard._ollama_reachable", return_value=True), \
         patch("builtins.input", side_effect=inputs):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["google_sheets"]["worksheet_name"] == "Sheet1"


def test_run_setup_wizard_local_unreachable_loops_back_to_menu(tmp_path):
    """When Ollama is unreachable, wizard loops back to provider selection."""
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    # First choice: local (fails — Ollama unreachable)
    # User presses Enter to go back, then picks Gemini
    inputs = ["1", "", "4", "no"]
    reachable_sequence = [False, True]  # unreachable first time, irrelevant after
    with patch("src.setup_wizard._ollama_reachable", side_effect=reachable_sequence), \
         patch("builtins.input", side_effect=inputs), \
         patch("src.setup_wizard._prompt_for_api_key", return_value="test-key"):
        from src.setup_wizard import run_setup_wizard
        result = run_setup_wizard(str(config_path), str(env_path))
    assert result["provider"] == "gemini"
