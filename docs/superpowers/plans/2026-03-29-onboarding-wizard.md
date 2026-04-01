# Onboarding Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-run setup wizard that guides users through provider selection, API key entry, and optional Google Sheets config — eliminating all manual file editing — and fix the provider default so the chosen provider persists across runs.

**Architecture:** A new `src/setup_wizard.py` owns provider readiness checks and the interactive first-run wizard. `main.py` detects a missing `config.yaml` on any `run` or `template` command, chains the wizard → resume onboarding → template selection → start prompt, and resolves the provider from `config["provider"]` instead of hardcoding `"local"`. `example_config.yaml` gains a top-level `provider: "local"` key to document the new field.

**Tech Stack:** Python stdlib (`urllib.request`, `getpass`, `pathlib`), `pyyaml`, `python-dotenv`, `click`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/setup_wizard.py` | **Create** | `_ollama_reachable`, `_append_env`, `_prompt_for_api_key`, `ensure_provider_ready`, `_build_config`, `run_setup_wizard` |
| `example_config.yaml` | **Modify** | Add top-level `provider: "local"` key |
| `main.py` | **Modify** | First-run detection in `run_jobs` and `set_template`; provider default from config; `ensure_provider_ready` calls |
| `tests/test_setup_wizard.py` | **Create** | Unit tests for all wizard functions |

No changes to `src/onboarding.py`, `src/template_agent.py`, `src/providers.py`, or `src/agent.py`.

---

## Task 1: Add `provider` key to `example_config.yaml`

**Files:**
- Modify: `example_config.yaml`

- [ ] **Step 1: Add the key**

Open `example_config.yaml` and add `provider: "local"` as the very first key, before `google_sheets:`:

```yaml
provider: "local"   # default provider — set by setup wizard, overridden by --provider flag

google_sheets:
  # ... rest unchanged
```

- [ ] **Step 2: Commit**

```bash
git add example_config.yaml
git commit -m "feat: add provider key to example_config.yaml"
```

---

## Task 2: `src/setup_wizard.py` — provider utilities and `ensure_provider_ready`

**Files:**
- Create: `src/setup_wizard.py`
- Create: `tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_setup_wizard.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
uv run pytest tests/test_setup_wizard.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` for `src.setup_wizard`.

- [ ] **Step 3: Implement the utilities**

Create `src/setup_wizard.py`:

```python
"""
First-run setup wizard and runtime provider readiness check.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path

import yaml

# Maps provider name → environment variable name for its API key.
_API_KEY_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cloud": "OLLAMA_API_KEY",
}

_API_KEY_URLS: dict[str, str] = {
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/account/keys",
    "gemini": "https://aistudio.google.com/app/apikey",
    "cloud": "https://ollama.com",
}

_PROVIDER_MENU = """\

Choose your AI provider:

  1. Local Ollama  (free, runs on your machine — requires Ollama installed)
  2. OpenAI        (requires API key)
  3. Anthropic     (requires API key)
  4. Google Gemini (requires API key)
  5. Ollama Cloud  (requires API key)

Enter 1-5: """

_PROVIDER_NAMES = ["local", "openai", "anthropic", "gemini", "cloud"]


def _ollama_reachable() -> bool:
    """Return True if a local Ollama server is responding on localhost:11434."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=2)
        return True
    except Exception:
        return False


