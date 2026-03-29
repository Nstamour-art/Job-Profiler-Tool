from unittest.mock import MagicMock, patch
import pytest


def test_build_agent_returns_compiled_graph(sample_config, sample_resume):
    """build_agent returns a compiled graph without making any API calls."""
    fake_graph = MagicMock()

    with patch("src.agent.create_deep_agent", return_value=fake_graph), \
         patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.get_provider", return_value=MagicMock()), \
         patch("src.agent.create_search_tool", return_value=MagicMock()), \
         patch("src.agent.create_generate_tool", return_value=MagicMock()), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_sheet_log_tool", return_value=MagicMock()):
        from src.agent import build_agent
        agent = build_agent(
            config=sample_config,
            resume=sample_resume,
            provider_name="anthropic",
            recalled_memories="No prior sessions.",
        )

    assert agent is fake_graph


def test_build_agent_system_prompt_includes_candidate_name(sample_config, sample_resume):
    """The system prompt injected into the agent includes the candidate's name."""
    captured = {}

    def fake_create(model, tools, system_prompt):
        captured["prompt"] = system_prompt
        return MagicMock()

    with patch("src.agent.create_deep_agent", side_effect=fake_create), \
         patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.get_provider", return_value=MagicMock()), \
         patch("src.agent.create_search_tool", return_value=MagicMock()), \
         patch("src.agent.create_generate_tool", return_value=MagicMock()), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_sheet_log_tool", return_value=MagicMock()):
        from src.agent import build_agent
        build_agent(
            config=sample_config,
            resume=sample_resume,
            provider_name="anthropic",
            recalled_memories="",
        )

    assert "Jane Doe" in captured["prompt"]


def test_run_agent_chat_calls_onboarding_when_resume_missing(tmp_path, sample_config, sample_resume):
    """run_agent_chat triggers run_onboarding when resume.yaml does not exist."""
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")
    # File does NOT exist — tmp_path / "resume.yaml" is not created

    with patch("src.agent.run_onboarding", return_value=sample_resume) as mock_onboard, \
         patch("src.agent.MemoryManager") as mock_mm, \
         patch("src.agent.build_agent", return_value=MagicMock()), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        mock_mm.return_value.recall.return_value = ""
        mock_mm.return_value.start.return_value = None
        mock_mm.return_value.stop.return_value = None
        from src.agent import run_agent_chat
        run_agent_chat(config=sample_config, provider_name="local")

    mock_onboard.assert_called_once_with(sample_config, "local")


def test_run_agent_chat_loads_resume_from_disk_when_exists(tmp_path, sample_config, sample_resume):
    """run_agent_chat reads resume.yaml from disk when the file exists."""
    import yaml as _yaml
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(_yaml.dump(sample_resume), encoding="utf-8")
    sample_config["paths"]["resume_yaml"] = str(resume_path)

    with patch("src.agent.run_onboarding") as mock_onboard, \
         patch("src.agent.MemoryManager") as mock_mm, \
         patch("src.agent.build_agent", return_value=MagicMock()), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        mock_mm.return_value.recall.return_value = ""
        mock_mm.return_value.start.return_value = None
        mock_mm.return_value.stop.return_value = None
        from src.agent import run_agent_chat
        run_agent_chat(config=sample_config, provider_name="local")

    mock_onboard.assert_not_called()
