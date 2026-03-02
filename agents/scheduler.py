"""
SchedulerAgent - Bo nao len lich hang ngay cua Zertdoo.

Chay tu dong luc 6:00 AM moi ngay (qua APScheduler).
Co the goi thu cong bat ky luc nao.

Luong xu ly:
1. Thu thap du lieu tu tat ca nguon (Sheet, Notion, Tasks, Calendar, Postgres)
2. Xay dung context text cho LLM
3. Goi LLM voi scheduler prompt
4. Parse response thanh DailyPlanOutput
5. Ghi output: tao Google Tasks list, tao Calendar events, luu Postgres
6. Tra ve summary de gui Telegram
"""

import asyncio
import logging
import os
from datetime import date, datetime

from config import settings
from models.schemas import DailyPlanOutput, ScheduledTask, EventToCreate
from services.llm import call_llm
from utils.time_utils import (
    now_vn, today_vn, format_date_vn,
    VN_TZ, WEEKDAY_NAMES_FULL,
)

logger = logging.getLogger("zertdoo.scheduler")

# Duong dan den file prompt
PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
    "scheduler.txt",
)


def _load_prompt() -> str:
    """Doc system prompt tu file."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# BUOC 1: THU THAP DU LIEU
# ============================================================

def _collect_sheets_data() -> str:
    """Doc du lieu tu Google Sheets."""
    try:
        from services.google_sheets import read_sheets_summary
        return read_sheets_summary()
    except Exception as e:
        logger.error("Loi doc Google Sheets: %s", e)
        return f"[LỖI] Không đọc được Google Sheets: {e}"


def _collect_tasks_data() -> str:
    """Doc du lieu tu Google Tasks."""
    try:
        from services.google_tasks import read_tasks_summary
        return read_tasks_summary()
    except Exception as e:
        logger.error("Loi doc Google Tasks: %s", e)
        return f"[LỖI] Không đọc được Google Tasks: {e}"


def _collect_calendar_data() -> str:
    """Doc su kien tu Google Calendar."""
    try:
        from services.google_calendar import read_calendar_summary
        return read_calendar_summary(days=3)
    except Exception as e:
        logger.error("Loi doc Google Calendar: %s", e)
        return f"[LỖI] Không đọc được Google Calendar: {e}"


def _collect_notion_data() -> str:
    """Doc ghi chu tu Notion."""
    try:
        from services.notion import read_notion_summary
        return read_notion_summary(fetch_content=True)
    except Exception as e:
        logger.error("Loi doc Notion: %s", e)
        return f"[LỖI] Không đọc được Notion: {e}"


async def _collect_db_data() -> str:
    """Doc thong ke hanh vi va ke hoach cu tu Postgres."""
    try:
        from services.database import get_behavior_stats, get_latest_daily_plan
        stats = await get_behavior_stats(days=30)
        yesterday_plan = await get_latest_daily_plan(
            today_vn() - __import__("datetime").timedelta(days=1)
        )

        lines = ["=== THỐNG KÊ HÀNH VI 30 NGÀY ==="]
        lines.append(f"- Tổng tasks: {stats.get('total_tasks', 0)}")
        lines.append(f"- Hoàn thành: {stats.get('completed_tasks', 0)}")
        lines.append(f"- Bỏ qua: {stats.get('skipped_tasks', 0)}")
        lines.append(f"- Dời lịch: {stats.get('rescheduled_tasks', 0)}")
        cr = stats.get("completion_rate", 0)
        lines.append(f"- Tỉ lệ hoàn thành: {cr:.0%}" if cr else "- Tỉ lệ hoàn thành: chưa có dữ liệu")
        lines.append(f"- Trung bình tasks/ngày: {stats.get('avg_tasks_per_day', 0):.1f}")

        if yesterday_plan:
            lines.append("\n=== KẾ HOẠCH HÔM QUA ===")
            plan_json = yesterday_plan.get("plan_json", {})
            if isinstance(plan_json, str):
                import json
                plan_json = json.loads(plan_json)
            tasks = plan_json.get("daily_tasks", [])
            for t in tasks:
                title = t.get("title", "?")
                slot = t.get("time_slot", "?")
                lines.append(f"  - {slot}: {title}")
        else:
            lines.append("\n(Không có kế hoạch hôm qua)")

        return "\n".join(lines)
    except Exception as e:
        logger.error("Loi doc database: %s", e)
        return f"[LỖI] Không đọc được database: {e}"


# ============================================================
# BUOC 2: XAY DUNG CONTEXT CHO LLM
# ============================================================

async def _build_context() -> str:
    """
    Gop tat ca du lieu thanh 1 chuoi context de truyen vao LLM.
    Chay readers song song toi da.
    """
    now = now_vn()
    today = today_vn()
    weekday = WEEKDAY_NAMES_FULL[now.weekday()]

    # Chay cac sync readers song song trong thread pool
    loop = asyncio.get_event_loop()
    sheets_task = loop.run_in_executor(None, _collect_sheets_data)
    tasks_task = loop.run_in_executor(None, _collect_tasks_data)
    calendar_task = loop.run_in_executor(None, _collect_calendar_data)
    notion_task = loop.run_in_executor(None, _collect_notion_data)
    db_task = _collect_db_data()

    # Thu thap ket qua
    sheets_data, tasks_data, calendar_data, notion_data, db_data = await asyncio.gather(
        sheets_task, tasks_task, calendar_task, notion_task, db_task
    )

    context = f"""=== NGÀY HÔM NAY ===
{weekday}, {format_date_vn(today)} ({today.strftime('%Y-%m-%d')})
Giờ hiện tại: {now.strftime('%H:%M')}

