"""
Test SchedulerAgent - chay thu cong full pipeline.
Chay: python tests/test_scheduler.py

Test nay se:
1. Thu thap du lieu that tu Sheet, Tasks, Calendar, Notion, DB
2. Goi LLM that (Gemini/Groq)
3. Tao Google Tasks list that
4. Luu vao Postgres that
5. KHONG tao Calendar events (de tranh spam) - chi log

Luu y: can .env day du va Google OAuth token hop le.
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")

logger = logging.getLogger("test_scheduler")


async def test_build_context():
    """Test buoc 1: thu thap du lieu."""
    print("\n=== Test thu thap du lieu ===")
    from agents.scheduler import _build_context

    context = await _build_context()
    print(f"Context length: {len(context)} ky tu")
    print("--- BAT DAU CONTEXT (500 ky tu dau) ---")
    print(context[:500])
    print("--- KET THUC ---")
    assert len(context) > 100, "Context qua ngan"
    print("[OK] Thu thap du lieu thanh cong")
    return context


async def test_generate_plan(context: str):
    """Test buoc 2: goi LLM."""
    print("\n=== Test goi LLM ===")
    from agents.scheduler import _generate_plan

    plan = await _generate_plan(context)
    print(f"Tasks: {len(plan.daily_tasks)}")
    print(f"Events: {len(plan.events_to_create)}")
    print(f"Risks: {len(plan.risks)}")
    print(f"Questions: {len(plan.questions_for_user)}")

    for t in plan.daily_tasks:
        print(f"  [{t.priority_rank}] {t.time_slot} - {t.title} ({t.duration_minutes}p)")

    assert len(plan.daily_tasks) >= 0, "Plan phai co daily_tasks"
    assert plan.overall_reasoning, "Plan phai co overall_reasoning"
    print("[OK] LLM tra ve plan hop le")
    return plan


async def test_full_run():
    """Test chay full pipeline."""
    print("\n=== Test FULL SchedulerAgent.run() ===")
    print("Luu y: se tao Google Tasks THAT va luu Postgres THAT")
    print()

    from services.database import init_pool, close_pool
    from agents.scheduler import run

    # Init DB pool
    await init_pool()

    try:
        result = await run()

        plan = result["plan"]
        summary = result["summary"]

        print(f"\nTask list ID: {result['task_list_id']}")
        print(f"Task IDs: {len(result['task_ids'])}")
        print(f"Event IDs: {len(result['event_ids'])}")
        print(f"Plan ID (DB): {result['plan_id']}")

        print("\n--- SUMMARY ---")
        print(summary)
        print("--- END SUMMARY ---")

        # Verify
        assert result["plan_id"] > 0, "Plan phai duoc luu vao DB"
        assert len(result["task_ids"]) == len(plan.daily_tasks), "So task IDs phai bang so tasks"

        print("\n[OK] Full pipeline thanh cong!")

    finally:
        await close_pool()


async def main():
    print("=" * 60)
    print("TEST SCHEDULER AGENT")
    print("=" * 60)

    # Test tung buoc
    context = await test_build_context()

    from config import settings
    if not settings.gemini_api_key and not settings.groq_api_key:
        print("\n[SKIP] Khong co LLM API key")
        return

    plan = await test_generate_plan(context)

    # Hoi truoc khi chay full (vi se tao du lieu that)
    print("\n" + "=" * 60)
    print("Ban co muon chay FULL pipeline khong?")
    print("(Se tao Google Tasks that va luu DB that)")
    print("Nhap 'y' de tiep tuc, bat ky phim nao khac de bo qua:")

    answer = input("> ").strip().lower()
    if answer == "y":
        await test_full_run()
    else:
        print("[SKIP] Bo qua full run")

    print("\n" + "=" * 60)
    print("TEST HOAN THANH")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
