"""
SyncAgent - Dong bo trang thai giua Google Tasks, Google Sheet va Postgres.

Chay moi 15 phut qua APScheduler.

Moi lan chay:
1. Doc trang thai hien tai tu Google Tasks (cac list hom nay)
2. Doc trang thai hien tai tu Google Sheet (cot Status)
3. So sanh voi sync_states snapshot truoc do trong Postgres
4. Phat hien thay doi:
   - Task tick completed trong Tasks -> cap nhat Postgres task_logs
   - Task danh "Done" trong Sheet -> cap nhat Postgres task_logs
   - Task moi duoc them -> log
5. Luu sync_states snapshot moi vao Postgres
6. Canh bao: task priority High, due trong 24h, chua done -> gui Telegram
"""

import asyncio
import json
import logging
from datetime import date, timedelta

from config import settings
from utils.time_utils import today_vn, format_date_vn, now_vn

logger = logging.getLogger("zertdoo.sync")


# ============================================================
# THU THAP TRANG THAI HIEN TAI
# ============================================================

def _snapshot_google_tasks() -> dict:
    """
    Tao snapshot trang thai tu Google Tasks.
    Chi doc task lists co ten dang ngay (VD: "CN 01/03").

    Returns:
        dict: {
            "tasks": [
                {"title": "...", "status": "needsAction|completed", "task_id": "...", "task_list_id": "...", "notes": "..."},
            ],
            "timestamp": "...",
        }
    """
    from services.google_tasks import get_all_task_lists, get_tasks_from_list

    today = today_vn()
    today_list_title = format_date_vn(today)

    all_lists = get_all_task_lists()
    tasks_snapshot = []

    for tl in all_lists:
        # Doc tat ca lists (khong chi hom nay) de bat hoan thanh bat ky list nao
        try:
            tasks = get_tasks_from_list(
                task_list_id=tl["id"],
                task_list_title=tl["title"],
                show_completed=True,
                show_hidden=True,
            )
            for t in tasks:
                tasks_snapshot.append({
                    "title": t.title,
                    "status": t.status,
                    "task_id": t.task_id,
                    "task_list_id": t.task_list_id,
                    "task_list_title": tl["title"],
                    "notes": t.notes,
                    "updated": t.updated or "",
                })
        except Exception as e:
            logger.warning("Loi doc task list '%s': %s", tl["title"], e)

    now = now_vn()
    return {
        "tasks": tasks_snapshot,
        "timestamp": now.isoformat(),
    }


def _snapshot_google_sheets() -> dict:
    """
    Tao snapshot trang thai tu Google Sheets.

    Returns:
        dict: {
            "tasks": [
                {"sheet_name": "...", "category": "...", "task": "...", "status": "...", "priority": "...", "due_date": "..."},
            ],
            "timestamp": "...",
        }
    """
    from services.google_sheets import read_all_sheets

    all_tasks = read_all_sheets()
    tasks_snapshot = []

    for t in all_tasks:
        tasks_snapshot.append({
            "sheet_name": t.sheet_name,
            "category": t.category,
            "task": t.task,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date or "",
            "start_date": t.start_date or "",
            "notes": t.notes,
        })

    now = now_vn()
    return {
        "tasks": tasks_snapshot,
        "timestamp": now.isoformat(),
    }


# ============================================================
# SO SANH VA PHAT HIEN THAY DOI
# ============================================================

def _detect_tasks_changes(old_snapshot: dict, new_snapshot: dict) -> list[dict]:
    """
    So sanh 2 Google Tasks snapshots, phat hien thay doi.

    Returns:
        list cac thay doi: [{"type": "completed|uncompleted|new|removed", "task": {...}}]
    """
    changes = []

    # Index tasks cu theo task_id
    old_by_id = {}
    for t in old_snapshot.get("tasks", []):
        old_by_id[t["task_id"]] = t

    # Index tasks moi theo task_id
    new_by_id = {}
    for t in new_snapshot.get("tasks", []):
        new_by_id[t["task_id"]] = t

    # Kiem tra thay doi
    for task_id, new_task in new_by_id.items():
        old_task = old_by_id.get(task_id)

        if old_task is None:
            # Task moi
            changes.append({
                "type": "new_task",
                "source": "google_tasks",
                "task": new_task,
            })
        elif old_task["status"] != new_task["status"]:
            if new_task["status"] == "completed":
                changes.append({
                    "type": "completed",
                    "source": "google_tasks",
                    "task": new_task,
                })
            else:
                changes.append({
                    "type": "uncompleted",
                    "source": "google_tasks",
                    "task": new_task,
                })

    # Task bi xoa
    for task_id, old_task in old_by_id.items():
        if task_id not in new_by_id:
            changes.append({
                "type": "removed",
                "source": "google_tasks",
                "task": old_task,
            })

    return changes


