"""
LLM provider implementations.

Each provider wraps a different backend SDK and exposes a single .call() method.
The factory function get_provider() returns the right instance based on the --provider CLI flag.
"""

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


class LLMProvider(ABC):
    @abstractmethod
    def call(self, model: str, system: str, prompt: str, temperature: float) -> str: ...


# ---------------------------------------------------------------------------
# Ollama — local (default, no API key required)
# ---------------------------------------------------------------------------

class LocalOllamaProvider(LLMProvider):
    """Uses the ollama.generate() function against a locally running Ollama server."""

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from ollama import generate
        response = generate(
            model=model,
            prompt=prompt,
            system=system,
            format="json",
            options={"temperature": temperature},
        )
        return response.response


# ---------------------------------------------------------------------------
# Ollama Cloud (requires OLLAMA_API_KEY)
# ---------------------------------------------------------------------------

class OllamaCloudProvider(LLMProvider):
    """Uses the ollama.Client against Ollama Cloud with bearer-token auth."""

    def __init__(self, host: str) -> None:
        from ollama import Client
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
        return response.message.content or ""


# ---------------------------------------------------------------------------
# OpenAI (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Run: uv add openai")
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
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Anthropic (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError("Anthropic SDK not installed. Run: uv add anthropic")
        self._client = anthropic.Anthropic(api_key=_require_key("ANTHROPIC_API_KEY", "anthropic"))

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from anthropic.types import TextBlock
        response = self._client.messages.create(
            model=model,
            max_tokens=8096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        for content_block in response.content:
            if isinstance(content_block, TextBlock):
                return content_block.text or ""
        return ""


# ---------------------------------------------------------------------------
# Google Gemini (requires GEMINI_API_KEY)
# ---------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            from google import genai
        except ImportError:
            raise ImportError("Google GenAI SDK not installed. Run: uv add google-genai")
        self._client = genai.Client(api_key=_require_key("GEMINI_API_KEY", "gemini"))

    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        from google.genai import types
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=temperature,
            ),
        )
        return response.text or ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

PROVIDER_NAMES = ["local", "cloud", "openai", "anthropic", "gemini"]


def get_provider(name: str, llm_cfg: dict) -> LLMProvider:
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


def resolve_models(name: str, llm_cfg: dict) -> tuple[str, str]:
    """Return (model, parser_model) for the given provider name.

    Looks first in llm.<provider>.model, then falls back to llm.model.
    parser_model falls back to model if not set.
    """
    provider_cfg = llm_cfg.get(name, {})
    model = provider_cfg.get("model") or llm_cfg.get("model", "llama3.2:latest")
    parser_model = provider_cfg.get("parser_model") or llm_cfg.get("parser_model") or model
    return model, parser_model
