"""
LLM provider implementations.

Each provider wraps a different backend SDK and exposes a single .call() method.
The factory function get_provider() returns the right instance based on the --provider CLI flag.
"""
# pylint: disable=too-few-public-methods,no-member

import os
from abc import ABC, abstractmethod


def _require_key(env_var: str, provider: str) -> str:
    """Return the value of env_var, or raise a clear error if it is missing."""
    value = os.environ.get(env_var, "").strip()
    if not value:
        raise EnvironmentError(
            f"Missing API key for --provider {provider}: "
            f"set {env_var} in your .env file."
        )
    return value


class BaseProvider(ABC):
    """Abstract base class for all LLM providers.

    All subclasses must implement the .call() method.
    """

    @abstractmethod
    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        """Execute a chat completion request."""


# ---------------------------------------------------------------------------
# Ollama — local (default, no API key required)
# ---------------------------------------------------------------------------

class LocalOllamaProvider(BaseProvider):
    """Uses the ollama.generate() function against a locally running Ollama server."""

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from ollama import generate  # pylint: disable=import-outside-toplevel
        response = generate(
            model=model,
            prompt=prompt,
            system=system,
            format="json",
            options={"temperature": temperature},
        )
        return response.response or ""


# ---------------------------------------------------------------------------
# Ollama Cloud (requires OLLAMA_API_KEY)
# ---------------------------------------------------------------------------

class OllamaCloudProvider(BaseProvider):
    """Uses the ollama.Client against Ollama Cloud with bearer-token auth."""

    def __init__(self, host: str) -> None:
        from ollama import Client  # pylint: disable=import-outside-toplevel
        api_key = _require_key("OLLAMA_API_KEY", "cloud")
        self._client = Client(
            host=host,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        response = self._client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            format="json",
            options={"temperature": temperature},
        )
        if response.message and response.message.content:
            return str(response.message.content)
        return ""


# ---------------------------------------------------------------------------
# OpenAI (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseProvider):
    """OpenAI chat completions provider (requires OPENAI_API_KEY)."""

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError("OpenAI SDK not installed. Run: uv add openai") from exc
        self._client = OpenAI(api_key=_require_key("OPENAI_API_KEY", "openai"))

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        return str(response.choices[0].message.content or "")


# ---------------------------------------------------------------------------
# Anthropic (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseProvider):
    """Anthropic Messages API provider (requires ANTHROPIC_API_KEY)."""

    def __init__(self) -> None:
        try:
            import anthropic  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError("Anthropic SDK not installed. Run: uv add anthropic") from exc
        self._client = anthropic.Anthropic(api_key=_require_key("ANTHROPIC_API_KEY", "anthropic"))

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from anthropic.types import TextBlock  # pylint: disable=import-outside-toplevel
        response = self._client.messages.create(
            model=model,
            max_tokens=8096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        for content_block in response.content:
            if isinstance(content_block, TextBlock):
                return str(content_block.text or "")
        return ""


# ---------------------------------------------------------------------------
# Google Gemini (requires GEMINI_API_KEY)
# ---------------------------------------------------------------------------

class GeminiProvider(BaseProvider):
    """Google Gemini provider via google-genai SDK (requires GEMINI_API_KEY)."""

    def __init__(self) -> None:
        try:
            from google import genai  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError("Google GenAI SDK not installed. Run: uv add google-genai") from exc
        self._client = genai.Client(api_key=_require_key("GEMINI_API_KEY", "gemini"))

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from google.genai import types  # pylint: disable=import-outside-toplevel
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=temperature,
            ),
        )
        return str(response.text or "")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

PROVIDER_NAMES = ["local", "cloud", "openai", "anthropic", "gemini"]

_RATE_ERROR_SIGNALS = {
    "503", "429",
    "rate limit", "quota", "quota exceeded",
    "unavailable", "overloaded", "too many requests",
    "resource exhausted", "capacity",
}


def is_rate_error(exc: Exception) -> bool:
    """Return True if the exception looks like a rate-limit or capacity error."""
    msg = str(exc).lower()
    return any(signal in msg for signal in _RATE_ERROR_SIGNALS)


# Private alias kept for callers in llm.py
_is_rate_error = is_rate_error


def get_provider(name: str, llm_cfg: dict) -> BaseProvider:
    """Instantiate and return the LLM provider for the given name."""
    match name:
        case "local":
            return LocalOllamaProvider()
        case "cloud":
            host = llm_cfg.get("cloud", {}).get("host", "https://ollama.com")
            return OllamaCloudProvider(host=host)
        case "openai":
            return OpenAIProvider()
        case "anthropic":
            return AnthropicProvider()
        case "gemini":
            return GeminiProvider()
        case _:
            raise ValueError(
                f"Unknown provider '{name}'. Valid options: {', '.join(PROVIDER_NAMES)}"
            )


def resolve_models(name: str, llm_cfg: dict) -> tuple[list[str], list[str]]:
    """Return (models, parser_models) for the given provider name.

    Each list starts with the primary model followed by any configured fallbacks.
    Looks first in llm.<provider>, then falls back to top-level llm keys.
    """
    provider_cfg = llm_cfg.get(name, {})

    primary = provider_cfg.get("model") or llm_cfg.get("model", "llama3.2:latest")
    fallbacks = provider_cfg.get("fallback_models", [])
    models = [primary] + list(fallbacks)

    primary_parser = provider_cfg.get("parser_model") or llm_cfg.get("parser_model") or primary
    parser_fallbacks = provider_cfg.get("parser_fallback_models", [])
    parser_models = [primary_parser] + list(parser_fallbacks)

    return models, parser_models