def _detect_sheets_changes(old_snapshot: dict, new_snapshot: dict) -> list[dict]:
    """
    So sanh 2 Google Sheets snapshots, phat hien thay doi status.

    Returns:
        list cac thay doi
    """
    changes = []

    # Key = (sheet_name, task_name) vi Sheet khong co ID
    def _key(t):
        return (t.get("sheet_name", ""), t.get("task", ""))

    old_by_key = {}
    for t in old_snapshot.get("tasks", []):
        old_by_key[_key(t)] = t

    new_by_key = {}
    for t in new_snapshot.get("tasks", []):
        new_by_key[_key(t)] = t

    for key, new_task in new_by_key.items():
        old_task = old_by_key.get(key)

        if old_task is None:
            changes.append({
                "type": "new_task",
                "source": "google_sheets",
                "task": new_task,
            })
        elif old_task.get("status", "").lower() != new_task.get("status", "").lower():
            old_status = old_task.get("status", "").lower()
            new_status = new_task.get("status", "").lower()

            if new_status in ("done", "completed"):
                changes.append({
                    "type": "completed",
                    "source": "google_sheets",
                    "task": new_task,
                })
            elif old_status in ("done", "completed") and new_status not in ("done", "completed"):
                changes.append({
                    "type": "uncompleted",
                    "source": "google_sheets",
                    "task": new_task,
                })
            else:
                changes.append({
                    "type": "status_changed",
                    "source": "google_sheets",
                    "task": new_task,
                    "old_status": old_status,
                    "new_status": new_status,
                })

    return changes


# ============================================================
# DONG BO VA CAP NHAT
# ============================================================

async def _sync_completion_to_db(changes: list[dict]):
    """
    Cap nhat task_logs trong Postgres khi phat hien task hoan thanh.
    """
    from services.database import get_recent_task_logs, update_task_status

    if not changes:
        return

    # Lay task_logs gan day de match
    recent_logs = await get_recent_task_logs(days=7)
    logs_by_name = {}
    for log in recent_logs:
        name = log.get("task_name", "").lower()
        logs_by_name.setdefault(name, []).append(log)

    updated_count = 0
    for change in changes:
        if change["type"] != "completed":
            continue

        task_info = change["task"]
        task_name = ""

        if change["source"] == "google_tasks":
            # Title trong Google Tasks co dang "[1] Ten task"
            raw_title = task_info.get("title", "")
            # Bo prefix [N]
            if raw_title.startswith("[") and "]" in raw_title:
                task_name = raw_title.split("]", 1)[1].strip()
            else:
                task_name = raw_title
        elif change["source"] == "google_sheets":
            task_name = task_info.get("task", "")

        if not task_name:
            continue

        # Tim trong task_logs
        matching_logs = logs_by_name.get(task_name.lower(), [])
        for log in matching_logs:
            if log.get("status") not in ("done", "completed"):
                await update_task_status(log["id"], "done")
                updated_count += 1
                logger.info(
                    "Dong bo hoan thanh: '%s' (task_log id=%d, source=%s)",
                    task_name, log["id"], change["source"],
                )
                break

    if updated_count:
        logger.info("Da dong bo %d tasks thanh 'done' trong Postgres", updated_count)


# ============================================================
# CANH BAO DEADLINE
# ============================================================

