"""
Cau hinh trung tam cho toan bo he thong Zertdoo.
Doc bien moi truong tu file .env, cung cap cho moi module khac.
"""

import base64
import json
import os
import logging

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

logger = logging.getLogger("zertdoo.config")


class Settings(BaseSettings):
    """
    Tat ca cau hinh duoc doc tu bien moi truong hoac file .env.
    Dat ten bien theo format: ZERTDOO_TEN_BIEN hoac ten truc tiep.
    """

    # === App ===
    app_name: str = "Zertdoo"
    debug: bool = False
    timezone: str = "Asia/Ho_Chi_Minh"

    # === PostgreSQL ===
    database_url: str = Field(
        default="postgresql://zertdoo:zertdoo@localhost:5432/zertdoo",
        description="Connection string cho PostgreSQL"
    )

    # === Google APIs ===
    google_credentials_path: str = Field(
        default="credentials/credentials.json",
        description="Duong dan den file credentials.json (OAuth Client ID)"
    )
    google_token_path: str = Field(
        default="credentials/token.json",
        description="Duong dan den file token.json (OAuth token da xac thuc)"
    )
    # Cho deploy cloud: luu credentials duoi dang base64 trong env var
    # Neu co gia tri, se tu dong decode va tao file tam
    google_credentials_base64: str = Field(
        default="",
        description="Base64-encoded credentials.json (dung cho cloud deploy thay vi file)"
    )
    google_token_base64: str = Field(
        default="",
        description="Base64-encoded token.json (dung cho cloud deploy thay vi file)"
    )
    google_spreadsheet_id: str = Field(
        default="",
        description="ID cua Google Spreadsheet chua tasks"
    )

    # === Notion ===
    notion_token: str = Field(
        default="",
        description="Internal Integration Token cua Notion"
    )

    # === LLM ===
    gemini_api_key: str = Field(
        default="",
        description="API key cua Google Gemini"
    )
    groq_api_key: str = Field(
        default="",
        description="API key cua Groq (fallback)"
    )
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    llm_max_retries: int = 3

    # === Telegram ===
    telegram_bot_token: str = Field(
        default="",
        description="Token cua Telegram Bot tu BotFather"
    )
    telegram_allowed_chat_id: str = Field(
        default="",
        description="Chat ID cua nguoi dung duoc phep tuong tac voi bot"
    )
    telegram_webhook_secret: str = Field(
        default="",
        description="Secret token de xac thuc webhook tu Telegram"
    )

    # === Gmail ===
    gmail_recipient: str = "nhatdm234112e@st.uel.edu.vn"
    year_vision_path: str = "assets/year_vision.jpg"

    # === API Security ===
    api_secret_key: str = Field(
        default="",
        description="Secret key de xac thuc cac API endpoint (Authorization: Bearer <key>)"
    )

    # === Scheduler ===
    scheduler_hour: int = 6
    scheduler_minute: int = 0

    # === Server ===
    host: str = "0.0.0.0"
    port: int = 8000
    webhook_base_url: str = Field(
        default="",
        description="URL goc cua server (VD: https://zertdoo.duckdns.org)"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton: import settings tu bat ky dau
settings = Settings()


def setup_google_credentials():
    """
    Neu chay tren cloud (Koyeb), Google credentials duoc luu dang base64
    trong bien moi truong. Ham nay decode va ghi ra file tam de cac
    Google API client doc duoc.

    Goi ham nay 1 lan khi server khoi dong (trong lifespan).
    """
    if settings.google_credentials_base64:
        os.makedirs(os.path.dirname(settings.google_credentials_path), exist_ok=True)
        decoded = base64.b64decode(settings.google_credentials_base64)
        with open(settings.google_credentials_path, "wb") as f:
            f.write(decoded)
        logger.info("Da tao file credentials.json tu bien moi truong.")

    if settings.google_token_base64:
        os.makedirs(os.path.dirname(settings.google_token_path), exist_ok=True)
        decoded = base64.b64decode(settings.google_token_base64)
        with open(settings.google_token_path, "wb") as f:
            f.write(decoded)
        logger.info("Da tao file token.json tu bien moi truong.")
