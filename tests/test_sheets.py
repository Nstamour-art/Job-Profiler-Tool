from unittest.mock import MagicMock, patch
import pytest


def _make_mock_sheet(headers):
    sheet = MagicMock()
    sheet.row_values.return_value = headers
    return sheet


def test_append_job_row_calls_append_row(sample_config):
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import append_job_row
        append_job_row(
            config=sample_config,
            title="AI Engineer",
            company="Acme Corp",
            url="https://example.com/job/1",
            status="Seen",
            date_found="2026-03-27",
        )

    mock_sheet.append_row.assert_called_once()
    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "AI Engineer"
    assert appended[headers.index("Company")] == "Acme Corp"
    assert appended[headers.index("URL")] == "https://example.com/job/1"
    assert appended[headers.index("Status")] == "Seen"
    assert appended[headers.index("Date Found")] == "2026-03-27"


def test_append_job_row_skips_missing_columns(sample_config):
    """If a column like 'Company' isn't in the sheet yet, skip it gracefully."""
    headers = ["Title", "URL", "Status"]  # no Company or Date Found column
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import append_job_row
        append_job_row(
            config=sample_config,
            title="ML Engineer",
            company="Stripe",
            url="https://example.com/job/2",
            status="Seen",
            date_found="2026-03-27",
        )

    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "ML Engineer"
    assert appended[headers.index("URL")] == "https://example.com/job/2"
