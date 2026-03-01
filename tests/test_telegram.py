"""
Test Phase 4: TelegramAgent

Test 1: Gui tin nhan test den Telegram
Test 2: Xu ly 1 tin nhan mo phong (khong qua webhook)
Test 3: Morning summary
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_send_message():
    """Test gui tin nhan den Telegram."""
    from services.telegram_sender import send_message
    print("=== TEST 1: Gui tin nhan ===")
    results = await send_message("Zertdoo test: he thong dang hoat dong binh thuong.")
    print(f"Da gui {len(results)} tin nhan")
    if results:
        print(f"Message ID: {results[0].get('message_id')}")
    return len(results) > 0


async def test_handle_message():
    """Test xu ly tin nhan (mo phong nguoi dung nhan)."""
    from services.database import init_pool, close_pool
    from agents.telegram import handle_message
    from config import settings

    print("\n=== TEST 2: Xu ly tin nhan ===")
    await init_pool()
    try:
        reply = await handle_message(
            message_text="trang thai hom nay the nao?",
            chat_id=settings.telegram_allowed_chat_id,
        )
        print(f"Reply ({len(reply)} ky tu):")
        print(reply[:500])
    finally:
        await close_pool()


async def test_morning_summary():
    """Test morning summary."""
    from services.database import init_pool, close_pool
    from agents.telegram import send_morning_summary

    print("\n=== TEST 3: Morning summary ===")
    await init_pool()
    try:
        await send_morning_summary()
        print("Da gui morning summary")
    finally:
        await close_pool()


async def main():
    print("Phase 4 - TelegramAgent Test")
    print("=" * 40)

    # Test 1: gui tin nhan
    ok = await test_send_message()
    if not ok:
        print("[FAIL] Khong gui duoc tin nhan. Kiem tra BOT_TOKEN va CHAT_ID.")
        return

    # Test 2: xu ly tin nhan
    await test_handle_message()

    # Test 3: morning summary
    await test_morning_summary()

    print("\n" + "=" * 40)
    print("Tat ca tests hoan thanh.")


if __name__ == "__main__":
    asyncio.run(main())
