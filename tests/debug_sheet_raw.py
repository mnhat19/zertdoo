"""Xem du lieu raw tu sheet In_class de hieu cau truc."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from services.google_auth import build_service
from config import settings

service = build_service("sheets", "v4")
sid = settings.google_spreadsheet_id

# Doc hang 1 (header) va 10 hang dau cua In_class
result = service.spreadsheets().values().get(
    spreadsheetId=sid,
    range="'In_class'!A1:H15",
).execute()

rows = result.get("values", [])
print(f"=== In_class: {len(rows)} rows ===")
for i, row in enumerate(rows):
    print(f"  Row {i+1}: {row}")

# Doc Self-study
result2 = service.spreadsheets().values().get(
    spreadsheetId=sid,
    range="'Self-study'!A1:H10",
).execute()
rows2 = result2.get("values", [])
print(f"\n=== Self-study: {len(rows2)} rows ===")
for i, row in enumerate(rows2):
    print(f"  Row {i+1}: {row}")
