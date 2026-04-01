from unittest.mock import patch

from src.memory import MAX_RECALL_ENTRIES


def test_retain_and_recall_roundtrip(tmp_path, sample_config, sample_resume):
    """Facts retained in a session are returned by recall() in the same session."""
    with patch("src.memory._MEMORY_DIR", tmp_path), \
         patch("src.memory._KEY_FILE", tmp_path / ".key"):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("User prefers remote roles above $130k.", context="preferences")
        result = mgr.recall()
        mgr.stop()

    assert "User prefers remote roles above $130k." in result


def test_memory_persists_across_instances(tmp_path, sample_config, sample_resume):
    """Facts written by one MemoryManager are readable by a second instance."""
    with patch("src.memory._MEMORY_DIR", tmp_path), \
         patch("src.memory._KEY_FILE", tmp_path / ".key"):
        from src.memory import MemoryManager

        mgr1 = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr1.start()
        mgr1.retain("User wants ML engineer roles.", context="preferences")
        mgr1.stop()

        mgr2 = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr2.start()
        result = mgr2.recall()
        mgr2.stop()

    assert "User wants ML engineer roles." in result


def test_memory_is_silent_when_key_creation_fails(sample_config, sample_resume):
    """If the key file cannot be created, MemoryManager silently no-ops."""
    with patch("src.memory._get_or_create_key", return_value=None):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("anything")
        result = mgr.recall()
        mgr.stop()

    assert result == ""


def test_recall_returns_last_n_entries(tmp_path, sample_config, sample_resume):
    """recall() returns at most MAX_RECALL_ENTRIES entries."""
    with patch("src.memory._MEMORY_DIR", tmp_path), \
         patch("src.memory._KEY_FILE", tmp_path / ".key"):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        for i in range(MAX_RECALL_ENTRIES + 5):
            mgr.retain(f"fact {i}")
        result = mgr.recall()
        mgr.stop()

    # Count entries by searching for the known "fact N" token prefix, not raw newlines,
    # to avoid false failures from embedded newlines inside a single retained entry.
    entry_count = sum(1 for line in result.splitlines() if line.strip().startswith("fact "))
    assert entry_count <= MAX_RECALL_ENTRIES


def test_memory_uses_resume_name_as_bank_id(sample_config, sample_resume):
    """Bank ID defaults to sanitized resume basics.name when memory_bank config is empty."""
    from src.memory import MemoryManager
    mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
    assert mgr._bank_id == "Jane_Doe"  # noqa: SLF001


def test_memory_path_computed_from_memory_dir(tmp_path, sample_config, sample_resume):
    """_memory_path is built from _MEMORY_DIR and the sanitized bank_id — no manual override."""
    with patch("src.memory._MEMORY_DIR", tmp_path), \
         patch("src.memory._KEY_FILE", tmp_path / ".key"):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")

    assert mgr._memory_path == tmp_path / f"{mgr._bank_id}.enc"  # noqa: SLF001


def test_bank_id_sanitization_prevents_path_traversal(sample_config):
    """Special characters in bank_id (e.g., path separators) are replaced, not preserved."""
    from src.memory import MemoryManager
    resume_with_special_chars = {"basics": {"name": "Jane/Doe..Evil"}}
    mgr = MemoryManager(config=sample_config, resume=resume_with_special_chars, provider_name="anthropic")
    assert "/" not in mgr._bank_id  # noqa: SLF001
    assert ".." not in mgr._bank_id  # noqa: SLF001
    assert mgr._bank_id == "Jane_Doe__Evil"  # noqa: SLF001
