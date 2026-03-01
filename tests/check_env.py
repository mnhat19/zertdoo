"""Kiem tra env vars."""
from dotenv import load_dotenv
load_dotenv()
from config import settings

sid = settings.google_spreadsheet_id
nt = settings.notion_token

print(f"SPREADSHEET_ID: [{sid if sid else '(trong)'}]")
print(f"NOTION_TOKEN: [{nt[:10] + '...' if nt else '(trong)'}]")
