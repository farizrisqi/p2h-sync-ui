import json
import os
from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SHEET_ID = "1YTHzqtKQ3so2gz0D1tZzuBwmw5evXeFITG7qhJILGzA"
SHEET_NAME = "P2H"
COLUMNS = ["JAM P2H", "UNIT", "NO P2H", "APPROVER"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
LAST_SYNC_CELL = "F1"


def _get_worksheet():
    creds_info = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        return sh.sheet1


def read_last_sync() -> str | None:
    """Baca timestamp ETL terakhir dari cell G1 Google Sheets."""
    worksheet = _get_worksheet()
    val = worksheet.acell("G1").value
    return val if val else None


def sync_p2h_sheet(csv_path: Path) -> int:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    df = df[COLUMNS]

    worksheet = _get_worksheet()
    worksheet.clear()
    worksheet.update("A1", [COLUMNS] + df.values.tolist())
    worksheet.update(LAST_SYNC_CELL, [["LAST_SYNC_UTC", datetime.now(timezone.utc).isoformat()]])
    return len(df)
