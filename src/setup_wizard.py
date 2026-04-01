"""
First-run setup wizard and runtime provider readiness check.
"""
from __future__ import annotations

import getpass
import os
import urllib.request
import urllib.error
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
    try:
        with urllib.request.urlopen("http://localhost:11434/", timeout=2):
            return True
    except (OSError, urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def _append_env(key: str, value: str, env_path: str = ".env") -> None:
    """Append or replace a KEY=value line in the .env file."""
    value = value.replace("\r", "").replace("\n", "")
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prompt_for_api_key(provider_name: str, key_var: str, env_path: str = ".env") -> str:
    """Prompt for an API key, write it to .env, and reload dotenv in the current process."""
    from dotenv import load_dotenv  # pylint: disable=import-outside-toplevel
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
    provider_name: str, _config: dict, env_path: str = ".env"
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
        key_var = _API_KEY_VARS.get(provider_name)
        if key_var is None:
            raise ValueError(
                f"Unknown provider: {provider_name!r}. Choose from: {list(_PROVIDER_NAMES)}"
            )
        if not os.environ.get(key_var, "").strip():
            print(f"\n  {provider_name.capitalize()} API key not found.")
            _prompt_for_api_key(provider_name, key_var, env_path)


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

    # --- Provider selection + provider-specific setup ---
    while True:
        while True:
            choice = input(_PROVIDER_MENU).strip()
            if choice in ("1", "2", "3", "4", "5"):
                provider = _PROVIDER_NAMES[int(choice) - 1]
                break
            print("  Please enter a number from 1 to 5.")

        if provider == "local":
            if _ollama_reachable():
                print("\n  Ollama is running.\n")
                break
            print("\n  Ollama doesn't appear to be running.")
            print("  Install it from https://ollama.com, then re-run this tool.")
            input("\n  Press Enter to choose a different provider, or Ctrl+C to exit.\n> ")
            # Loop back to provider selection
            continue
        key_var = _API_KEY_VARS[provider]
        if not os.environ.get(key_var, "").strip():
            _prompt_for_api_key(provider, key_var, env_path)
        break

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
