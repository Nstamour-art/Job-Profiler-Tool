from unittest.mock import MagicMock, patch


def test_memory_manager_retain_and_recall(sample_config, sample_resume):
    mock_client = MagicMock()
    mock_client.recall.return_value = "User prefers remote roles above $130k."

    with patch("src.memory.Hindsight", return_value=mock_client), \
         patch.dict("os.environ", {"HINDSIGHT_BASE_URL": "http://localhost:8888"}):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("User prefers remote roles above $130k.", context="preferences")
        result = mgr.recall("What are the user's job preferences?")
        mgr.stop()

    mock_client.retain.assert_called_once_with(
        bank_id="Jane Doe",
        content="User prefers remote roles above $130k.",
        context="preferences",
    )
    assert result == "User prefers remote roles above $130k."


def test_memory_manager_uses_resume_name_as_bank_id(sample_config, sample_resume):
    mock_client = MagicMock()

    with patch("src.memory.Hindsight", return_value=mock_client), \
         patch.dict("os.environ", {"HINDSIGHT_BASE_URL": "http://localhost:8888"}):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("some fact")
        mgr.stop()

    call_kwargs = mock_client.retain.call_args[1]
    assert call_kwargs["bank_id"] == "Jane Doe"


def test_memory_manager_is_silent_when_no_url(sample_config, sample_resume):
    """If HINDSIGHT_BASE_URL is not set, MemoryManager does nothing silently."""
    with patch.dict("os.environ", {}, clear=True):
        # Remove the key entirely if present
        import os
        os.environ.pop("HINDSIGHT_BASE_URL", None)

        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        result = mgr.recall("anything")
        mgr.retain("anything")
        mgr.stop()

    assert result == ""  # empty string when memory is unavailable
