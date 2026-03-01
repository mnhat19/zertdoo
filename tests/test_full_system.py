"""
Test rà soát toàn bộ hệ thống Zertdoo trước Phase 7.

Tests:
1. SchedulerAgent: full pipeline (collect -> LLM -> write -> summary Telegram)
2. TelegramAgent: handle_message + morning summary
3. SyncAgent: snapshot + change detection
4. ReportAgent: weekly report (data -> LLM -> email -> Telegram)
5. Kiểm tra tiếng Việt có dấu trong output
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def has_vietnamese_diacritics(text: str) -> bool:
    """Kiểm tra text có chứa ký tự tiếng Việt có dấu."""
    diacritics = "àáạảãăắằặẳẵâấầậẩẫèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹđ"
    diacritics += diacritics.upper()
    return any(c in diacritics for c in text)


async def test_1_scheduler():
    """Test 1: SchedulerAgent full pipeline."""
    print("\n--- Test 1: SchedulerAgent ---")
    from agents.scheduler import run as scheduler_run
    
    result = await scheduler_run()
    
    assert result["plan"] is not None
    assert result["summary"] is not None
    
    summary = result["summary"]
    print(f"  Tasks: {len(result['plan'].daily_tasks)}")
    print(f"  Events: {len(result['event_ids'])}")
    print(f"  Summary length: {len(summary)} chars")
    
    # Kiểm tra tiếng Việt có dấu trong summary
    assert has_vietnamese_diacritics(summary), "Summary KHÔNG có tiếng Việt có dấu!"
    print(f"  Tiếng Việt có dấu: OK")
    
    # In vài dòng đầu summary
    lines = summary.split("\n")[:5]
    for line in lines:
        print(f"  > {line}")
    
    print("[OK] Test 1: SchedulerAgent passed")
    return result


async def test_2_telegram():
    """Test 2: TelegramAgent handle_message."""
    print("\n--- Test 2: TelegramAgent ---")
    from agents.telegram import handle_message
    from config import settings
    
    chat_id = settings.telegram_allowed_chat_id
    
    # Test query
    reply = await handle_message("tiến độ hôm nay thế nào?", chat_id)
    print(f"  Query reply: {reply[:200]}")
    assert reply is not None
    assert len(reply) > 10
    assert has_vietnamese_diacritics(reply), "Telegram reply KHÔNG có tiếng Việt có dấu!"
    print(f"  Tiếng Việt có dấu: OK")
    
    print("[OK] Test 2: TelegramAgent passed")
    return reply


async def test_3_sync():
    """Test 3: SyncAgent snapshot."""
    print("\n--- Test 3: SyncAgent ---")
    from agents.sync import run as sync_run
    
    result = await sync_run()
    
    print(f"  Tasks snapshot: {result['total_tasks_snapshot']}")
    print(f"  Sheets snapshot: {result['total_sheets_snapshot']}")
    print(f"  Changes: tasks={result['tasks_changes']}, sheets={result['sheets_changes']}")
    print(f"  DB synced: {result['db_synced']}")
    
    assert result["total_tasks_snapshot"] >= 0
    assert result["total_sheets_snapshot"] >= 0
    
    print("[OK] Test 3: SyncAgent passed")
    return result


async def test_4_report():
    """Test 4: ReportAgent weekly."""
    print("\n--- Test 4: ReportAgent weekly ---")
    from agents.report import run_weekly_report
    
    result = await run_weekly_report()
    
    assert result["type"] == "weekly"
    assert result.get("email_id")
    assert result["report_length"] > 0
    
    print(f"  Email ID: {result['email_id']}")
    print(f"  Report length: {result['report_length']} chars")
    print(f"  Tasks in data: {result['data']['total_tasks']}")
    
    print("[OK] Test 4: ReportAgent passed")
    return result


async def test_5_vietnamese_check():
    """Test 5: Kiểm tra prompts có tiếng Việt có dấu."""
    print("\n--- Test 5: Kiểm tra prompts tiếng Việt ---")
    
    prompt_files = [
        "prompts/scheduler.txt",
        "prompts/telegram.txt",
        "prompts/report.txt",
    ]
    
    for pf in prompt_files:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), pf)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert has_vietnamese_diacritics(content), f"{pf} KHÔNG có tiếng Việt có dấu!"
        print(f"  {pf}: OK ({len(content)} chars)")
    
    # Kiểm tra gmail footer
    from services.gmail import format_report_html
    html = format_report_html("Test report content", "Test title")
    assert "Báo cáo được tạo tự động" in html, "Gmail footer KHÔNG có tiếng Việt có dấu!"
    print(f"  Gmail footer: OK")
    
    print("[OK] Test 5: Vietnamese check passed")


async def main():
    print("=" * 60)
    print("RÀ SOÁT TOÀN BỘ HỆ THỐNG ZERTDOO")
    print("=" * 60)
    
    from services.database import init_pool
    await init_pool()
    
    errors = []
    
    # Test 5 first (no API calls)
    try:
        await test_5_vietnamese_check()
    except Exception as e:
        print(f"[FAIL] Test 5: {e}")
        errors.append(("Test 5 Vietnamese", str(e)))
    
    # Test 1: Scheduler
    try:
        await test_1_scheduler()
    except Exception as e:
        print(f"[FAIL] Test 1: {e}")
        errors.append(("Test 1 Scheduler", str(e)))
    
    # Test 2: Telegram
    try:
        await test_2_telegram()
    except Exception as e:
        print(f"[FAIL] Test 2: {e}")
        errors.append(("Test 2 Telegram", str(e)))
    
    # Test 3: Sync
    try:
        await test_3_sync()
    except Exception as e:
        print(f"[FAIL] Test 3: {e}")
        errors.append(("Test 3 Sync", str(e)))
    
    # Test 4: Report
    try:
        await test_4_report()
    except Exception as e:
        print(f"[FAIL] Test 4: {e}")
        errors.append(("Test 4 Report", str(e)))
    
    print("\n" + "=" * 60)
    if errors:
        print(f"KẾT QUẢ: {len(errors)} THẤT BẠI")
        for name, err in errors:
            print(f"  [X] {name}: {err}")
    else:
        print("TẤT CẢ TESTS ĐÃ PASS!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
