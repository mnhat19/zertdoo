"""
TelegramAgent - Xu ly tin nhan va tuong tac 2 chieu qua Telegram.

Luong xu ly moi tin nhan:
1. Nhan message text tu webhook
2. Lay context: daily_plan hom nay, tasks hien tai, events, lich su
3. Goi LLM voi telegram prompt + context + message
4. Parse response: intent + actions + reply
5. Thuc thi actions (cap nhat Tasks, Calendar, DB)
6. Gui reply ve Telegram

Thong bao chu dong:
- 6:15 AM: tom tat lich ngay (sau SchedulerAgent)
- 12:00 PM: nhac tasks buoi chieu
- 9:00 PM: review cuoi ngay
"""

import asyncio
import logging
import os
from datetime import date

from config import settings
from models.schemas import TelegramResponse, TelegramAction
from services.llm import call_llm
from services.telegram_sender import send_message
from utils.time_utils import (
    now_vn, today_vn, format_date_vn,
    VN_TZ, WEEKDAY_NAMES_FULL,
)

logger = logging.getLogger("zertdoo.telegram")

# === Prompt file ===
PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
    "telegram.txt",
)


def _load_prompt() -> str:
    """Doc system prompt tu file."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# XAY DUNG CONTEXT
# ============================================================

async def _build_context() -> str:
    """
    Thu thap context hien tai cho LLM:
    - Ngay gio
    - Daily plan hom nay
    - Google Tasks hien tai
    - Calendar events
    - Lich su hanh vi
    """
    now = now_vn()
    today = today_vn()
    weekday = WEEKDAY_NAMES_FULL[now.weekday()]

    loop = asyncio.get_event_loop()

    # Thu thap du lieu song song
    tasks_task = loop.run_in_executor(None, _collect_tasks)
    calendar_task = loop.run_in_executor(None, _collect_calendar)
    db_task = _collect_db_context()

    tasks_data, calendar_data, db_data = await asyncio.gather(
        tasks_task, calendar_task, db_task
    )

    context = f"""=== THOI GIAN HIEN TAI ===
{weekday}, {format_date_vn(today)} ({today.strftime('%Y-%m-%d')})
Gio: {now.strftime('%H:%M')}

=== GOOGLE TASKS HOM NAY ===
{tasks_data}

=== GOOGLE CALENDAR ===
{calendar_data}

{db_data}
"""
    return context


def _collect_tasks() -> str:
    """Doc Google Tasks hien tai."""
    try:
        from services.google_tasks import read_tasks_summary
        return read_tasks_summary()
    except Exception as e:
        logger.error("Loi doc Google Tasks: %s", e)
        return f"[LOI] Khong doc duoc: {e}"


def _collect_calendar() -> str:
    """Doc events tu Calendar."""
    try:
        from services.google_calendar import read_calendar_summary
        return read_calendar_summary(days=2)
    except Exception as e:
        logger.error("Loi doc Calendar: %s", e)
        return f"[LOI] Khong doc duoc: {e}"


async def _collect_db_context() -> str:
    """Doc daily plan + task logs tu Postgres."""
    try:
        from services.database import get_latest_daily_plan, get_recent_task_logs

        today = today_vn()
        plan = await get_latest_daily_plan(today)
        recent_logs = await get_recent_task_logs(days=3)

        lines = []
        if plan:
            import json
            plan_json = plan.get("plan_json", {})
            if isinstance(plan_json, str):
                plan_json = json.loads(plan_json)

            lines.append("=== KE HOACH HOM NAY (tu SchedulerAgent) ===")
            tasks = plan_json.get("daily_tasks", [])
            for t in tasks:
                title = t.get("title", "?")
                slot = t.get("time_slot", "?")
                dur = t.get("duration_minutes", "?")
                rank = t.get("priority_rank", "?")
                reasoning = t.get("reasoning", "")
                lines.append(f"  {rank}. [{slot}] {title} ({dur}p)")
                if reasoning:
                    lines.append(f"     Ly do: {reasoning}")

            risks = plan_json.get("risks", [])
            if risks:
                lines.append("\nCanh bao:")
                for r in risks:
                    lines.append(f"  - {r}")

            overall = plan_json.get("overall_reasoning", "")
            if overall:
                lines.append(f"\nTong the: {overall}")
        else:
            lines.append("=== CHUA CO KE HOACH HOM NAY ===")
            lines.append("(SchedulerAgent chua chay hoac chua tao plan)")

        if recent_logs:
            lines.append("\n=== TASK LOGS 3 NGAY GAN ===")
            for log in recent_logs[:15]:
                name = log.get("task_name", "?")
                status = log.get("status", "?")
                sched_date = log.get("scheduled_date", "?")
                lines.append(f"  - [{sched_date}] {name}: {status}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("Loi doc DB context: %s", e)
        return f"[LOI] Khong doc duoc database: {e}"


# ============================================================
# GOI LLM VA PARSE RESPONSE
# ============================================================

async def _analyze_message(message_text: str, context: str) -> TelegramResponse:
    """
    Goi LLM voi telegram prompt + context + message.
    Tra ve TelegramResponse (intent, reply, actions).
    """
    system_prompt = _load_prompt()

    user_content = f"""{context}

