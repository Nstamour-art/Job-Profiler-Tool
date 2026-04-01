---
goal: Replace Hindsight with LangChain + Fernet-encrypted persistent memory
version: 1.0
date_created: 2026-04-01
owner: Nstamour-art
status: 'Planned'
tags: [refactor, memory, security, langchain, migration]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Replace the Hindsight third-party memory backend with a self-contained LangChain-based
`MemoryManager` that persists cross-session facts to a Fernet-encrypted JSON file on disk.
The public interface of `MemoryManager` (`start`, `stop`, `retain`, `recall`) is preserved
so `src/agent.py` requires only minimal changes. The `cryptography` package (already a
transitive dependency of many LangChain packages) is the only new direct dependency.

---

## 1. Requirements & Constraints

- **REQ-001**: `MemoryManager` must maintain the same public interface: `__init__(config, resume, provider_name)`, `start()`, `stop()`, `retain(content, context="")`, `recall(query) -> str`.
- **REQ-002**: Cross-session memory must be persisted to disk between runs.
- **REQ-003**: Persisted memory file must be encrypted at rest using `cryptography.Fernet` (AES-128-CBC + HMAC-SHA256).
- **REQ-004**: The Fernet key must be stored in `~/.job-profiler/.key` with file mode `0o600` (owner read/write only). The storage directory must be created with mode `0o700`.
- **REQ-005**: Memory files must be stored in `~/.job-profiler/<bank_id>.enc`, separate from the project repo so they are never committed to git.
- **REQ-006**: `recall(query)` must return the most recent retained entries as a plain-text string (last `MAX_RECALL_ENTRIES = 30`). The `query` parameter is kept for interface compatibility.
- **REQ-007**: All operations must silently no-op on any error so the agent always starts.
- **SEC-001**: The `.key` file must never be committed to git. Verify `.gitignore` does not explicitly track `~/.job-profiler/`.
- **SEC-002**: Do NOT use `pickle` for serialization — JSON only (inert, no code execution on load).
- **CON-001**: `provider_name` parameter of `__init__` is kept for interface compatibility but is no longer used internally (no LLM needed for memory extraction).
- **CON-002**: The `memory_model` config key under `agent:` is obsolete and must be removed from `config.yaml` and `example_config.yaml`.
- **CON-003**: `hindsight-all-slim` must be removed from `pyproject.toml` dependencies.
- **GUD-001**: Use `langchain_core.chat_history.InMemoryChatMessageHistory` as the in-session backing store; serialize with `langchain.schema.messages_to_dict` / `messages_from_dict`.
- **GUD-002**: Each retained fact is stored as a `HumanMessage` with `content = f"[{context}] {content}"` so context is embedded and recoverable.
- **PAT-001**: Follow the existing `src/memory.py` graceful-degradation pattern — wrap all I/O in `try/except` and fall back to no-op.

---

## 2. Implementation Steps

### Phase 1 — Dependencies

- GOAL-001: Swap `hindsight-all-slim` for `cryptography` in `pyproject.toml`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `pyproject.toml`: remove `"hindsight-all-slim>=0.1.7"` from `dependencies`. | | |
| TASK-002 | In `pyproject.toml`: add `"cryptography>=42.0.0"` to `dependencies`. | | |
| TASK-003 | Run `uv sync` to update lockfile and virtual environment. | | |

### Phase 2 — Rewrite `src/memory.py`

