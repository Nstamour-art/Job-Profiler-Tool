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

    with patch("src.tools.lookup._fetch_snippet", return_value="Acme is hiring. Responsibilities include ML."), \
         patch("src.tools.lookup._call_with_retry", return_value=mock_result):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "ML pipelines" in result
    assert "Acme" in result


def test_lookup_returns_error_when_snippet_is_none(sample_config):
    """When _fetch_snippet returns None, return a graceful error string."""
    with patch("src.tools.lookup._fetch_snippet", return_value=None):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "Could not fetch details" in result
    assert "https://example.com/job/1" in result


def test_lookup_returns_error_on_llm_failure(sample_config):
    """When _call_with_retry raises, return a graceful error string."""
    with patch("src.tools.lookup._fetch_snippet", return_value="Some page text."), \
         patch("src.tools.lookup._call_with_retry", side_effect=RuntimeError("LLM down")):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "https://example.com/job/1", "title": "ML Engineer", "company": "Acme"})

    assert "Could not summarize job details" in result
    assert "LLM down" in result


def test_lookup_returns_error_for_empty_url(sample_config):
    """Empty URL guard fires before any network call."""
    with patch("src.tools.lookup._fetch_snippet") as mock_fetch:
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        result = tool.invoke({"url": "", "title": "ML Engineer", "company": "Acme"})

    mock_fetch.assert_not_called()
    assert "No URL provided" in result


def test_lookup_wraps_snippet_in_delimiters(sample_config):
    """The prompt sent to the LLM must wrap the snippet in untrusted-content delimiters."""
    from src.models import JobSummary

    captured = {}

    def fake_retry(model_class, provider, llm_cfg, system, prompt, models):
        captured["prompt"] = prompt
        return JobSummary(summary="Summarised.")

    with patch("src.tools.lookup._fetch_snippet", return_value="raw page text here"), \
         patch("src.tools.lookup._call_with_retry", side_effect=fake_retry):
        from src.tools.lookup import create_lookup_tool
        tool = create_lookup_tool(sample_config, MagicMock(), ["parser-model"])
        tool.invoke({"url": "https://example.com/job/1", "title": "Engineer", "company": "Corp"})

    assert "--- BEGIN UNTRUSTED CONTENT ---" in captured["prompt"]
    assert "--- END UNTRUSTED CONTENT ---" in captured["prompt"]
    assert "raw page text here" in captured["prompt"]