=== TIN NHAN NGUOI DUNG ===
{message_text}
"""

    result: TelegramResponse = await call_llm(
        system_prompt=system_prompt,
        user_content=user_content,
        response_model=TelegramResponse,
        agent_name="telegram",
        log_to_db=True,
    )  # type: ignore[assignment]

    logger.info(
        "LLM phan tich: intent=%s, %d actions",
        result.intent, len(result.actions),
    )
    return result


# ============================================================
# THUC THI ACTIONS
# ============================================================

async def _execute_actions(actions: list[TelegramAction]) -> list[str]:
    """
    Thuc thi cac actions tu LLM response.

    Returns:
        list log cua tung action da thuc hien
    """
    if not actions:
        return []

    action_logs = []
    loop = asyncio.get_event_loop()

    for action in actions:
        action_type = action.type
        params = action.params

        try:
            if action_type == "no_action":
                continue

            elif action_type == "complete_task":
                log = await _action_complete_task(params, loop)
                action_logs.append(log)

            elif action_type == "create_task":
                log = await _action_create_task(params, loop)
                action_logs.append(log)

            elif action_type == "delete_task":
                log = await _action_delete_task(params, loop)
                action_logs.append(log)

            elif action_type == "update_task":
                log = await _action_update_task(params, loop)
                action_logs.append(log)

            elif action_type == "create_event":
                log = await _action_create_event(params, loop)
                action_logs.append(log)

            elif action_type == "update_event":
                log = await _action_update_event(params, loop)
                action_logs.append(log)

            elif action_type == "delete_event":
                log = await _action_delete_event(params, loop)
                action_logs.append(log)

            elif action_type == "reschedule_plan":
                log = await _action_reschedule_plan(params)
                action_logs.append(log)

            else:
                logger.warning("Action type khong ho tro: %s", action_type)
                action_logs.append(f"[SKIP] Khong ho tro: {action_type}")

        except Exception as e:
            logger.error("Loi thuc thi action %s: %s", action_type, e)
            action_logs.append(f"[LOI] {action_type}: {e}")

    return action_logs


async def _action_complete_task(params: dict, loop) -> str:
    """Danh dau task hoan thanh trong Google Tasks."""
    from services.google_tasks import (
        get_all_task_lists, get_tasks_from_list, complete_task,
    )

    task_title = params.get("task_title", "")
    if not task_title:
        return "[SKIP] Khong co task_title"

    # Tim task theo title
    def _find_and_complete():
        lists = get_all_task_lists()
        for tl in lists:
            tasks = get_tasks_from_list(tl["id"])
            for t in tasks:
                if task_title.lower() in t.title.lower():
                    complete_task(tl["id"], t.task_id)
                    return f"Da hoan thanh: {t.title}"
        return f"Khong tim thay task: {task_title}"

    result = await loop.run_in_executor(None, _find_and_complete)

    # Log vao DB
    try:
        from services.database import log_behavior
        await log_behavior("complete_task", {"task_title": task_title, "result": result})
    except Exception:
        pass

    logger.info("Action complete_task: %s", result)
    return result


async def _action_create_task(params: dict, loop) -> str:
    """Tao task moi trong Google Tasks (them vao list hom nay)."""
    from services.google_tasks import (
        get_all_task_lists, create_task_list, create_task,
    )
    from utils.time_utils import format_date_vn

    title = params.get("title", "")
    time_slot = params.get("time_slot", "")
    duration = params.get("duration_minutes", "")
    priority = params.get("priority", "Medium")

    if not title:
        return "[SKIP] Khong co title"

    today = today_vn()
    list_title = format_date_vn(today)

    def _create():
        # Tim list hom nay
        lists = get_all_task_lists()
        task_list_id = None
        for tl in lists:
            if tl["title"] == list_title:
                task_list_id = tl["id"]
                break

        if not task_list_id:
            result = create_task_list(list_title)
            task_list_id = result["id"]

        notes = ""
        if time_slot:
            notes += f"[{time_slot}] "
        if duration:
            notes += f"{duration}p "
        notes += f"Priority: {priority}"

        created = create_task(task_list_id, title, notes=notes)
        return f"Da tao task: {title} (id={created['id']})"

    result = await loop.run_in_executor(None, _create)
    logger.info("Action create_task: %s", result)
    return result


async def _action_delete_task(params: dict, loop) -> str:
    """Xoa task tu Google Tasks."""
    from services.google_tasks import (
        get_all_task_lists, get_tasks_from_list, delete_task,
    )

    task_title = params.get("task_title", "")
    if not task_title:
        return "[SKIP] Khong co task_title"

    def _find_and_delete():
        lists = get_all_task_lists()
        for tl in lists:
            tasks = get_tasks_from_list(tl["id"])
            for t in tasks:
                if task_title.lower() in t.title.lower():
                    delete_task(tl["id"], t.task_id)
                    return f"Da xoa: {t.title}"
        return f"Khong tim thay task: {task_title}"

    result = await loop.run_in_executor(None, _find_and_delete)
    logger.info("Action delete_task: %s", result)
    return result


async def _action_update_task(params: dict, loop) -> str:
    """Cap nhat thong tin task (hien tai: ghi nhan, chua edit truc tiep)."""
    task_title = params.get("task_title", "")
    field = params.get("field", "")
    new_value = params.get("new_value", "")

    # Log vao behavior
    try:
        from services.database import log_behavior
        await log_behavior("update_task", {
            "task_title": task_title,
            "field": field,
            "new_value": new_value,
        })
    except Exception:
        pass

    return f"Da ghi nhan thay doi: {task_title} - {field} = {new_value}"


async def _action_create_event(params: dict, loop) -> str:
    """Tao event moi tren Google Calendar."""
    from services.google_calendar import create_event

    title = params.get("title", "")
    start = params.get("start", "")
    end = params.get("end", "")
    description = params.get("description", "")

    if not title or not start or not end:
        return f"[SKIP] Thieu thong tin event: title={title}, start={start}, end={end}"

    def _create():
        result = create_event(
            summary=title, start=start, end=end, description=description
        )
        return f"Da tao event: {title} (id={result['id']})"

    result = await loop.run_in_executor(None, _create)
    logger.info("Action create_event: %s", result)
    return result


async def _action_update_event(params: dict, loop) -> str:
    """Cap nhat event (ghi nhan)."""
    event_title = params.get("event_title", "")
    field = params.get("field", "")
    new_value = params.get("new_value", "")
    return f"Da ghi nhan thay doi event: {event_title} - {field} = {new_value}"


async def _action_delete_event(params: dict, loop) -> str:
    """Xoa event tu Calendar (can event_id)."""
    event_title = params.get("event_title", "")
    return f"Da ghi nhan yeu cau xoa event: {event_title}"


async def _action_reschedule_plan(params: dict) -> str:
    """
    Sap xep lai ke hoach.
    Goi SchedulerAgent chay lai.
    """
    strategy = params.get("strategy", "")
    reason = params.get("reason", "")
    logger.info("Reschedule plan: strategy=%s, reason=%s", strategy, reason)

    try:
        from agents.scheduler import run as scheduler_run
        result = await scheduler_run()
        summary = result["summary"]

        # Gui summary moi
        await send_message(
            f"DA SAP XEP LAI LICH:\n\n{summary}"
        )
        return f"Da reschedule: {len(result['plan'].daily_tasks)} tasks"
    except Exception as e:
        logger.error("Loi reschedule: %s", e)
        return f"[LOI] Reschedule that bai: {e}"


# ============================================================
# MAIN: XU LY TIN NHAN
# ============================================================

async def handle_message(message_text: str, chat_id: str) -> str:
    """
    Xu ly 1 tin nhan tu Telegram.
    Day la entry point chinh cua TelegramAgent.

    Args:
        message_text: Noi dung tin nhan
        chat_id: Chat ID nguoi gui

    Returns:
        Noi dung reply da gui
    """
    logger.info("Nhan tin nhan tu chat %s: %s", chat_id, message_text[:100])

    # 1. Kiem tra quyen
    if str(chat_id) != str(settings.telegram_allowed_chat_id):
        logger.warning("Chat ID khong duoc phep: %s", chat_id)
        await send_message("Khong co quyen su dung bot nay.", chat_id=chat_id)
        return "Unauthorized"

    try:
        # 2. Thu thap context
        logger.info("Thu thap context...")
        context = await _build_context()
        logger.info("Context: %d ky tu", len(context))

        # 3. Goi LLM phan tich
        logger.info("Goi LLM phan tich tin nhan...")
        response = await _analyze_message(message_text, context)

        # 4. Thuc thi actions
        if response.actions:
            action_logs = await _execute_actions(response.actions)
            if action_logs:
                logger.info("Actions da thuc thi: %s", action_logs)

        # 5. Gui reply
        reply = response.response_message
        await send_message(reply)

        # 6. Log vao DB
        try:
            from services.database import log_behavior
            await log_behavior("telegram_message", {
                "message": message_text[:200],
                "intent": response.intent,
                "actions_count": len(response.actions),
                "reasoning": response.reasoning[:200] if response.reasoning else "",
            })
        except Exception:
            pass

        logger.info(
            "Da xu ly tin nhan: intent=%s, reply=%d ky tu",
            response.intent, len(reply),
        )
        return reply

    except Exception as e:
        logger.error("Loi xu ly tin nhan: %s", e, exc_info=True)
        error_msg = f"Loi he thong khi xu ly yeu cau. Vui long thu lai. ({type(e).__name__})"
        await send_message(error_msg)
        return error_msg


# ============================================================
# THONG BAO CHU DONG
# ============================================================

async def send_morning_summary():
    """
    Gui tom tat lich ngay vao 6:15 AM.
    Goi sau khi SchedulerAgent chay xong.
    """
    logger.info("Gui thong bao buoi sang...")
    try:
        from services.database import get_latest_daily_plan
        import json

        today = today_vn()
        plan = await get_latest_daily_plan(today)

        if not plan:
            await send_message(
                f"SANG {format_date_vn(today)}\n\n"
                "Chua co ke hoach hom nay. SchedulerAgent co the chua chay."
            )
            return

        plan_json = plan.get("plan_json", {})
        if isinstance(plan_json, str):
            plan_json = json.loads(plan_json)

        weekday = WEEKDAY_NAMES_FULL[today.weekday()]
        lines = [
            f"LICH {weekday.upper()} {format_date_vn(today)}",
            "",
        ]

        tasks = plan_json.get("daily_tasks", [])
        if tasks:
            lines.append(f"--- {len(tasks)} NHIEM VU ---")
            for t in sorted(tasks, key=lambda x: x.get("priority_rank", 99)):
                rank = t.get("priority_rank", "?")
                slot = t.get("time_slot", "?")
                title = t.get("title", "?")
                dur = t.get("duration_minutes", "?")
                lines.append(f"{rank}. [{slot}] {title} ({dur}p)")

        risks = plan_json.get("risks", [])
        if risks:
            lines.append("\n--- LUU Y ---")
            for r in risks:
                lines.append(f"- {r}")

        questions = plan_json.get("questions_for_user", [])
        if questions:
            lines.append("\n--- CAN XAC NHAN ---")
            for q in questions:
                lines.append(f"- {q}")

        await send_message("\n".join(lines))
        logger.info("Da gui thong bao buoi sang")

    except Exception as e:
        logger.error("Loi gui thong bao buoi sang: %s", e, exc_info=True)


async def send_afternoon_reminder():
    """
    Gui nhac buoi chieu vao 12:00.
    Liet ke tasks con lai chua xong.
    """
    logger.info("Gui nhac buoi chieu...")
    try:
        from services.database import get_latest_daily_plan
        import json

        today = today_vn()
        plan = await get_latest_daily_plan(today)
        if not plan:
            return

        plan_json = plan.get("plan_json", {})
        if isinstance(plan_json, str):
            plan_json = json.loads(plan_json)

        tasks = plan_json.get("daily_tasks", [])
        # Loc tasks buoi chieu (time_slot bat dau tu 12:00 tro di)
        afternoon_tasks = []
        for t in tasks:
            slot = t.get("time_slot", "")
            if slot:
                start_hour = slot.split(":")[0].strip()
                try:
                    if int(start_hour) >= 12:
                        afternoon_tasks.append(t)
                except ValueError:
                    pass

        if not afternoon_tasks:
            # Khong co task buoi chieu -> thong bao tat ca tasks con lai
            await send_message(
                f"GIUA NGAY {format_date_vn(today)}\n\n"
                "Khong co nhiem vu buoi chieu duoc len lich."
            )
            return

        lines = [
            f"GIUA NGAY {format_date_vn(today)}",
            f"",
            f"--- {len(afternoon_tasks)} NHIEM VU BUOI CHIEU ---",
        ]
        for t in sorted(afternoon_tasks, key=lambda x: x.get("priority_rank", 99)):
            rank = t.get("priority_rank", "?")
            slot = t.get("time_slot", "?")
            title = t.get("title", "?")
            dur = t.get("duration_minutes", "?")
            lines.append(f"{rank}. [{slot}] {title} ({dur}p)")

        lines.append("")
        lines.append("Phan hoi neu can dieu chinh.")

        await send_message("\n".join(lines))
        logger.info("Da gui nhac buoi chieu")

    except Exception as e:
        logger.error("Loi gui nhac buoi chieu: %s", e, exc_info=True)


async def send_evening_review():
    """
    Gui review cuoi ngay vao 21:00.
    Tom tat: nhung gi da xong, chua xong, de xuat.
    """
    logger.info("Gui review cuoi ngay...")
    try:
        from services.database import get_latest_daily_plan, get_recent_task_logs
        import json

        today = today_vn()
        plan = await get_latest_daily_plan(today)
        if not plan:
            return

        plan_json = plan.get("plan_json", {})
        if isinstance(plan_json, str):
            plan_json = json.loads(plan_json)

        tasks = plan_json.get("daily_tasks", [])
        total = len(tasks)

        # Lay task logs hom nay de kiem tra trang thai
        logs = await get_recent_task_logs(days=1)
        completed_names = set()
        for log in logs:
            if log.get("status") == "completed":
                completed_names.add(log.get("task_name", "").lower())

        done_tasks = []
        remaining_tasks = []
        for t in tasks:
            title = t.get("title", "")
            if title.lower() in completed_names:
                done_tasks.append(t)
            else:
                remaining_tasks.append(t)

        lines = [
            f"TONG KET NGAY {format_date_vn(today)}",
            "",
        ]

        if done_tasks:
            lines.append(f"--- DA HOAN THANH ({len(done_tasks)}/{total}) ---")
            for t in done_tasks:
                lines.append(f"  [x] {t.get('title', '?')}")

        if remaining_tasks:
            lines.append(f"\n--- CHUA XONG ({len(remaining_tasks)}/{total}) ---")
            for t in remaining_tasks:
                slot = t.get("time_slot", "?")
                lines.append(f"  [ ] [{slot}] {t.get('title', '?')}")

        if remaining_tasks:
            lines.append("\nNhung task chua xong se duoc xem xet lai ngay mai.")
            lines.append("Nhan tin neu muon dieu chinh.")

        if not done_tasks and not remaining_tasks:
            lines.append("Khong co du lieu de tong ket.")

        await send_message("\n".join(lines))
        logger.info("Da gui review cuoi ngay")

    except Exception as e:
        logger.error("Loi gui review cuoi ngay: %s", e, exc_info=True)


# ============================================================
# APSCHEDULER WRAPPERS (sync -> async)
# ============================================================

def run_morning_summary():
    """Wrapper sync cho APScheduler."""
    logger.info("APScheduler trigger: morning summary")
    try:
        asyncio.run(send_morning_summary())
    except Exception as e:
        logger.error("Loi morning summary: %s", e, exc_info=True)


def run_afternoon_reminder():
    """Wrapper sync cho APScheduler."""
    logger.info("APScheduler trigger: afternoon reminder")
    try:
        asyncio.run(send_afternoon_reminder())
    except Exception as e:
        logger.error("Loi afternoon reminder: %s", e, exc_info=True)


def run_evening_review():
    """Wrapper sync cho APScheduler."""
    logger.info("APScheduler trigger: evening review")
    try:
        asyncio.run(send_evening_review())
    except Exception as e:
        logger.error("Loi evening review: %s", e, exc_info=True)
