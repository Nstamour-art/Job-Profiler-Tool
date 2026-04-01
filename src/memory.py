"""
Hindsight memory wrapper for the job search agent.

Connects to a user-hosted Hindsight server via HINDSIGHT_BASE_URL env var.
If the env var is not set or the server is unreachable, all operations
silently no-op — the agent still works without persistent memory.

To run a Hindsight server locally:
  docker run --rm -p 8888:8888 -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \\
    ghcr.io/vectorize-io/hindsight:latest
Then set HINDSIGHT_BASE_URL=http://localhost:8888 in your .env file.
"""

from __future__ import annotations

import os


try:
    from hindsight_client import Hindsight
    _CLIENT_AVAILABLE = True
except ImportError:
    _CLIENT_AVAILABLE = False


def _resolve_bank_id(config: dict, resume: dict) -> str:
    return (
        config.get("agent", {}).get("memory_bank", "").strip()
        or resume["basics"]["name"]
    )


class MemoryManager:
    """Thin wrapper around Hindsight retain/recall for the job search agent."""

    def __init__(self, config: dict, resume: dict, provider_name: str) -> None:  # pylint: disable=unused-argument
        self._bank_id = _resolve_bank_id(config, resume)
        self._available = False
        self._client = None

    def start(self) -> None:
        """Connect to the Hindsight server. Silent no-op if URL not configured."""
        if not _CLIENT_AVAILABLE:
            return
        base_url = os.environ.get("HINDSIGHT_BASE_URL", "").strip()
        if not base_url:
            return
        try:
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                base_url = "http://" + base_url
            if _CLIENT_AVAILABLE:
                self._client = Hindsight(base_url=base_url) # pyright: ignore
                self._available = True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            from src import ui  # pylint: disable=import-outside-toplevel
            ui.print_warning(
                f"Could not connect to Hindsight ({exc})"
                " — running without persistent memory."
            )

    def stop(self) -> None:
        """Close the Hindsight client session."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._client = None
            self._available = False

    def retain(self, content: str, context: str = "") -> None:
        """Store a fact or experience in the memory bank."""
        if not self._available or self._client is None:
            return
        try:
            self._client.retain(bank_id=self._bank_id, content=content, context=context)
        except Exception:  # pylint: disable=broad-exception-caught
            # Silently ignore errors — memory is optional, agent continues without it
            return

    def recall(self, query: str) -> str:
        """Retrieve memories relevant to the query. Returns empty string if unavailable."""
        if not self._available or self._client is None:
            return ""
        try:
            result = self._client.recall(bank_id=self._bank_id, query=query)
            if isinstance(result, list):
                return "\n".join(str(r) for r in result)
            return str(result) if result else ""
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    def reflect(self, query: str) -> str:
        """Reflect on memories to generate insights. Returns empty string if unavailable."""
        if not self._available or self._client is None:
            return ""
        try:
            result = self._client.reflect(bank_id=self._bank_id, query=query)
            return str(result) if result else ""
        except Exception:  # pylint: disable=broad-exception-caught
            return ""
