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


def update_status(config: dict, row: int, status: str) -> None:
    """Write a status value back to the sheet for the given row number."""
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)
    col_index = headers.index(cols["status"]) + 1  # gspread is 1-indexed
    sheet.update_cell(row, col_index, status)
