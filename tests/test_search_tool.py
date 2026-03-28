from unittest.mock import MagicMock, patch
import json
import pytest


def test_search_tool_returns_job_list():
    fake_jobs = {"jobs": [
        {"title": "AI Engineer", "company": "Acme", "url": "https://example.com/1",
         "location": "Remote", "salary": "$130k"},
    ]}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {
        "messages": [MagicMock(content=json.dumps(fake_jobs))]
    }

    with patch("src.tools.search.create_deep_agent", return_value=fake_agent):
        from src.tools.search import create_search_tool
        search_tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="test-key",
            max_jobs=10,
        )
        result = search_tool.invoke({"preferences_summary": "AI Engineer, Remote, $130k+"})

    assert "AI Engineer" in result
    assert "Acme" in result


def test_search_tool_handles_agent_error():
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = Exception("Tavily timeout")

    with patch("src.tools.search.create_deep_agent", return_value=fake_agent):
        from src.tools.search import create_search_tool
        search_tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="test-key",
            max_jobs=10,
        )
        result = search_tool.invoke({"preferences_summary": "AI Engineer"})

    assert "Search failed" in result