async def _check_deadline_alerts(sheets_snapshot: dict):
    """
    Kiem tra tasks priority High, due trong 24h, chua done.
    Gui Telegram canh bao.
    """
    now = now_vn()
    today = today_vn()
    tomorrow = today + timedelta(days=1)
    alerts = []

    for t in sheets_snapshot.get("tasks", []):
        priority = t.get("priority", "").lower()
        status = t.get("status", "").lower()
        due_str = t.get("due_date", "")

        # Chi canh bao High priority chua done
        if priority != "high" or status in ("done", "completed"):
            continue

        if not due_str:
            continue

        # Parse due date (co the la DD/MM/YYYY hoac YYYY-MM-DD)
        due_date = _parse_date(due_str)
        if due_date is None:
            continue

        # Due trong 24h
        if due_date <= tomorrow:
            task_name = t.get("task", "?")
            sheet_name = t.get("sheet_name", "?")
            days_left = (due_date - today).days

            if days_left < 0:
                urgency = f"QUÁ HẠN {abs(days_left)} NGÀY"
            elif days_left == 0:
                urgency = "ĐẾN HẠN HÔM NAY"
            else:
                urgency = f"CÒN {days_left} NGÀY"

            alerts.append(f"- [{sheet_name}] {task_name} ({urgency})")

    if alerts:
        from services.telegram_sender import send_message
        msg = "CẢNH BÁO DEADLINE (Priority High):\n\n" + "\n".join(alerts)
        await send_message(msg)
        logger.info("Da gui %d canh bao deadline", len(alerts))


def _parse_date(date_str: str):
    """Parse date string linh hoat."""
    from datetime import datetime as dt
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return dt.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ============================================================
# MAIN: RUN
# ============================================================

async def run() -> dict:
    """
    Chay SyncAgent 1 lan.

    Returns:
        dict: {
            "tasks_changes": int,
            "sheets_changes": int,
            "db_synced": int,
            "alerts_sent": int,
        }
    """
    logger.info("SyncAgent bat dau...")

    loop = asyncio.get_event_loop()

    # 1. Thu thap snapshots (song song)
    logger.info("Thu thap snapshots tu Google Tasks va Sheets...")
    tasks_snap_future = loop.run_in_executor(None, _snapshot_google_tasks)
    sheets_snap_future = loop.run_in_executor(None, _snapshot_google_sheets)
    tasks_snapshot, sheets_snapshot = await asyncio.gather(
        tasks_snap_future, sheets_snap_future
    )
    logger.info(
        "Snapshots: %d tasks tu Google Tasks, %d tasks tu Sheets",
        len(tasks_snapshot["tasks"]), len(sheets_snapshot["tasks"]),
    )

    # 2. Lay snapshots cu tu Postgres
    from services.database import get_latest_sync_state, save_sync_state

    old_tasks_state = await get_latest_sync_state("google_tasks")
    old_sheets_state = await get_latest_sync_state("google_sheets")

    old_tasks_snap = {}
    if old_tasks_state:
        raw = old_tasks_state.get("state_snapshot", {})
        old_tasks_snap = json.loads(raw) if isinstance(raw, str) else raw

    old_sheets_snap = {}
    if old_sheets_state:
        raw = old_sheets_state.get("state_snapshot", {})
        old_sheets_snap = json.loads(raw) if isinstance(raw, str) else raw

    # 3. Detect changes
    tasks_changes = []
    sheets_changes = []

    if old_tasks_snap:
        tasks_changes = _detect_tasks_changes(old_tasks_snap, tasks_snapshot)
        if tasks_changes:
            logger.info("Google Tasks: %d thay doi", len(tasks_changes))
            for c in tasks_changes:
                title = c["task"].get("title", "?")
                logger.info("  - %s: %s", c["type"], title)
    else:
        logger.info("Lan dau sync Google Tasks, khong co snapshot cu")

    if old_sheets_snap:
        sheets_changes = _detect_sheets_changes(old_sheets_snap, sheets_snapshot)
        if sheets_changes:
            logger.info("Google Sheets: %d thay doi", len(sheets_changes))
            for c in sheets_changes:
                task_name = c["task"].get("task", "?")
                logger.info("  - %s: %s", c["type"], task_name)
    else:
        logger.info("Lan dau sync Google Sheets, khong co snapshot cu")

    # 4. Dong bo completions vao Postgres
    all_changes = tasks_changes + sheets_changes
    completed_changes = [c for c in all_changes if c["type"] == "completed"]
    await _sync_completion_to_db(completed_changes)

    # 5. Gui thong bao thay doi quan trong qua Telegram
    notify_changes = [
        c for c in all_changes
        if c["type"] in ("completed", "new_task", "removed")
    ]
    if notify_changes:
        await _notify_changes(notify_changes)

    # 6. Kiem tra deadline alerts
    alerts_count = 0
    try:
        await _check_deadline_alerts(sheets_snapshot)
    except Exception as e:
        logger.error("Loi kiem tra deadline: %s", e)

    # 7. Luu snapshots moi
    await save_sync_state("google_tasks", tasks_snapshot)
    await save_sync_state("google_sheets", sheets_snapshot)
    logger.info("Da luu sync snapshots moi")

    # 8. Log
    try:
        from services.database import log_agent
        await log_agent(
            agent_name="sync",
            input_summary=f"Tasks: {len(tasks_snapshot['tasks'])}, Sheets: {len(sheets_snapshot['tasks'])}",
            output_summary=f"Changes: tasks={len(tasks_changes)}, sheets={len(sheets_changes)}, synced={len(completed_changes)}",
        )
    except Exception:
        pass

    result = {
        "tasks_changes": len(tasks_changes),
        "sheets_changes": len(sheets_changes),
        "db_synced": len(completed_changes),
        "total_tasks_snapshot": len(tasks_snapshot["tasks"]),
        "total_sheets_snapshot": len(sheets_snapshot["tasks"]),
    }
    logger.info("SyncAgent hoan thanh: %s", result)
    return result