def _append_env(key: str, value: str, env_path: str = ".env") -> None:
    """Append or replace a KEY=value line in the .env file."""
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [l for l in lines if not l.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prompt_for_api_key(provider_name: str, key_var: str, env_path: str = ".env") -> str:
    """Prompt for an API key, write it to .env, and reload dotenv in the current process."""
    from dotenv import load_dotenv
    url = _API_KEY_URLS.get(provider_name, "")
    print(f"\n  Get your {provider_name.capitalize()} API key at: {url}")
    key = getpass.getpass(f"  Enter {provider_name.capitalize()} API key: ").strip()
    while not key:
        print("  API key cannot be empty.")
        key = getpass.getpass(f"  Enter {provider_name.capitalize()} API key: ").strip()
    _append_env(key_var, key, env_path)
    load_dotenv(override=True)
    return key


def ensure_provider_ready(
    provider_name: str, config: dict, env_path: str = ".env"
) -> None:
    """Verify the requested provider is usable; prompt for setup if not.

    Raises SystemExit if the user cannot or will not complete setup.
    """
    if provider_name == "local":
        if not _ollama_reachable():
            print("\n  Ollama doesn't appear to be running.")
            print("  Install it from https://ollama.com, then run this tool again.")
            print("  Or pass --provider <name> to use a cloud provider.\n")
            raise SystemExit(1)
    else:
        key_var = _API_KEY_VARS[provider_name]
        if not os.environ.get(key_var, "").strip():
            print(f"\n  {provider_name.capitalize()} API key not found.")
            _prompt_for_api_key(provider_name, key_var, env_path)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_setup_wizard.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/setup_wizard.py tests/test_setup_wizard.py
git commit -m "feat: add setup_wizard provider utilities and ensure_provider_ready"
```

---

## Task 3: `src/setup_wizard.py` — `_build_config` and `run_setup_wizard`

**Files:**
- Modify: `src/setup_wizard.py`
- Modify: `tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_setup_wizard.py`:

```python
# ---------------------------------------------------------------------------
# run_setup_wizard
# ---------------------------------------------------------------------------

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
    # local, sheets=yes, spreadsheet id, worksheet name (Enter=Sheet1), default creds path (Enter)
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_setup_wizard.py::test_run_setup_wizard_local_writes_config -v
```

Expected: FAIL with `ImportError` (functions not defined yet).

- [ ] **Step 3: Implement `_build_config` and `run_setup_wizard`**

Append to `src/setup_wizard.py`:

```python
def _build_config(provider: str, sheets: dict | None) -> dict:
    """Return a complete config dict for the given provider and optional sheets config."""
    cfg: dict = {
        "provider": provider,
        "llm": {
            "temperature": 0.3,
            "max_retries": 3,
            "model": "llama3.2:latest",
            "parser_model": "llama3.2:latest",
            "cloud": {
                "host": "https://ollama.com",
                "model": "gpt-oss:120b",
                "fallback_models": [],
                "parser_model": "nemotron-3-nano:30b",
                "parser_fallback_models": [],
            },
            "openai": {
                "model": "gpt-4o",
                "fallback_models": ["gpt-4o-mini"],
                "parser_model": "gpt-4o-mini",
                "parser_fallback_models": [],
            },
            "anthropic": {
                "model": "claude-opus-4-6",
                "fallback_models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
                "parser_model": "claude-haiku-4-5-20251001",
                "parser_fallback_models": [],
            },
            "gemini": {
                "model": "gemini-2.5-pro-preview-03-25",
                "fallback_models": ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
                "parser_model": "gemini-2.0-flash",
                "parser_fallback_models": ["gemini-2.0-flash-lite"],
            },
        },
        "paths": {
            "resume_yaml": "resume.yaml",
            "template_yaml": "template.yaml",
            "output_dir": "output",
            "credentials": "credentials/google_service_account.json",
        },
        "agent": {
            "max_jobs": 10,
            "memory_bank": "",
            "memory_model": "",
        },
    }
    if sheets:
        cfg["google_sheets"] = sheets
    return cfg


def run_setup_wizard(
    config_path: str = "config.yaml", env_path: str = ".env"
) -> dict:
    """Run the interactive first-run setup wizard. Returns the completed config dict."""
    print("\nWelcome to Job Profiler Tool!")
    print("Let's get you set up. This will only take a couple of minutes.\n")

    # --- Provider selection ---
    while True:
        choice = input(_PROVIDER_MENU).strip()
        if choice in ("1", "2", "3", "4", "5"):
            provider = _PROVIDER_NAMES[int(choice) - 1]
            break
        print("  Please enter a number from 1 to 5.")

    # --- Provider-specific setup ---
    if provider == "local":
        if _ollama_reachable():
            model = "llama3.2:latest"
            pull = input(
                f"\n  Ollama is running. Pull {model} now? (yes / no)\n> "
            ).strip().lower()
            if pull == "yes":
                import subprocess
                print(f"  Pulling {model} ...")
                subprocess.run(["ollama", "pull", model], check=False)
        else:
            print("\n  Ollama doesn't appear to be running.")
            print("  Install it from https://ollama.com, then re-run this tool.")
            input("\n  Press Enter to choose a different provider, or Ctrl+C to exit.\n> ")
            return run_setup_wizard(config_path, env_path)
    else:
        key_var = _API_KEY_VARS[provider]
        if not os.environ.get(key_var, "").strip():
            _prompt_for_api_key(provider, key_var, env_path)

    # --- Google Sheets (optional) ---
    sheets: dict | None = None
    use_sheets = input(
        "\nDo you want to track jobs in a Google Sheet? (yes / no)\n> "
    ).strip().lower()
    if use_sheets == "yes":
        spreadsheet_id = input(
            "\n  Spreadsheet ID (from the URL of your Google Sheet):\n> "
        ).strip()
        worksheet = (
            input("  Worksheet name (press Enter for 'Sheet1'):\n> ").strip() or "Sheet1"
        )
        creds_path = (
            input(
                "  Path to service account JSON (press Enter for default):\n> "
            ).strip()
            or "credentials/google_service_account.json"
        )
        sheets = {
            "spreadsheet_id": spreadsheet_id,
            "worksheet_name": worksheet,
            "columns": {
                "job_title": "Title",
                "company": "Company",
                "url": "URL",
                "status": "Status",
                "date_found": "Date Found",
                "details": "Details",
                "priority": "Priority",
                "reasoning": "Reasoning",
            },
        }
        if creds_path != "credentials/google_service_account.json":
            _append_env("GOOGLE_CREDENTIALS_PATH", creds_path, env_path)

    # --- Write config.yaml ---
    config = _build_config(provider, sheets)
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"\n  config.yaml created. Provider: {provider.capitalize()}\n")
    return config
