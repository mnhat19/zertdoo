"""
Web Push Notification service.
Gui push notification den trinh duyet cua nguoi dung qua VAPID protocol.

Yeu cau:
- VAPID_PUBLIC_KEY va VAPID_PRIVATE_KEY trong config
- Browser da dang ky subscription qua /api/push/subscribe
"""

import asyncio
import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger("zertdoo.web_push")


async def send_push_notification(title: str, body: str) -> int:
    """
    Gui web push notification den tat ca subscriptions da dang ky.

    Args:
        title: Tieu de notification
        body:  Noi dung notification

    Returns:
        So subscriptions da gui thanh cong.
    """
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.warning("VAPID keys chua cau hinh, bo qua web push")
        return 0

    from services.database import get_push_subscriptions, remove_push_subscription

    subscriptions = await get_push_subscriptions()
    if not subscriptions:
        logger.debug("Khong co push subscription nao")
        return 0

    payload = json.dumps(
        {
            "title": title,
            "body": body,
        },
        ensure_ascii=False,
    )

    success_count = 0
    gone_endpoints: list[str] = []
    loop = asyncio.get_event_loop()

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["p256dh"],
                "auth": sub["auth"],
            },
        }
        try:
            await loop.run_in_executor(None, _send_one_push, subscription_info, payload)
            success_count += 1
        except Exception as e:
            err_str = str(e)
            # 404/410 nghia la subscription het han
            if "404" in err_str or "410" in err_str:
                gone_endpoints.append(sub["endpoint"])
                logger.info("Push subscription het han, se xoa: %s...", sub["endpoint"][:50])
            else:
                logger.warning("Loi gui push toi %s...: %s", sub["endpoint"][:40], e)

    # Xoa subscriptions het han
    for endpoint in gone_endpoints:
        try:
            await remove_push_subscription(endpoint)
        except Exception:
            pass

    logger.info(
        "Web push: %d/%d subscriptions thanh cong", success_count, len(subscriptions)
    )
    return success_count


def _send_one_push(subscription_info: dict, payload: str) -> None:
    """Sync helper (chay trong executor): gui push den 1 subscription."""
    from pywebpush import webpush

    webpush(
        subscription_info=subscription_info,
        data=payload,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
        ttl=3600,  # Notification ton tai toi da 1 tieng
    )
