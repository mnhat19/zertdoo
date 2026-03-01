"""Xem header va 3 hang dau cua tat ca sheets."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from services.google_auth import build_service
from services.google_sheets import get_all_worksheet_names
from config import settings

service = build_service("sheets", "v4")
sid = settings.google_spreadsheet_id

names = get_all_worksheet_names()
for name in names:
    result = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=f"'{name}'!A1:H5",
    ).execute()
    rows = result.get("values", [])
    print(f"\n=== {name} ({len(rows)} rows preview) ===")
    for i, row in enumerate(rows):
        label = "HEADER" if i == 0 else f"Row {i+1}"
        print(f"  {label}: {row}")
