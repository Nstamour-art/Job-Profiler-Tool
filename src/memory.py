"""
LangChain-based persistent memory for the job search agent.

Facts retained during each session are stored in an encrypted file at
~/.job-profiler/<bank_id>.enc using Fernet (AES-128-CBC + HMAC-SHA256).
The Fernet key is stored at ~/.job-profiler/.key with mode 0o600.

The public interface (start, stop, retain, recall) is identical to the
previous Hindsight-backed implementation so src/agent.py needs only minor
changes.  All operations silently no-op on any error so the agent always
starts successfully.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

from cryptography.fernet import Fernet
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict


_MEMORY_DIR = Path.home() / ".job-profiler"
_KEY_FILE = _MEMORY_DIR / ".key"
MAX_RECALL_ENTRIES = 30


def _resolve_bank_id(config: dict, resume: dict) -> str:
    return (
        config.get("agent", {}).get("memory_bank", "").strip()
        or resume.get("basics", {}).get("name", "default")
    )


def _sanitize_bank_id(bank_id: str) -> str:
    """Return a filesystem-safe name by keeping only alphanumeric characters and underscores."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", bank_id)
    return sanitized or "default"


def _get_or_create_key() -> bytes | None:
    """Return the Fernet key, creating it (and the storage dir) if needed."""
    try:
        _MEMORY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(_MEMORY_DIR, stat.S_IRWXU)
        if _KEY_FILE.exists():
            return _KEY_FILE.read_bytes()
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
        return key
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _load_history(path: Path, fernet: Fernet) -> InMemoryChatMessageHistory:
    """Decrypt and deserialise a saved history file into an in-memory store."""
    history = InMemoryChatMessageHistory()
    try:
        if path.exists():
            raw = fernet.decrypt(path.read_bytes())
            messages = messages_from_dict(json.loads(raw))
            history.add_messages(messages)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return history


def _save_history(path: Path, fernet: Fernet, history: InMemoryChatMessageHistory) -> None:
    """Serialise and encrypt the in-memory history to disk."""
    try:
        raw = json.dumps(messages_to_dict(history.messages)).encode()
        path.write_bytes(fernet.encrypt(raw))
    except Exception:  # pylint: disable=broad-exception-caught
        pass


class MemoryManager:
    """Encrypted persistent memory for the job search agent."""

    def __init__(self, config: dict, resume: dict, provider_name: str) -> None:  # pylint: disable=unused-argument
        self._bank_id = _sanitize_bank_id(_resolve_bank_id(config, resume))
        self._memory_path = _MEMORY_DIR / f"{self._bank_id}.enc"
        self._fernet: Fernet | None = None
        self._history: InMemoryChatMessageHistory | None = None

    def start(self) -> None:
        """Load (or initialise) the encrypted memory store."""
        try:
            key = _get_or_create_key()
            if key is None:
                return
            self._fernet = Fernet(key)
            self._history = _load_history(self._memory_path, self._fernet)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def stop(self) -> None:
        """Persist the current in-memory history to disk."""
        if self._history is not None and self._fernet is not None:
            _save_history(self._memory_path, self._fernet, self._history)

    def retain(self, content: str, context: str = "") -> None:
        """Append a fact to the memory store and immediately persist it."""
        if self._history is None or self._fernet is None:
            return
        try:
            text = f"[{context}] {content}" if context else content
            self._history.add_message(HumanMessage(content=text))
            _save_history(self._memory_path, self._fernet, self._history)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def recall(self, query: str = "") -> str:  # pylint: disable=unused-argument
        """Return the most recent retained facts as a plain-text string."""
        if self._history is None:
            return ""
        try:
            recent = self._history.messages[-MAX_RECALL_ENTRIES:]
            return "\n".join(
                msg.content if isinstance(msg.content, str) else str(msg.content)
                for msg in recent
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return ""