=== TASKS TỪ GOOGLE SHEET ===
{sheets_data}

=== TASKS TỪ GOOGLE TASKS ===
{tasks_data}

=== SỰ KIỆN GOOGLE CALENDAR ===
{calendar_data}

=== GHI CHÚ NOTION ===
{notion_data}

{db_data}
"""
    return context


# ============================================================
# BUOC 3-4: GOI LLM VA PARSE RESPONSE
# ============================================================

async def _generate_plan(context: str) -> DailyPlanOutput:
    """Goi LLM voi scheduler prompt va context, tra ve DailyPlanOutput."""
    system_prompt = _load_prompt()

    result = await call_llm(
        system_prompt=system_prompt,
        user_content=context,
        response_model=DailyPlanOutput,
        agent_name="scheduler",
        log_to_db=True,
    )

    logger.info(
        "LLM tra ve: %d tasks, %d events, %d risks",
        len(result.daily_tasks),
        len(result.events_to_create),
        len(result.risks),
    )
    return result


# ============================================================
# BUOC 5: GHI OUTPUT
# ============================================================

def _write_google_tasks(plan: DailyPlanOutput, plan_date: date) -> dict:
    """
    Tao task list moi trong Google Tasks theo plan.
    Kiem tra trung truoc khi tao.

    Returns:
        dict voi task_list_id va danh sach task_ids
    """
    from services.google_tasks import (
        get_all_task_lists, create_task_list, create_task, clear_task_list,
    )

    list_title = format_date_vn(plan_date)

    # Kiem tra task list da ton tai chua
    existing_lists = get_all_task_lists()
    existing = None
    for el in existing_lists:
        if el["title"] == list_title:
            existing = el
            break

    if existing:
        task_list_id = existing["id"]
        logger.info("Task list '%s' da ton tai (id=%s), xoa tasks cu...", list_title, task_list_id)
        clear_task_list(task_list_id)
    else:
        result = create_task_list(list_title)
        task_list_id = result["id"]
        logger.info("Da tao task list moi: '%s' (id=%s)", list_title, task_list_id)

    # Tao tasks theo thu tu uu tien
    task_ids = []
    for t in sorted(plan.daily_tasks, key=lambda x: x.priority_rank):
        notes = f"[{t.time_slot}] {t.duration_minutes}p\n{t.reasoning}"
        created = create_task(
            task_list_id=task_list_id,
            title=f"[{t.priority_rank}] {t.title}",
            notes=notes,
        )
        task_ids.append(created["id"])
        logger.debug("Da tao task: [%d] %s", t.priority_rank, t.title)

    logger.info("Da tao %d tasks trong Google Tasks", len(task_ids))
    return {"task_list_id": task_list_id, "task_ids": task_ids}


def _write_google_calendar(plan: DailyPlanOutput) -> list[str]:
    """
    Tao events tren Google Calendar.
    Chi tao events_to_create tu LLM output.

    Returns:
        list event_ids da tao
    """
    from services.google_calendar import create_event

    if not plan.events_to_create:
        logger.info("Khong co event nao can tao")
        return []

    event_ids = []
    for e in plan.events_to_create:
        try:
            result = create_event(
                summary=e.title,
                start=e.start,
                end=e.end,
                description=e.description,
            )
            event_ids.append(result["id"])
            logger.info("Da tao event: '%s'", e.title)
        except Exception as ex:
            logger.error("Loi tao event '%s': %s", e.title, ex)

    return event_ids


async def _write_database(
    plan: DailyPlanOutput,
    plan_date: date,
) -> int:
    """
    Luu plan vao Postgres: daily_plans + task_logs.

    Returns:
        plan_id
    """
    from services.database import save_daily_plan, save_task_log

    # Luu daily plan
    plan_dict = plan.model_dump(mode="json")
    plan_id = await save_daily_plan(plan_date, plan_dict)
    logger.info("Da luu daily plan id=%d cho ngay %s", plan_id, plan_date)

    # Luu tung task vao task_logs
    for t in plan.daily_tasks:
        # Tach source thanh sheet_name/category
        parts = t.source.split("/", 1)
        sheet_name = parts[0] if parts else ""
        category = parts[1] if len(parts) > 1 else ""

        await save_task_log(
            task_name=t.title,
            source="scheduler",
            sheet_name=sheet_name,
            category=category,
            priority=str(t.priority_rank),
            status="pending",
            scheduled_date=plan_date,
            scheduled_time_slot=t.time_slot,
            duration_minutes=t.duration_minutes,
        )

    logger.info("Da luu %d task logs", len(plan.daily_tasks))
    return plan_id


# ============================================================
# BUOC 6: TAO SUMMARY (DE GUI TELEGRAM)
# ============================================================

def _build_summary(plan: DailyPlanOutput, plan_date: date) -> str:
    """
    Tao tin nhan tom tat lich ngay de gui Telegram.
    Khong emoji, khong icon.
    """
    weekday = WEEKDAY_NAMES_FULL[plan_date.weekday()]
    lines = [
        f"LỊCH NGÀY {weekday.upper()} {format_date_vn(plan_date)}",
        f"({plan_date.strftime('%Y-%m-%d')})",
        "",
    ]

    if plan.daily_tasks:
        lines.append(f"--- {len(plan.daily_tasks)} NHIỆM VỤ ---")
        for t in sorted(plan.daily_tasks, key=lambda x: x.priority_rank):
            lines.append(f"{t.priority_rank}. [{t.time_slot}] {t.title} ({t.duration_minutes}p)")
            lines.append(f"   {t.reasoning}")
        lines.append("")

    if plan.events_to_create:
        lines.append(f"--- SỰ KIỆN MỚI ---")
        for e in plan.events_to_create:
            lines.append(f"- {e.title}: {e.start} -> {e.end}")
        lines.append("")

    if plan.risks:
        lines.append("--- CẢNH BÁO ---")
        for r in plan.risks:
            lines.append(f"- {r}")
        lines.append("")

    if plan.questions_for_user:
        lines.append("--- CẦN XÁC NHẬN ---")
        for q in plan.questions_for_user:
            lines.append(f"- {q}")
        lines.append("")

    if plan.overall_reasoning:
        lines.append("--- TỔNG THỂ ---")
        lines.append(plan.overall_reasoning)

    return "\n".join(lines)


# ============================================================
# MAIN: RUN
# ============================================================

async def run(target_date: date = None) -> dict:
    """
    Chay SchedulerAgent hoan chinh.

    Args:
        target_date: Ngay can len lich (mac dinh = hom nay)

    Returns:
        dict voi:
        - plan: DailyPlanOutput
        - summary: str (tin nhan tom tat)
        - task_list_id: str
        - event_ids: list[str]
        - plan_id: int (Postgres)
    """
    plan_date = target_date or today_vn()
    logger.info("=" * 50)
    logger.info("SchedulerAgent bat dau cho ngay %s", plan_date)
    logger.info("=" * 50)

    # 1. Thu thap du lieu
    logger.info("Buoc 1: Thu thap du lieu...")
    context = await _build_context()
    logger.info("Context: %d ky tu", len(context))

    # 2-3-4. Goi LLM
    logger.info("Buoc 2: Goi LLM phan tich va len lich...")
    plan = await _generate_plan(context)

    # 5a. Ghi Google Tasks (chay trong thread vi la sync)
    logger.info("Buoc 3: Ghi Google Tasks...")
    loop = asyncio.get_event_loop()
    tasks_result = await loop.run_in_executor(
        None, _write_google_tasks, plan, plan_date
    )

    # 5b. Ghi Google Calendar (sync)
    logger.info("Buoc 4: Ghi Google Calendar...")
    event_ids = await loop.run_in_executor(
        None, _write_google_calendar, plan
    )

    # 5c. Ghi database (async)
    logger.info("Buoc 5: Luu vao database...")
    plan_id = await _write_database(plan, plan_date)

    # 6. Tao summary
    summary = _build_summary(plan, plan_date)

    logger.info("=" * 50)
    logger.info("SchedulerAgent hoan thanh cho ngay %s", plan_date)
    logger.info("  Tasks: %d, Events: %d, Plan ID: %d",
                len(plan.daily_tasks), len(event_ids), plan_id)
    logger.info("=" * 50)

    return {
        "plan": plan,
        "summary": summary,
        "task_list_id": tasks_result["task_list_id"],
        "task_ids": tasks_result["task_ids"],
        "event_ids": event_ids,
        "plan_id": plan_id,
    }


# ============================================================
# APSCHEDULER WRAPPER (async - dung voi AsyncIOScheduler)
# ============================================================

async def run_scheduled_async():
    """
    Async wrapper cho AsyncIOScheduler.
    Chay tren cung event loop voi FastAPI, truy cap DB pool truc tiep.

    Khong gui Telegram o day - viec do thuoc ve send_morning_summary()
    chay luc 6:15 AM (sau khi co du lieu de trinh bay dep hon).
    """
    logger.info("APScheduler trigger: chay SchedulerAgent...")
    try:
        result = await run()
        logger.info(
            "SchedulerAgent chay xong: %d tasks, %d events, plan_id=%d",
            len(result["plan"].daily_tasks),
            len(result["event_ids"]),
            result["plan_id"],
        )
    except Exception as e:
        logger.error("SchedulerAgent loi: %s", e, exc_info=True)
        # Chi gui Telegram khi co loi nghiem trong
        try:
            from services.telegram_sender import send_message
            await send_message(
                f"[LOI] SchedulerAgent that bai: {type(e).__name__}: {e}"
            )
        except Exception:
            pass
