"""
Test TelegramAgent - kich ban phuc tap.
Mo phong cac tin nhan thuc te.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_messages():
    from services.database import init_pool, close_pool
    from agents.telegram import handle_message
    from config import settings

    chat_id = settings.telegram_allowed_chat_id
    await init_pool()

    test_cases = [
        "hom nay met qua, uu tien lai giup",
        "tai sao task nay xep truoc task kia?",
        "them task doc sach 30 phut buoi toi",
    ]

    for i, msg in enumerate(test_cases, 1):
        print(f"\n{'='*40}")
        print(f"TEST {i}: \"{msg}\"")
        print(f"{'='*40}")

        reply = await handle_message(msg, chat_id)
        print(f"Intent + Reply ({len(reply)} chars):")
        print(reply[:500])
        print()

        # Nghi 2s giua cac test
        await asyncio.sleep(2)

    await close_pool()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(test_messages())