```

- [ ] **Step 4: Run the full test file**

```bash
uv run pytest tests/test_setup_wizard.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/setup_wizard.py tests/test_setup_wizard.py
git commit -m "feat: implement run_setup_wizard with provider selection and Google Sheets config"
```

---

## Task 4: `main.py` — provider default fix and `ensure_provider_ready`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_setup_wizard.py`:

```python
# ---------------------------------------------------------------------------
# main.py — provider default from config
# ---------------------------------------------------------------------------

import yaml
from click.testing import CliRunner


def test_template_command_uses_config_provider_as_default(tmp_path):
    """When no --provider flag is passed, template should use config["provider"]."""
    config = {
        "provider": "gemini",
        "llm": {"temperature": 0.3, "max_retries": 3, "model": "llama3.2:latest",
                "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": "resume.yaml", "template_yaml": str(tmp_path / "template.yaml"),
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    with patch("src.setup_wizard.ensure_provider_ready"), \
         patch("src.template_agent.run_template_wizard") as mock_wizard:
        from main import cli
        runner = CliRunner()
        runner.invoke(cli, ["--config", str(config_path), "template"])
    # provider passed to run_template_wizard must be "gemini", not "local"
    mock_wizard.assert_called_once()
    _, called_provider = mock_wizard.call_args[0]
    assert called_provider == "gemini"


def test_run_command_uses_config_provider_as_default(tmp_path):
    """run command without --provider should use config["provider"]."""
    config = {
        "provider": "anthropic",
        "llm": {"temperature": 0.3, "max_retries": 3, "model": "llama3.2:latest",
                "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": str(tmp_path / "resume.yaml"),
                  "template_yaml": str(tmp_path / "template.yaml"),
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text("basics: {name: Test}")

    with patch("src.setup_wizard.ensure_provider_ready"), \
         patch("src.agent.run_agent_chat") as mock_agent:
        from main import cli
        runner = CliRunner()
        runner.invoke(cli, ["--config", str(config_path), "run"])
    mock_agent.assert_called_once()
    assert mock_agent.call_args[1]["provider_name"] == "anthropic"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_setup_wizard.py::test_template_command_uses_config_provider_as_default tests/test_setup_wizard.py::test_run_command_uses_config_provider_as_default -v
```

