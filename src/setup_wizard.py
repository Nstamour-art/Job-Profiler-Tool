"""
First-run setup wizard and runtime provider readiness check.
"""
from __future__ import annotations

import getpass
import os
import urllib.request
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
        urllib.request.urlopen("http://localhost:11434/", timeout=2)
        return True
    except Exception:
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
        key_var = _API_KEY_VARS.get(provider_name)
        if key_var is None:
            raise ValueError(f"Unknown provider: {provider_name!r}. Choose from: {list(_PROVIDER_NAMES)}")
        if not os.environ.get(key_var, "").strip():
            print(f"\n  {provider_name.capitalize()} API key not found.")
            _prompt_for_api_key(provider_name, key_var, env_path)
