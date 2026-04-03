"""Google Sheets integration — read jobs and append/update rows."""

import gspread
from google.oauth2.service_account import Credentials


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import JobRow


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _open_sheet(config: dict):
    creds = Credentials.from_service_account_file(
        config["paths"]["credentials"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet_cfg = config["google_sheets"]
    spreadsheet = client.open_by_key(sheet_cfg["spreadsheet_id"])
    return spreadsheet.worksheet(sheet_cfg["worksheet_name"])


def get_jobs(config: dict) -> list[dict]:
    """Return all rows from the sheet as a list of dicts (1-indexed row numbers included)."""
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    records = sheet.get_all_records()
    jobs = []
    for i, row in enumerate(records, start=2):  # row 1 is header
        jobs.append({
            "row": i,
            "job_title": row.get(cols["job_title"], ""),
            "url": row.get(cols["url"], ""),
            "status": row.get(cols["status"], ""),
            "details": row.get(cols["details"], ""),
        })
    return jobs


def update_row(config: dict, row: int, **fields) -> None:
    """Write multiple column values for a row in a single sheet request.

    Keyword arguments must match keys in config.google_sheets.columns, e.g.:
        update_row(config, 3, status="Generated", priority=8, details="...")
    """
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)
    updates = []
    for field, value in fields.items():
        col_name = cols.get(field)
        if not col_name:
            continue
        try:
            col_index = headers.index(col_name) + 1
        except ValueError:
            continue
        cell = gspread.utils.rowcol_to_a1(row, col_index)
        updates.append({"range": cell, "values": [[value]]})
    if updates:
        sheet.batch_update(updates)


def update_status(config: dict, row: int, status: str) -> None:
    """Convenience wrapper — write only the status column."""
    update_row(config, row, status=status)


def _find_existing_row(
    sheet,
    headers: list[str],
    cols: dict,
    job_row: "JobRow",
) -> int | None:
    """Return the 1-based row index of the first matching row, or None.

    Matches on: URL OR (company AND title both match).
    Reads all values in a single API call to minimise round-trips.
    """
    url_col = cols.get("url", "")
    title_col = cols.get("job_title", "")
    company_col = cols.get("company", "")

    norm_url = (job_row.url or "").strip().lower()
    norm_title = (job_row.title or "").strip().lower()
    norm_company = (job_row.company or "").strip().lower()

    all_values = sheet.get_all_values()
    if len(all_values) < 2:
        return None

    for row_idx, row in enumerate(all_values[1:], start=2):
        def _cell(col_name: str) -> str:
            if col_name not in headers:
                return ""
            idx = headers.index(col_name)
            return (row[idx] if idx < len(row) else "").strip().lower()

        if norm_url and _cell(url_col) == norm_url:
            return row_idx
        if norm_title and norm_company and _cell(title_col) == norm_title and _cell(company_col) == norm_company:
            return row_idx

    return None


def upsert_job_row(
    config: dict,
    job_row: "JobRow",
) -> None:
    """Insert or update a job row in the sheet.

    Match strategy: URL matches OR (company + title both match).
    On insert: all fields including date_found are written.
    On update: all fields except date_found are written (preserve original search date).
    Skips any column not present in the sheet.
    """
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)

    full_field_map = {
        "job_title": job_row.title,
        "company": job_row.company,
        "url": job_row.url,
        "status": job_row.status,
        "date_found": job_row.date_found,
        "details": job_row.details,
        "priority": job_row.priority,
        "reasoning": job_row.reasoning,
    }

    update_field_map = {k: v for k, v in full_field_map.items() if k != "date_found"}

    existing_row_index = _find_existing_row(sheet, headers, cols, job_row)

    if existing_row_index is not None:
        updates = []
        for field, value in update_field_map.items():
            col_name = cols.get(field, "")
            if col_name and col_name in headers:
                col_index = headers.index(col_name) + 1
                cell = gspread.utils.rowcol_to_a1(existing_row_index, col_index)
                updates.append({"range": cell, "values": [[value]]})
        if updates:
            sheet.batch_update(updates)
        return

    row = [""] * len(headers)
    for field, value in full_field_map.items():
        col_name = cols.get(field, "")
        if col_name and col_name in headers:
            row[headers.index(col_name)] = value
    sheet.append_row(row)