Expected: FAIL — both commands currently hardcode `"local"`.

- [ ] **Step 3: Fix `set_template` in `main.py`**

Replace the `set_template` function:

```python
@cli.command("template")
@click.option("--provider", "provider_name", default=None,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider to use for customization extraction.")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def set_template(provider_name, config_path):
    """Interactively choose and customize your resume template."""
    from pathlib import Path
    if not Path(config_path).exists():
        from src.setup_wizard import run_setup_wizard
        config = run_setup_wizard(config_path)
    else:
        config = load_config(config_path)

    resolved_provider = provider_name or config.get("provider", "local")

    from src.setup_wizard import ensure_provider_ready
    ensure_provider_ready(resolved_provider, config)
    run_template_wizard(config, resolved_provider)
```

- [ ] **Step 4: Fix provider resolution in `run_jobs`**

In `run_jobs`, replace:

```python
    resolved_provider = provider_name or "local"
```

with:

```python
    resolved_provider = provider_name or config.get("provider", "local")
```

This line appears twice inside `run_jobs` (once in normal flow, which we'll restructure in Task 5). For now, fix the one at line ~112 that applies to the direct URL and agent paths.

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_setup_wizard.py -v
```

Expected: all 17 tests pass.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_setup_wizard.py
git commit -m "fix: resolve default provider from config instead of hardcoding local"
```

---

## Task 5: `main.py` — first-run detection in `run_jobs`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_setup_wizard.py`:

```python
# ---------------------------------------------------------------------------
# main.py — first-run detection
# ---------------------------------------------------------------------------

def test_run_command_triggers_setup_when_config_missing(tmp_path):
    """When config.yaml doesn't exist, run should call run_setup_wizard."""
    config_path = tmp_path / "config.yaml"
    # config does NOT exist yet

    mock_config = {
        "provider": "gemini",
        "llm": {"temperature": 0.3, "max_retries": 3, "model": "m", "parser_model": "m"},
        "paths": {"resume_yaml": str(tmp_path / "resume.yaml"),
                  "template_yaml": str(tmp_path / "template.yaml"),
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }

    with patch("src.setup_wizard.run_setup_wizard", return_value=mock_config) as mock_wizard, \
         patch("src.onboarding.run_onboarding", return_value={}), \
         patch("src.template_agent.run_template_wizard"), \
         patch("builtins.input", return_value="no"):
        from main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--config", str(config_path), "run"])

    mock_wizard.assert_called_once_with(str(config_path))
```

- [ ] **Step 2: Run test — verify it fails**

```bash
uv run pytest tests/test_setup_wizard.py::test_run_command_triggers_setup_when_config_missing -v
```

Expected: FAIL — setup wizard is not triggered yet.

- [ ] **Step 3: Restructure `run_jobs` to add first-run detection**

Replace the body of `run_jobs` in `main.py` from the point after the flag-validation block:

```python
def run_jobs(direct_url, resume_only, cover_only, provider_name, config_path, debug,
             row_num, run_all, force):
    """Search for jobs with the agent, or process a single URL with --url."""
    if row_num is not None or run_all or force:
        raise click.UsageError(
            "--row, --all, and --force are no longer supported.\n"
            "Run without --url to use the new agent-driven search mode.\n"
            "The Google Sheet is now an output log — the agent writes to it automatically."
        )

    if resume_only and cover_only:
        raise click.UsageError("Cannot use --resume-only and --cover-only together.")

    from pathlib import Path

    # --- First-run: config.yaml doesn't exist yet ---
    if not Path(config_path).exists():
        from src.setup_wizard import run_setup_wizard
        config = run_setup_wizard(config_path)
        resolved_provider = provider_name or config.get("provider", "local")

        resume_yaml = config["paths"]["resume_yaml"]
        if not Path(resume_yaml).exists():
            from src.onboarding import run_onboarding
            run_onboarding(config, resolved_provider)

        template_yaml = config.get("paths", {}).get("template_yaml", "template.yaml")
        if not Path(template_yaml).exists():
            run_template_wizard(config, resolved_provider)

        answer = input(
            "\nSetup complete! Ready to start the job search agent? (yes / no)\n> "
        ).strip().lower()
        if answer != "yes":
            click.echo("\nRun 'uv run python main.py run' when you're ready.\n")
            return

        from src.agent import run_agent_chat
        run_agent_chat(config=config, provider_name=resolved_provider)
        return

    # --- Normal flow: config.yaml exists ---
    config = load_config(config_path)
    if "template_yaml" not in config.get("paths", {}):
        config.setdefault("paths", {})["template_yaml"] = "template.yaml"

    from src.providers import get_provider, resolve_models
    resolved_provider = provider_name or config.get("provider", "local")

    from src.setup_wizard import ensure_provider_ready
    ensure_provider_ready(resolved_provider, config)

    # --- Direct URL mode ---
    if direct_url:
        resume = load_resume(config["paths"]["resume_yaml"])
        llm_cfg = config["llm"]
        provider = get_provider(resolved_provider, llm_cfg)
        models, parser_models = resolve_models(resolved_provider, llm_cfg)
        click.echo(f"Provider: {resolved_provider}  |  model: {models[0]}  |  parser: {parser_models[0]}")

        from src.debug import init_db, log_run
        if debug:
            init_db()
            click.echo(click.style("  Debug mode enabled — logging to debug.db", fg="cyan"))

        from src.pipeline import process_job
        job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
        click.echo(f"\nProcessing: {direct_url}")
        debug_run_id = log_run(direct_url, resolved_provider, models[0], parser_models[0]) if debug else None
        folder, _, resume_json = process_job(
            job, config, resume, provider, models, parser_models,
            resume_only=resume_only, cover_only=cover_only,
            debug_run_id=debug_run_id,
        )
        if resume_json is not None:
            click.echo(f"  Priority: {resume_json.priority}/10 — {resume_json.priority_reasoning}")
        click.echo(click.style(f"\n  Saved to: {folder}", fg="green"))
        return

    # --- Agent mode ---
    from src.agent import run_agent_chat
    run_agent_chat(config=config, provider_name=resolved_provider)
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/test_setup_wizard.py -v
```

Expected: all 18 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_setup_wizard.py
git commit -m "feat: add first-run detection in run_jobs; chain setup → onboarding → template → start"
```

---

## Self-Review

**Spec coverage:**
- [x] `run_setup_wizard()` — Task 3
- [x] `ensure_provider_ready()` — Task 2
- [x] `_ollama_reachable` + install guide — Task 2
- [x] API key prompting + `.env` write — Task 2 + Task 3
- [x] Google Sheets optional step — Task 3
- [x] `provider` key in `example_config.yaml` — Task 1
- [x] Provider default from `config["provider"]` — Task 4
- [x] First-run detection in `run_jobs` — Task 5
- [x] First-run detection in `set_template` — Task 4 (set_template)
- [x] `ensure_provider_ready` call in both commands — Task 4 + Task 5

**Placeholder scan:** None found. All steps contain concrete code.

**Type consistency:**
- `ensure_provider_ready(provider_name: str, config: dict, env_path: str = ".env")` — consistent across definition (Task 2) and call sites (Task 4 + Task 5).
- `run_setup_wizard(config_path: str, env_path: str)` — consistent across definition (Task 3) and call sites (Task 5 uses single-arg call `run_setup_wizard(config_path)` — default `env_path=".env"` applies correctly).
- `_prompt_for_api_key(provider_name, key_var, env_path)` — called with 3 args in `ensure_provider_ready` (Task 2) and `run_setup_wizard` (Task 3). Matches definition.
