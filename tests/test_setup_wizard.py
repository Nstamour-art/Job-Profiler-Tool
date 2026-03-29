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
