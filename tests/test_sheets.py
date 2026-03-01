"""Test Google Sheets reader."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from services.google_sheets import get_all_worksheet_names, read_all_sheets

print("=== Google Sheets Reader ===")
names = get_all_worksheet_names()
print(f"Worksheets: {names}")

tasks = read_all_sheets()
print(f"Tong tasks: {len(tasks)}")
for t in tasks[:10]:
    print(f"  [{t.sheet_name}] {t.category} / {t.task} | {t.priority} | {t.status}")
if len(tasks) > 10:
    print(f"  ... va {len(tasks) - 10} tasks nua")
print("DONE")