- GOAL-002: Replace the full contents of `src/memory.py` with the new LangChain + Fernet implementation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Remove all Hindsight imports (`hindsight_embed`, `hindsight_client`) and the `_EMBEDDED_AVAILABLE` / `_CLIENT_AVAILABLE` flags, `_HINDSIGHT_PROVIDER`, `_API_KEY_ENV`, `_resolve_memory_model` helper, and the existing `MemoryManager` class body. | | |
| TASK-005 | Add imports: `import json`, `import os`, `import stat`, `from datetime import datetime, timezone`, `from pathlib import Path`, `from cryptography.fernet import Fernet`, `from langchain.schema import HumanMessage, messages_to_dict, messages_from_dict`, `from langchain_core.chat_history import InMemoryChatMessageHistory`. | | |
| TASK-006 | Add module-level constants: `_MEMORY_DIR = Path.home() / ".job-profiler"`, `_KEY_FILE = _MEMORY_DIR / ".key"`, `MAX_RECALL_ENTRIES = 30`. | | |
| TASK-007 | Implement `_resolve_bank_id(config, resume) -> str` — identical logic to current: returns `config["agent"]["memory_bank"].strip() or resume["basics"]["name"]`. | | |
| TASK-008 | Implement `_get_or_create_key() -> bytes`: creates `_MEMORY_DIR` with `mode=0o700` if absent; if `_KEY_FILE` exists reads and returns it; otherwise generates `Fernet.generate_key()`, writes it, sets file mode to `0o600` via `os.chmod`, returns the key. Wrap entirely in `try/except Exception` returning `None` on failure. | | |
| TASK-009 | Implement `_load_history(path: Path, fernet: Fernet) -> InMemoryChatMessageHistory`: opens encrypted file, decrypts bytes, JSON-parses, calls `messages_from_dict()`, populates and returns a new `InMemoryChatMessageHistory`. Returns empty history on any error. | | |
| TASK-010 | Implement `_save_history(path: Path, fernet: Fernet, history: InMemoryChatMessageHistory) -> None`: serializes via `messages_to_dict(history.messages)`, JSON-encodes to bytes, encrypts with `fernet.encrypt()`, writes to `path`. Silently swallows exceptions. | | |
| TASK-011 | Rewrite `MemoryManager.__init__`: stores `self._bank_id`, `self._memory_path = _MEMORY_DIR / f"{self._bank_id}.enc"`, `self._fernet = None`, `self._history = None`. The `provider_name` parameter is accepted but not stored. | | |
| TASK-012 | Implement `MemoryManager.start()`: calls `_get_or_create_key()`; if key is `None` returns early (no-op); creates `Fernet(key)` and stores in `self._fernet`; calls `_load_history(self._memory_path, self._fernet)` and stores in `self._history`. | | |
| TASK-013 | Implement `MemoryManager.stop()`: if `self._history` and `self._fernet` are set, calls `_save_history(self._memory_path, self._fernet, self._history)`. | | |
| TASK-014 | Implement `MemoryManager.retain(content, context="")`: if `self._history` is `None`, returns early. Constructs `msg = HumanMessage(content=f"[{context}] {content}" if context else content)`. Calls `self._history.add_message(msg)`. Calls `_save_history(...)` immediately to persist after each retain. Wraps in `try/except`. | | |
| TASK-015 | Implement `MemoryManager.recall(query) -> str`: if `self._history` is `None`, returns `""`. Takes the last `MAX_RECALL_ENTRIES` messages from `self._history.messages`. Returns `"\n".join(msg.content for msg in recent_messages)`. The `query` param is unused. Wraps in `try/except` returning `""`. | | |

### Phase 3 — Update `src/agent.py`

- GOAL-003: Remove the two separate `recall()` calls and merge into one; update docstring.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | In `run_agent_chat()`, replace the two separate `memory.recall()` calls (lines ~112-114) with a single call: `recalled_memories = memory.recall("")`. The `query` argument is kept as empty string since the new implementation returns recent entries regardless. | | |
| TASK-017 | Update the module docstring in `src/agent.py` (lines 1-6): remove reference to "Hindsight memory", replace with "LangChain persistent memory". | | |

### Phase 4 — Update configuration files

- GOAL-004: Remove obsolete `memory_model` key from config files.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | In `config.yaml`: remove the `memory_model: ''` line under `agent:`. | | |
| TASK-019 | In `example_config.yaml`: remove the `memory_model: ''` line under `agent:` if present. | | |

### Phase 5 — Rewrite `tests/test_memory.py`

- GOAL-005: Replace Hindsight-patching tests with tests for the new encrypted-file implementation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-020 | Remove all existing tests that patch `src.memory.Hindsight` or `HINDSIGHT_BASE_URL`. | | |
| TASK-021 | Add `test_retain_and_recall_roundtrip(tmp_path, sample_config, sample_resume)`: patches `_MEMORY_DIR` to `tmp_path`; calls `start()`, `retain("User prefers remote", context="preferences")`, `recall("")`; asserts the returned string contains `"User prefers remote"`. | | |
| TASK-022 | Add `test_memory_persists_across_instances(tmp_path, sample_config, sample_resume)`: creates first `MemoryManager`, starts, retains a fact, stops; creates a second `MemoryManager` with same config, starts, calls `recall("")`; asserts the fact appears in the result. | | |
| TASK-023 | Add `test_memory_is_silent_when_key_creation_fails(tmp_path, sample_config, sample_resume)`: patches `_get_or_create_key` to return `None`; calls `start()`, `retain("anything")`, `recall("anything")`; asserts `recall` returns `""` and no exception is raised. | | |
| TASK-024 | Add `test_recall_returns_last_n_entries(tmp_path, sample_config, sample_resume)`: retains 35 entries; asserts `recall("")` returns at most `MAX_RECALL_ENTRIES` (30) entries (count newlines). | | |
| TASK-025 | Update `conftest.py` `sample_config` fixture: remove `memory_model` key from `agent` sub-dict. | | |

