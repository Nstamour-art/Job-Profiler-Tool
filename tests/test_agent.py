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
