"""
Test SchedulerAgent prompt voi du lieu that tu Google Sheet.
Chay: python tests/test_scheduler_prompt.py
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from services.llm import call_llm
from models.schemas import DailyPlanOutput
from utils.time_utils import now_vn, today_vn, format_date_vn


def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


async def main():
    print("=" * 60)
    print("TEST SCHEDULER PROMPT VOI DU LIEU MAU")
    print("=" * 60)

    # Load system prompt
    system_prompt = load_prompt("prompts/scheduler.txt")

    # Tao du lieu mau (giong nhu SchedulerAgent se lam)
    today = format_date_vn(today_vn())
    now = now_vn()
    weekday_names = ["Thu 2", "Thu 3", "Thu 4", "Thu 5", "Thu 6", "Thu 7", "Chu nhat"]
    weekday = weekday_names[now.weekday()]

    user_content = f"""
=== NGAY HOM NAY ===
{weekday}, {today}
Gio hien tai: {now.strftime('%H:%M')}

=== TASKS CHUA XONG TU GOOGLE SHEET ===
1. [In_class/CNPM] Thi giua ky CNPM | Priority: High | Due: 03/03/2026 | Status: Pending
2. [Self-study/Toan] Bai tap Toan roi rac chuong 5 | Priority: Medium | Due: 05/03/2026 | Status: Pending
3. [Self-study/English] Luyen IELTS Writing Task 2 | Priority: Medium | Due: khong co | Status: Pending
4. [Skills/Code] Lam project FastAPI ca nhan | Priority: Low | Due: 15/03/2026 | Status: Pending
5. [Research/AI] Doc paper ve RAG | Priority: Low | Due: khong co | Status: Pending

=== SU KIEN GOOGLE CALENDAR HOM NAY ===
- 13:30 - 15:00: Lop CNPM (phong B204)

=== GHI CHU NOTION ===
- "Can on tap lai chuong 3-4 CNPM truoc khi thi"
- "IELTS Writing: focus vao Task 2 argument essay"

=== THONG KE HANH VI 30 NGAY ===
- Tong tasks: 45
- Hoan thanh: 30 (67%)
- Bo qua: 8
- Doi lich: 7
- Trung binh: 3.2 tasks/ngay
- Khung gio hieu qua nhat: 08:00-11:00, 20:00-22:00
- Thuong bo qua: tasks category Research vao cuoi tuan
"""

    print("\n--- Dang goi LLM... ---\n")
    result = await call_llm(
        system_prompt=system_prompt,
        user_content=user_content,
        response_model=DailyPlanOutput,
        agent_name="test_scheduler",
        log_to_db=False,
    )

    print("=== KET QUA ===\n")
    print(f"So tasks duoc len lich: {len(result.daily_tasks)}")
    for t in result.daily_tasks:
        print(f"  [{t.priority_rank}] {t.time_slot} - {t.title} ({t.duration_minutes}p)")
        print(f"      Ly do: {t.reasoning}")

    if result.events_to_create:
        print(f"\nSu kien can tao: {len(result.events_to_create)}")
        for e in result.events_to_create:
            print(f"  {e.title}: {e.start} -> {e.end}")

    if result.risks:
        print(f"\nRui ro:")
        for r in result.risks:
            print(f"  - {r}")

    if result.questions_for_user:
        print(f"\nCau hoi can xac nhan:")
        for q in result.questions_for_user:
            print(f"  - {q}")

    print(f"\nTong the: {result.overall_reasoning}")
    print("\n[OK] Scheduler prompt hoat dong tot")


if __name__ == "__main__":
    asyncio.run(main())