async def _notify_changes(changes: list[dict]):
    """
    Luu thong bao thay doi vao DB va gui web push notification.
    Khong gui Telegram de giam tai.
    """
    from services.database import save_web_notification
    from services.web_push import send_push_notification

    lines: list[str] = []

    for c in changes[:10]:  # Gioi han 10 thay doi moi lan
        task = c["task"]
        source = c["source"].replace("google_", "").replace("_", " ").title()
        ctype = c["type"]

        if ctype == "completed":
            name = task.get("title", "") or task.get("task", "?")
            lines.append(f"[x] {name} (tu {source})")
        elif ctype == "new_task":
            name = task.get("title", "") or task.get("task", "?")
            lines.append(f"[+] {name} (them moi tu {source})")
        elif ctype == "removed":
            name = task.get("title", "") or task.get("task", "?")
            lines.append(f"[-] {name} (xoa tu {source})")

    if len(changes) > 10:
        lines.append(f"... va {len(changes) - 10} thay doi khac")

    body = "\n".join(lines)

    # Luu vao DB de hien thi tren dashboard
    try:
        await save_web_notification(
            title=f"Dong bo: {len(changes)} thay doi",
            body=body,
        )
    except Exception as e:
        logger.warning("Loi luu web notification: %s", e)

    # Gui web push neu co subscription
    try:
        sent = await send_push_notification(
            title=f"Dong bo: {len(changes)} thay doi",
            body=body,
        )
        logger.info("Da gui web push cho %d subscriptions", sent)
    except Exception as e:
        logger.warning("Loi gui web push: %s", e)

    logger.info("Da xu ly %d thay doi -> web push (Telegram da bo qua)", len(changes))


# ============================================================
# APSCHEDULER WRAPPER (async - dung voi AsyncIOScheduler)
# ============================================================

async def run_scheduled_async():
    """Async wrapper cho AsyncIOScheduler."""
    logger.info("APScheduler trigger: SyncAgent...")
    try:
        result = await run()
        logger.info("SyncAgent scheduled run xong: %s", result)
    except Exception as e:
        logger.error("SyncAgent scheduled loi: %s", e, exc_info=True)
        # Gui Telegram thong bao loi
        try:
            from services.telegram_sender import send_message
            await send_message(
                f"[LỖI] SyncAgent thất bại: {type(e).__name__}: {e}"
            )
        except Exception:
            pass
