"""
Google Auth helper cho Zertdoo.
Cung cap ham xac thuc chung cho tat ca Google API services
(Sheets, Tasks, Calendar, Gmail).

Su dung OAuth 2.0 voi credentials.json va token.json.
Token tu dong refresh khi het han.
"""

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import settings

logger = logging.getLogger("zertdoo.google_auth")

# Scopes can thiet cho toan bo he thong
# Neu thay doi scopes, xoa token.json va chay lai de xac thuc
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",   # Doc Google Sheets
    "https://www.googleapis.com/auth/tasks",                    # CRUD Google Tasks
    "https://www.googleapis.com/auth/calendar",                 # CRUD Google Calendar
    "https://www.googleapis.com/auth/gmail.send",               # Gui Gmail
]


def get_google_credentials() -> Credentials:
    """
    Lay Google OAuth credentials da xac thuc.

    Luong xu ly:
    1. Doc token.json (neu co) -> refresh neu het han
    2. Neu khong co token.json -> chay luong OAuth (chi chay lan dau tren local)
    3. Luu token.json moi sau khi refresh/tao

    Returns:
        google.oauth2.credentials.Credentials
    """
    creds = None
    token_path = settings.google_token_path
    creds_path = settings.google_credentials_path

    # Doc token da luu
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        logger.debug("Doc token tu %s", token_path)

    # Refresh hoac tao moi
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Token het han, dang refresh...")
            creds.refresh(Request())
            logger.info("Token da refresh thanh cong.")
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Khong tim thay file credentials: {creds_path}. "
                    "Tai tu Google Cloud Console > APIs & Services > Credentials."
                )
            logger.info("Chay luong OAuth xac thuc lan dau...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Xac thuc Google thanh cong.")

        # Luu token moi
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        logger.info("Token da luu vao %s", token_path)

    return creds


def build_service(api_name: str, api_version: str):
    """
    Tao Google API service client.

    Args:
        api_name: Ten API (vd: 'sheets', 'tasks', 'calendar', 'gmail')
        api_version: Phien ban (vd: 'v4', 'v1', 'v3')

    Returns:
        googleapiclient.discovery.Resource
    """
    from googleapiclient.discovery import build

    creds = get_google_credentials()
    service = build(api_name, api_version, credentials=creds)
    logger.debug("Da tao service %s %s", api_name, api_version)
    return service
