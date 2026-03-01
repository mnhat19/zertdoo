"""
Telegram message sender cho Zertdoo.

Gui tin nhan den nguoi dung qua Telegram Bot API.
Dung httpx (async) de goi API truc tiep -- don gian, nhe.

Chuc nang:
- send_message(): gui plain text, tu dong chia nho neu > 4096 ky tu
- set_webhook(): dang ky webhook URL voi Telegram
- delete_webhook(): xoa webhook (reset)
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger("zertdoo.telegram_sender")

# Telegram Bot API base URL
BASE_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

# Gioi han ky tu moi tin nhan Telegram
MAX_MESSAGE_LENGTH = 4096


async def send_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
) -> list[dict]:
    """
    Gui tin nhan text den nguoi dung.

    Tu dong chia nho neu tin nhan dai hon 4096 ky tu.
    Khong dung emoji, khong HTML/Markdown mac dinh.

    Args:
        text: Noi dung tin nhan
        chat_id: Chat ID nguoi nhan (mac dinh: ALLOWED_CHAT_ID)
        parse_mode: None (plain) hoac "HTML" hoac "MarkdownV2"

    Returns:
        list dict ket qua cua tung tin nhan da gui
    """
    if not settings.telegram_bot_token:
        logger.warning("Chua cau hinh TELEGRAM_BOT_TOKEN, khong gui duoc")
        return []

    target_chat_id = chat_id or settings.telegram_allowed_chat_id
    if not target_chat_id:
        logger.warning("Khong co chat_id de gui tin nhan")
        return []

    # Chia nho tin nhan neu can
    chunks = _split_message(text)
    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            payload = {
                "chat_id": target_chat_id,
                "text": chunk,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode

            try:
                resp = await client.post(
                    f"{BASE_URL}/sendMessage",
                    json=payload,
                )
                data = resp.json()
                if data.get("ok"):
                    results.append(data["result"])
                    logger.debug(
                        "Da gui tin nhan den chat %s (%d ky tu)",
                        target_chat_id, len(chunk),
                    )
                else:
                    logger.error(
                        "Telegram API loi: %s", data.get("description", data)
                    )
            except Exception as e:
                logger.error("Loi gui tin nhan Telegram: %s", e)

    logger.info(
        "Da gui %d/%d tin nhan den chat %s",
        len(results), len(chunks), target_chat_id,
    )
    return results


async def set_webhook(url: Optional[str] = None) -> bool:
    """
    Dang ky webhook URL voi Telegram.

    Args:
        url: Webhook URL day du (mac dinh: WEBHOOK_BASE_URL/webhook/telegram)

    Returns:
        True neu thanh cong
    """
    if not settings.telegram_bot_token:
        logger.warning("Chua cau hinh TELEGRAM_BOT_TOKEN")
        return False

    webhook_url = url or f"{settings.webhook_base_url}/webhook/telegram"
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],
    }
    # Them secret token neu co
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/setWebhook", json=payload)
        data = resp.json()

    if data.get("ok"):
        logger.info("Da dang ky webhook: %s", webhook_url)
        return True
    else:
        logger.error("Loi dang ky webhook: %s", data.get("description", data))
        return False


async def delete_webhook() -> bool:
    """Xoa webhook hien tai."""
    if not settings.telegram_bot_token:
        return False

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BASE_URL}/deleteWebhook",
            json={"drop_pending_updates": True},
        )
        data = resp.json()

    if data.get("ok"):
        logger.info("Da xoa webhook")
        return True
    else:
        logger.error("Loi xoa webhook: %s", data.get("description", data))
        return False


async def get_webhook_info() -> dict:
    """Lay thong tin webhook hien tai."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/getWebhookInfo")
        data = resp.json()
    return data.get("result", {})


def _split_message(text: str) -> list[str]:
    """
    Chia tin nhan dai thanh nhieu phan, moi phan <= 4096 ky tu.
    Uu tien cat tai dau dong.
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= MAX_MESSAGE_LENGTH:
            chunks.append(remaining)
            break

        # Tim vi tri xuong dong gan nhat truoc gioi han
        cut_at = remaining.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if cut_at <= 0:
            # Khong co xuong dong, cat cung tai gioi han
            cut_at = MAX_MESSAGE_LENGTH

        chunks.append(remaining[:cut_at])
        remaining = remaining[cut_at:].lstrip("\n")

    return chunks
