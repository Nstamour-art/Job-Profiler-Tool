import gspread
from google.oauth2.service_account import Credentials


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
