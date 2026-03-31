from unittest.mock import patch


def test_log_job_to_sheet_calls_append(sample_config):
    with patch("src.tools.sheet_log.append_job_row") as mock_append:
        from src.tools.sheet_log import create_sheet_log_tool
        log_tool = create_sheet_log_tool(sample_config)
        log_tool.invoke({
            "title": "AI Engineer",
            "company": "Acme Corp",
            "url": "https://example.com/job/1",
            "status": "Seen",
        })

    mock_append.assert_called_once()
    kwargs = mock_append.call_args[1]
    assert kwargs["title"] == "AI Engineer"
    assert kwargs["company"] == "Acme Corp"
    assert kwargs["status"] == "Seen"


def test_log_job_to_sheet_handles_sheet_error(sample_config):
    """Returns an error string instead of raising when the sheet is unavailable."""
    with patch("src.tools.sheet_log.append_job_row", side_effect=Exception("No credentials")):
        from src.tools.sheet_log import create_sheet_log_tool
        log_tool = create_sheet_log_tool(sample_config)
        result = log_tool.invoke({
            "title": "AI Engineer",
            "company": "Acme",
            "url": "https://example.com/job/1",
            "status": "Seen",
        })

    assert "Sheet logging unavailable" in result
