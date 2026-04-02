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


def append_job_row(
    config: dict,
    job_row: "JobRow",
) -> None:
    """Append a new job row to the sheet.

    Aligns values to the sheet's header row.
    If a row with a matching URL already exists, updates it in-place instead of appending.
    Skips any column not present in the sheet.
    """
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)

    field_map = {
        "job_title": job_row.title,
        "company": job_row.company,
        "url": job_row.url,
        "status": job_row.status,
        "date_found": job_row.date_found,
        "details": job_row.details,
        "priority": job_row.priority,
        "reasoning": job_row.reasoning,
    }

    # Check for an existing row with the same URL and update it instead of duplicating.
    url_col_name = cols.get("url", "")
    existing_row_index: int | None = None
    # Only attempt URL-based matching when the job's URL is non-empty after stripping.
    normalized_url = (job_row.url or "").strip()
    if normalized_url and url_col_name and url_col_name in headers:
        url_col_index = headers.index(url_col_name) + 1  # 1-based
        url_values = sheet.col_values(url_col_index)
        for i, cell_value in enumerate(url_values[1:], start=2):  # skip header row
            if (cell_value or "").strip() == normalized_url:
                existing_row_index = i
                break

    if existing_row_index is not None:
        updates = []
        for field, value in field_map.items():
            col_name = cols.get(field, "")
            if col_name and col_name in headers:
                col_index = headers.index(col_name) + 1
                cell = gspread.utils.rowcol_to_a1(existing_row_index, col_index)
                updates.append({"range": cell, "values": [[value]]})
        if updates:
            sheet.batch_update(updates)
        return

    row = [""] * len(headers)
    for field, value in field_map.items():
        col_name = cols.get(field, "")
        if col_name and col_name in headers:
            row[headers.index(col_name)] = value

    sheet.append_row(row)
