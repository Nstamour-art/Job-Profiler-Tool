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
