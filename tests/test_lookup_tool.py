# tests/test_lookup_tool.py
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# JobSummary model
# ---------------------------------------------------------------------------

def test_job_summary_model_accepts_string():
    from src.models import JobSummary
    result = JobSummary.model_validate({"summary": "This is a plain-English summary."})
    assert result.summary == "This is a plain-English summary."


# ---------------------------------------------------------------------------
# Prompt constant
# ---------------------------------------------------------------------------

def test_job_summary_system_prompt_exists_and_is_string():
    from src.prompts import JOB_SUMMARY_SYSTEM_PROMPT
    assert isinstance(JOB_SUMMARY_SYSTEM_PROMPT, str)
    assert len(JOB_SUMMARY_SYSTEM_PROMPT) > 50
    assert "summary" in JOB_SUMMARY_SYSTEM_PROMPT.lower()
    assert "UNTRUSTED" in JOB_SUMMARY_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# lookup_job_details tool behaviour
# ---------------------------------------------------------------------------

def test_lookup_returns_summary(sample_config):
    """Happy path — snippet fetched, LLM returns summary string."""
    from src.models import JobSummary

    mock_result = JobSummary(summary="This role involves building ML pipelines at Acme.")

    with patch("src.tools.lookup.fetch_page_snippet", return_value="Acme is hiring. Responsibilities include ML."), \
         patch("src.tools.lookup._call_with_retry", return_value=mock_result), \
         patch("src.tools.lookup.socket.gethostbyname", return_value="93.184.216.34"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "ML pipelines" in result
    assert "Acme" in result


def test_lookup_returns_error_when_snippet_is_none(sample_config):
    """When fetch_page_snippet returns None, return a graceful error string."""
    with patch("src.tools.lookup.fetch_page_snippet", return_value=None), \
         patch("src.tools.lookup.socket.gethostbyname", return_value="93.184.216.34"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "Could not fetch details" in result
    assert "https://example.com/job/1" in result


def test_lookup_returns_error_on_llm_failure(sample_config):
    """When _call_with_retry raises, return a graceful error string."""
    with patch("src.tools.lookup.fetch_page_snippet", return_value="Some page text."), \
         patch("src.tools.lookup._call_with_retry", side_effect=RuntimeError("LLM down")), \
         patch("src.tools.lookup.socket.gethostbyname", return_value="93.184.216.34"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "Could not summarize job details" in result
    assert "LLM down" in result


def test_lookup_returns_error_for_empty_url(sample_config):
    """Empty URL guard fires before any network call."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch:
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "", "title": "ML Engineer", "company": "Acme"})

    mock_fetch.assert_not_called()
    assert "No URL provided" in result


def test_lookup_returns_error_for_whitespace_only_url(sample_config):
    """Whitespace-only URL is treated as empty — no network call is made."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch:
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "   ", "title": "ML Engineer", "company": "Acme"})

    mock_fetch.assert_not_called()
    assert "No URL provided" in result


def test_lookup_rejects_non_http_scheme(sample_config):
    """Non-http(s) schemes (e.g. file://) must be rejected without fetching."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch:
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "file:///etc/passwd", "title": "Any", "company": "Corp"})

    mock_fetch.assert_not_called()
    assert "Invalid URL scheme" in result
    assert "file" in result


def test_lookup_rejects_ftp_scheme(sample_config):
    """FTP URLs must be rejected without fetching (only http/https are allowed)."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch:
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "ftp://example.com/job/1", "title": "Any", "company": "Corp"})

    mock_fetch.assert_not_called()
    assert "Invalid URL scheme" in result


def test_lookup_rejects_loopback_ip(sample_config):
    """Requests to loopback addresses (127.x.x.x) must be blocked."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch, \
         patch("src.tools.lookup.socket.gethostbyname", return_value="127.0.0.1"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "http://127.0.0.1/secret", "title": "Any", "company": "Corp"})

    mock_fetch.assert_not_called()
    assert "not allowed" in result


def test_lookup_rejects_private_ip(sample_config):
    """Requests to private IP ranges (e.g. 192.168.x.x) must be blocked."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch, \
         patch("src.tools.lookup.socket.gethostbyname", return_value="192.168.1.100"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "http://192.168.1.100/admin", "title": "Any", "company": "Corp"})

    mock_fetch.assert_not_called()
    assert "not allowed" in result


def test_lookup_rejects_link_local_ip(sample_config):
    """Requests to link-local addresses (169.254.x.x, e.g. AWS metadata) must be blocked."""
    with patch("src.tools.lookup.fetch_page_snippet") as mock_fetch, \
         patch("src.tools.lookup.socket.gethostbyname", return_value="169.254.169.254"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "http://169.254.169.254/latest/meta-data/", "title": "Any", "company": "Corp"})

    mock_fetch.assert_not_called()
    assert "not allowed" in result


def test_lookup_wraps_snippet_in_delimiters(sample_config):
    """The prompt sent to the LLM must wrap the snippet in untrusted-content delimiters."""
    from src.models import JobSummary

    captured = {}

    def fake_retry(model_class, provider, llm_cfg, system, prompt, models):
        captured["prompt"] = prompt
        return JobSummary(summary="Summarised.")

    with patch("src.tools.lookup.fetch_page_snippet", return_value="raw page text here"), \
         patch("src.tools.lookup._call_with_retry", side_effect=fake_retry), \
         patch("src.tools.lookup.socket.gethostbyname", return_value="93.184.216.34"):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        tool.invoke({"url": "https://example.com/job/1", "title": "Engineer", "company": "Corp"})

    assert "--- BEGIN UNTRUSTED CONTENT ---" in captured["prompt"]
    assert "--- END UNTRUSTED CONTENT ---" in captured["prompt"]
    assert "raw page text here" in captured["prompt"]


# ---------------------------------------------------------------------------
# Agent wiring
# ---------------------------------------------------------------------------

def test_agent_includes_lookup_tool():
    """build_agent must wire lookup_job_details into the tool list."""
    import os

    config = {
        "provider": "local",
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "llama3.2:latest",
                "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": "resume.yaml", "template_yaml": "template.yaml",
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    resume = {"basics": {"name": "Test User", "location": "Remote"}}

    with patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.create_deep_agent") as mock_create, \
         patch("src.agent.create_search_tool", return_value=MagicMock(name="search_jobs")), \
         patch("src.agent.create_generate_batch_tool", return_value=MagicMock(name="generate_batch")), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_suggest_roles_tool", return_value=MagicMock(name="suggest_roles")), \
         patch("src.agent.create_lookup_tool", return_value=MagicMock(name="lookup_job_details")) as mock_lookup, \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test"}):
        from src.agent import build_agent
        build_agent(config, resume, "local", "")

    mock_create.assert_called_once()
    tools_passed = mock_create.call_args.kwargs["tools"]
    assert mock_lookup.return_value in tools_passed
