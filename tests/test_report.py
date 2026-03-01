"""
Test Phase 6: ReportAgent + Gmail.

Test 1: format_report_html - format HTML dung
Test 2: send_email - gui 1 email test don gian
Test 3: run_weekly_report - full pipeline (data -> LLM -> email -> Telegram)
"""

import asyncio
import sys
import os

# Them root vao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_format_html():
    """Test 1: format_report_html tao HTML hop le."""
    from services.gmail import format_report_html

    sample = """BAO CAO TUAN 16/06 - 22/06/2025

1. TONG QUAN
- Tong so tasks: 25
- Hoan thanh: 18/25 (72%)
- Bo qua: 3
- Doi lich: 4

2. PHAN TICH THEO DANH MUC
- In_class: 10/12 hoan thanh
- Self-study: 5/8 hoan thanh
- Skills: 3/5 hoan thanh

3. DE XUAT TUAN TOI
- Tang thoi gian tu hoc them 30 phut moi ngay
- Uu tien tasks Skills vao buoi sang
"""
    html = format_report_html(sample, "Bao cao tuan test")
    
    assert "<!DOCTYPE html>" in html
    assert "BAO CAO TUAN" in html
    assert "TONG QUAN" in html
    assert "72%" in html
    assert "container" in html
    
    print("[OK] Test 1: format_report_html - HTML hop le")
    print(f"     HTML length: {len(html)} chars")
    return html


async def test_send_email():
    """Test 2: gui 1 email test don gian qua Gmail API."""
    from services.gmail import send_email, format_report_html

    html = format_report_html(
        "Day la email test tu Zertdoo Phase 6.\n\nHe thong dang hoat dong binh thuong.",
        "Zertdoo Test Email",
    )

    result = send_email(
        subject="[Zertdoo TEST] Email test Phase 6",
        body_html=html,
    )
    
    assert "id" in result
    print(f"[OK] Test 2: send_email - Da gui, message_id={result['id']}")
    return result


async def test_weekly_report():
    """Test 3: full pipeline weekly report."""
    from services.database import init_pool
    await init_pool()

    from agents.report import run_weekly_report
    result = await run_weekly_report()

    assert result["type"] == "weekly"
    assert result.get("email_id")
    assert result["report_length"] > 0
    
    print(f"[OK] Test 3: run_weekly_report")
    print(f"     Type: {result['type']}")
    print(f"     Email ID: {result['email_id']}")
    print(f"     Report length: {result['report_length']} chars")
    print(f"     Data: {result['data']['total_tasks']} tasks, completion={result['data']['completion_rate']}")


async def main():
    print("=" * 50)
    print("TEST PHASE 6: ReportAgent + Gmail")
    print("=" * 50)

    # Test 1: format HTML
    print("\n--- Test 1: format_report_html ---")
    await test_format_html()

    # Test 2: send simple email
    print("\n--- Test 2: send_email ---")
    await test_send_email()

    # Test 3: full weekly report pipeline
    print("\n--- Test 3: run_weekly_report (full pipeline) ---")
    await test_weekly_report()

    print("\n" + "=" * 50)
    print("TAT CA TESTS DA PASS!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
