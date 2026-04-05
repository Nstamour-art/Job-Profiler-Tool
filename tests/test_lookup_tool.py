# tests/test_lookup_tool.py
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# JobSummary model
# ---------------------------------------------------------------------------

def test_job_summary_model_accepts_string():
    from src.models import JobSummary
    result = JobSummary.model_validate({"summary": "This is a plain-English summary."})
    assert result.summary == "This is a plain-English summary."
