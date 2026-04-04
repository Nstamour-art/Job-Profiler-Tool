from unittest.mock import MagicMock, patch
import json


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


def test_search_jobs_calls_validate_job_links(sample_config):
    """After sub-agent returns results, validate_job_links is called."""
    jobs_payload = json.dumps({"jobs": [
        {"url": "https://example.com/job/1", "title": "AI Eng", "company": "Acme", "location": "Remote", "salary": ""},
    ]})
    mock_sub_result = {"messages": [MagicMock(content=jobs_payload)]}

    with patch("src.tools.search.create_deep_agent") as mock_agent_cls, \
         patch("src.tools.search.validate_job_links", return_value=[
             {"url": "https://example.com/job/1", "title": "AI Eng", "company": "Acme"}
         ]) as mock_validate, \
         patch("src.tools.search.bulk_upsert_job_rows"):
        mock_agent_cls.return_value.invoke.return_value = mock_sub_result
        from src.tools.search import create_search_tool
        tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="key",
            max_jobs=10,
            parser_model=MagicMock(),
            config=sample_config,
            provider=MagicMock(),
            parser_models=["model"],
        )
        tool.invoke({"preferences_summary": "Backend engineer in Toronto"})

    mock_validate.assert_called_once()


def test_search_jobs_logs_seen_for_each_valid_job(sample_config):
    """Each validated job is logged to Sheets as Seen."""
    jobs = [
        {"url": f"https://example.com/job/{i}", "title": "Eng", "company": "Co", "location": "", "salary": ""}
        for i in range(3)
    ]
    jobs_payload = json.dumps({"jobs": jobs})
    mock_sub_result = {"messages": [MagicMock(content=jobs_payload)]}

    with patch("src.tools.search.create_deep_agent") as mock_agent_cls, \
         patch("src.tools.search.validate_job_links", return_value=jobs), \
         patch("src.tools.search.bulk_upsert_job_rows") as mock_upsert:
        mock_agent_cls.return_value.invoke.return_value = mock_sub_result
        from src.tools.search import create_search_tool
        tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="key",
            max_jobs=10,
            config=sample_config,
            provider=MagicMock(),
            parser_models=["model"],
        )
        tool.invoke({"preferences_summary": "Backend engineer"})

    mock_upsert.assert_called_once()
    assert len(mock_upsert.call_args.kwargs["job_rows"]) == 3


def test_search_jobs_fetches_max_jobs_plus_buffer(sample_config):
    """The sub-agent system prompt should request max_jobs + search_buffer results."""
    captured_prompt = {}

    def fake_create_agent(model, tools, system_prompt):
        captured_prompt["value"] = system_prompt
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content='{"jobs": []}')]}
        return agent

    with patch("src.tools.search.create_deep_agent", side_effect=fake_create_agent), \
         patch("src.tools.search.validate_job_links", return_value=[]), \
         patch("src.tools.search.bulk_upsert_job_rows"):
        from src.tools.search import create_search_tool
        tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="key",
            max_jobs=10,         # search_buffer=5 from sample_config → expect 15
            config=sample_config,
            provider=MagicMock(),
            parser_models=["model"],
        )
        tool.invoke({"preferences_summary": "Engineer"})

    assert "15" in captured_prompt["value"]
