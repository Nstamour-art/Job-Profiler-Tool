import gspread
from unittest.mock import MagicMock, patch


def _make_mock_sheet(headers, existing_rows=None):
    """existing_rows: list of row-lists (not including header), or None for empty sheet."""
    sheet = MagicMock()
    sheet.row_values.return_value = headers
    all_values = [headers] + (existing_rows or [])
    sheet.get_all_values.return_value = all_values
    return sheet


def test_upsert_job_row_inserts_when_no_match(sample_config):
    """When no existing row matches, a new row is appended."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Seen",
                date_found="2026-04-02",
            ),
        )

    mock_sheet.append_row.assert_called_once()
    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "AI Engineer"
    assert appended[headers.index("Company")] == "Acme Corp"
    assert appended[headers.index("URL")] == "https://example.com/job/1"
    assert appended[headers.index("Status")] == "Seen"


def test_upsert_job_row_updates_existing_by_url(sample_config):
    """When a row with matching URL exists, it is updated, not appended."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    existing = [["AI Engineer", "Acme Corp", "https://example.com/job/1", "Seen", "2026-04-01", "", "", ""]]
    mock_sheet = _make_mock_sheet(headers, existing)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Generated",
                date_found="2026-04-02",
                priority="2",
                reasoning="Strong match.",
            ),
        )

    mock_sheet.append_row.assert_not_called()
    mock_sheet.batch_update.assert_called_once()


def test_upsert_job_row_updates_existing_by_company_and_title(sample_config):
    """When company + title match but URL differs, the existing row is updated."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    existing = [["AI Engineer", "Acme Corp", "https://old-url.com/job/99", "Seen", "2026-04-01", "", "", ""]]
    mock_sheet = _make_mock_sheet(headers, existing)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://new-url.com/job/1",
                status="Generated",
                date_found="2026-04-02",
            ),
        )

    mock_sheet.append_row.assert_not_called()
    mock_sheet.batch_update.assert_called_once()


def test_upsert_job_row_skips_missing_columns(sample_config):
    """Columns not present in the sheet are skipped gracefully."""
    headers = ["Title", "URL", "Status"]
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="ML Engineer",
                company="Stripe",
                url="https://example.com/job/2",
                status="Seen",
                date_found="2026-04-02",
            ),
        )

    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "ML Engineer"
    assert appended[headers.index("URL")] == "https://example.com/job/2"


def test_upsert_job_row_does_not_overwrite_date_found(sample_config):
    """When updating an existing row, date_found should not be changed."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    existing = [["AI Engineer", "Acme Corp", "https://example.com/job/1", "Seen", "2026-04-01", "", "", ""]]
    mock_sheet = _make_mock_sheet(headers, existing)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Generated",
                date_found="2026-04-03",  # different date — should NOT overwrite
                priority="2",
                reasoning="Strong match.",
            ),
        )

    mock_sheet.append_row.assert_not_called()
    mock_sheet.batch_update.assert_called_once()
    # Verify date_found cell was NOT included in the batch_update
    update_ranges = [u["range"] for u in mock_sheet.batch_update.call_args[0][0]]
    date_col_index = headers.index("Date Found") + 1
    date_cell = gspread.utils.rowcol_to_a1(2, date_col_index)
    assert date_cell not in update_ranges


def test_upsert_job_row_url_match_takes_priority_over_company_title(sample_config):
    """When both a URL match and a company+title match exist in different rows, URL match wins."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    existing = [
        # Row 2: company+title match, different URL
        ["AI Engineer", "Acme Corp", "https://old-url.com/job/99", "Seen", "2026-04-01", "", "", ""],
        # Row 3: URL match, different title
        ["Different Title", "Acme Corp", "https://example.com/job/1", "Seen", "2026-04-01", "", "", ""],
    ]
    mock_sheet = _make_mock_sheet(headers, existing)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Generated",
                date_found="2026-04-02",
            ),
        )

    mock_sheet.append_row.assert_not_called()
    mock_sheet.batch_update.assert_called_once()
    # The batch_update should target row 3 (URL match), not row 2 (company+title match)
    update_ranges = [u["range"] for u in mock_sheet.batch_update.call_args[0][0]]
    assert all(r.endswith("3") for r in update_ranges)


def test_upsert_job_row_handles_empty_sheet(sample_config):
    """An empty sheet (header only, no data rows) should result in a new row being appended."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    mock_sheet = _make_mock_sheet(headers, existing_rows=[])  # no data rows

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Seen",
                date_found="2026-04-02",
            ),
        )

    mock_sheet.append_row.assert_called_once()
    mock_sheet.batch_update.assert_not_called()


def test_upsert_seen_does_not_overwrite_existing_generated_row(sample_config):
    """A Seen upsert must not downgrade a pre-existing Generated row or clear its fields."""
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    existing = [
        ["AI Engineer", "Acme Corp", "https://example.com/job/1", "Generated", "2026-04-01", "desc", "8", "Strong match."]
    ]
    mock_sheet = _make_mock_sheet(headers, existing)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import upsert_job_row
        from src.models import JobRow
        upsert_job_row(
            config=sample_config,
            job_row=JobRow(
                title="AI Engineer",
                company="Acme Corp",
                url="https://example.com/job/1",
                status="Seen",
                date_found="2026-04-03",
            ),
        )

    # Row already exists — Seen upsert must not write anything
    mock_sheet.batch_update.assert_not_called()
    mock_sheet.append_row.assert_not_called()