---

## 3. Alternatives

- **ALT-001**: **SQLite via `SQLChatMessageHistory`** — Built into `langchain_community`. Binary format, not plaintext readable. Rejected because it adds a process-level lock and SQLite is not encrypted; would still require a second library for encryption. Net complexity is higher than the JSON+Fernet approach.
- **ALT-002**: **Pickle** — Rejected due to CWE-502: arbitrary code execution on deserialization of a tampered file. JSON is inert.
- **ALT-003**: **Hindsight external server** — Requires a running Docker container or separate process. Rejected because it adds operational overhead and is the dependency being removed.
- **ALT-004**: **Hybrid summarization memory** (`HybridChatMessageHistory` with an LLM summarizer) — Adds LLM API calls on every retain, increases latency and cost. The simple recency-windowed approach (`MAX_RECALL_ENTRIES`) is sufficient for the cross-session use case here.
- **ALT-005**: **Store key in environment variable** — Less convenient for local development; users would need to export `MEMORY_KEY` every session. A file-based key at `~/.job-profiler/.key` is more ergonomic and uses filesystem permissions for access control.

---

## 4. Dependencies

- **DEP-001**: `cryptography>=42.0.0` — Provides `Fernet` (AES-128-CBC + HMAC-SHA256). Already a transitive dependency of many langchain packages; adding as a direct dependency pins the minimum version.
- **DEP-002**: `langchain-core>=0.2.0` — Provides `InMemoryChatMessageHistory`. Already in `pyproject.toml`.
- **DEP-003**: `langchain>=0.2.0` — Provides `messages_to_dict`, `messages_from_dict`, `HumanMessage`. Already in `pyproject.toml`.

---

## 5. Files

- **FILE-001**: `src/memory.py` — Full rewrite. ~120 lines → ~120 lines (same size, different implementation).
- **FILE-002**: `src/agent.py` — Minor edits to docstring and the two `recall()` calls (lines ~6, ~112-114).
- **FILE-003**: `pyproject.toml` — Remove `hindsight-all-slim`, add `cryptography>=42.0.0`.
- **FILE-004**: `config.yaml` — Remove `memory_model: ''` under `agent:`.
- **FILE-005**: `example_config.yaml` — Remove `memory_model: ''` under `agent:` if present.
- **FILE-006**: `tests/test_memory.py` — Full rewrite of all test cases.
- **FILE-007**: `tests/conftest.py` — Remove `memory_model` from `sample_config` fixture.

---

## 6. Testing

- **TEST-001**: `test_retain_and_recall_roundtrip` — Verifies basic retain→recall within one session works.
- **TEST-002**: `test_memory_persists_across_instances` — Verifies encrypted file survives `stop()` and is readable by a new `MemoryManager` instance (cross-session persistence).
- **TEST-003**: `test_memory_is_silent_when_key_creation_fails` — Verifies graceful degradation when the key file cannot be created (e.g. read-only filesystem).
- **TEST-004**: `test_recall_returns_last_n_entries` — Verifies the `MAX_RECALL_ENTRIES` cap is enforced.

---

## 7. Risks & Assumptions

- **RISK-001**: If a user already has Hindsight memory stored from a previous session, that data will not be migrated. Cross-session memory will restart fresh after this change.
- **RISK-002**: If the `~/.job-profiler/.key` file is deleted or corrupted, previously encrypted memory files become unreadable. The implementation handles this gracefully (starts with empty history), but past memories are lost.
- **RISK-003**: On some Windows configurations, `os.chmod(..., 0o600)` is a no-op (Windows ACLs are separate from POSIX modes). Risk is low since this is a local developer tool, but users on shared Windows machines should be aware.
- **ASSUMPTION-001**: `langchain.schema.messages_to_dict` and `messages_from_dict` are stable across `langchain>=0.2.0`. These are core serialization primitives unlikely to change.
- **ASSUMPTION-002**: `recall()` does not need semantic search — returning the most recent `MAX_RECALL_ENTRIES` retained facts is sufficient context for the agent's system prompt. The current Hindsight `recall()` was called with only two broad queries anyway.

---

## 8. Related Specifications / Further Reading

- [LangChain InMemoryChatMessageHistory](https://python.langchain.com/docs/concepts/chat_history/)
- [cryptography Fernet spec](https://cryptography.io/en/latest/fernet/)
- [CWE-502: Deserialization of Untrusted Data](https://cwe.mitre.org/data/definitions/502.html)
