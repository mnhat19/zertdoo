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
# HELPER: TEN TASK VA FUZZY MATCH
# ============================================================

def _clean_task_name(title: str) -> str:
    """
    Chuan hoa ten task:
    - Bo prefix [N] (Google Tasks dung de danh so thu tu)
    - Strip whitespace
    """
    t = (title or "").strip()
    if t.startswith("[") and "]" in t:
        t = t.split("]", 1)[1].strip()
    return t


def _names_match(name_a: str, name_b: str) -> bool:
    """
    Kiem tra 2 ten co khop nhau khong (fuzzy).
    - Exact match (case-insensitive)
    - 1 ten chua ten kia
    - Tat ca cac tu cua ten ngan co mat trong ten dai
    """
    a = _clean_task_name(name_a).lower()
    b = _clean_task_name(name_b).lower()
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    # So sanh word-level: tat ca tu cua ten ngan phai co trong ten dai
    words_a = set(a.split())
    words_b = set(b.split())
    shorter = words_a if len(words_a) <= len(words_b) else words_b
    longer = words_b if shorter is words_a else words_a
    if len(shorter) >= 2 and shorter.issubset(longer):
        return True
    return False


def _dedup_changes(changes: list[dict]) -> list[dict]:
    """
    Loai bo cac thay doi trung lap cung task, cung type tu nhieu nguon.
    Giu lai ban ghi dau tien.
    """
    seen: set = set()
    result = []
    for c in changes:
        task = c["task"]
        raw_name = task.get("title", "") or task.get("task", "")
        clean = _clean_task_name(raw_name).lower()
        key = (c["type"], clean)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


# ============================================================
# DONG BO VA CAP NHAT
# ============================================================

async def _sync_completion_to_db(changes: list[dict]) -> int:
    """
    Cap nhat task_logs trong Postgres khi phat hien task hoan thanh.
    Su dung fuzzy name matching de tang do chinh xac.

    Returns:
        So task_logs da cap nhat.
    """
    from services.database import get_recent_task_logs, update_task_status

    if not changes:
        return 0

    # Lay task_logs trong 14 ngay (mo rong tu 7 de bat nhiem vu dai han)
    recent_logs = await get_recent_task_logs(days=14)
    updated_count = 0

    for change in changes:
        if change["type"] != "completed":
            continue

        task_info = change["task"]
        raw_name = task_info.get("title", "") or task_info.get("task", "")
        task_name = _clean_task_name(raw_name)
        if not task_name:
            continue

        # Tim log chua hoan thanh khop ten nhat
        for log in recent_logs:
            log_name = log.get("task_name", "")
            if _names_match(task_name, log_name) and log.get("status") not in ("done", "completed"):
                await update_task_status(log["id"], "done")
                updated_count += 1
                logger.info(
                    "Sync DB done: '%s' (task_log id=%d, nguon=%s)",
                    task_name, log["id"], change["source"],
                )
                break  # Chi cap nhat 1 log cho 1 task

    if updated_count:
        logger.info("Da dong bo %d tasks thanh 'done' trong Postgres", updated_count)
    return updated_count


async def _sync_tasks_completion_to_sheet(
    completed_from_tasks: list[dict],
    sheets_snapshot: dict,
    loop,
) -> int:
    """
    Khi task duoc tick trong Google Tasks: cap nhat cot F -> 'Done' trong Sheet.

    Sau khi ghi, cap nhat in-memory sheets_snapshot de tranh phat hien lai
    thanh 'completed' tu Sheet o lan sync tiep theo.

    Returns:
        So task da cap nhat vao Sheet.
    """
    from services.google_sheets import update_task_status_in_sheet

    sheet_tasks = sheets_snapshot.get("tasks", [])
    updated = 0

    for change in completed_from_tasks:
        raw_title = change["task"].get("title", "")
        task_name = _clean_task_name(raw_title)
        if not task_name:
            continue

        # Tim trong sheets_snapshot
        matched: dict | None = None
        for st in sheet_tasks:
            if _names_match(task_name, st.get("task", "")):
                matched = st
                break

        if not matched:
            logger.debug("Khong tim thay '%s' trong Sheet snapshot", task_name)
            continue

        # Bo qua neu Sheet da la Done
        if matched.get("status", "").lower() in ("done", "completed"):
            logger.debug("Sheet '%s' da Done, bo qua", matched["task"])
            continue

        # Ghi len Google Sheet
        try:
            success = await loop.run_in_executor(
                None,
                update_task_status_in_sheet,
                matched["sheet_name"],
                matched["task"],
                "Done",
            )
            if success:
                # Cap nhat in-memory de snapshot luu dung trang thai moi
                matched["status"] = "Done"
                updated += 1
                logger.info(
                    "Tasks->Sheet: '%s' (sheet=%s) -> Done",
                    matched["task"], matched["sheet_name"],
                )
            else:
                logger.warning("Khong cap nhat duoc Sheet cho '%s'", task_name)
        except Exception as e:
            logger.warning("Loi cap nhat Sheet cho '%s': %s", task_name, e)

    if updated:
        logger.info("Tasks->Sheet: da cap nhat %d tasks thanh Done", updated)
    return updated


async def _sync_sheets_completion_to_tasks(
    completed_from_sheets: list[dict],
    tasks_snapshot: dict,
    loop,
) -> int:
    """
    Khi task bang 'Done' trong Sheet: tim task tuong ung trong Google Tasks
    va danh dau completed.

    Cap nhat in-memory tasks_snapshot sau khi ghi de tranh phat hien lai.

    Returns:
        So task da cap nhat trong Google Tasks.
    """
    from services.google_tasks import complete_task

    google_tasks = tasks_snapshot.get("tasks", [])
    updated = 0

    for change in completed_from_sheets:
        task_name = change["task"].get("task", "")
        if not task_name:
            continue

        # Tim trong tasks_snapshot
        matched: dict | None = None
        for gt in google_tasks:
            clean_title = _clean_task_name(gt.get("title", ""))
            if _names_match(task_name, clean_title):
                matched = gt
                break

        if not matched:
            logger.debug("Khong tim thay '%s' trong Tasks snapshot", task_name)
            continue

        # Bo qua neu Tasks da completed
        if matched.get("status", "") == "completed":
            continue

        tl_id = matched.get("task_list_id", "")
        t_id = matched.get("task_id", "")
        if not tl_id or not t_id:
            continue

        try:
            success = await loop.run_in_executor(None, complete_task, tl_id, t_id)
            if success:
                matched["status"] = "completed"
                updated += 1
                logger.info(
                    "Sheet->Tasks: '%s' (list=%s) -> completed",
                    matched["title"], matched.get("task_list_title", "?"),
                )
            else:
                logger.warning("Khong danh dau completed Tasks cho '%s'", task_name)
        except Exception as e:
            logger.warning("Loi danh dau Tasks cho '%s': %s", task_name, e)

    if updated:
        logger.info("Sheet->Tasks: da cap nhat %d tasks thanh completed", updated)
    return updated


async def _sync_status_changes_to_db(status_changes: list[dict]) -> int:
    """
    Khi trang thai task trong Sheet thay doi (Reschedule, Pending, Skip, ...):
    cap nhat Postgres task_logs cho phu hop.

    Returns:
        So records da cap nhat.
    """
    from services.database import get_recent_task_logs, update_task_status

    if not status_changes:
        return 0

    recent_logs = await get_recent_task_logs(days=14)
    updated = 0

    # Map tu Sheet status sang DB status
    STATUS_MAP = {
        "pending":     "pending",
        "reschedule":  "rescheduled",
        "rescheduled": "rescheduled",
        "skip":        "skipped",
        "skipped":     "skipped",
        "done":        "done",
        "completed":   "done",
        "":            "pending",
    }

    for change in status_changes:
        task_name = change["task"].get("task", "")
        new_status_raw = change.get("new_status", "").lower()
        db_status = STATUS_MAP.get(new_status_raw, new_status_raw or "pending")

        for log in recent_logs:
            log_name = log.get("task_name", "")
            if _names_match(task_name, log_name):
                current = log.get("status", "")
                if current != db_status:
                    await update_task_status(log["id"], db_status)
                    logger.info(
                        "Sheet status_changed -> DB: '%s' %s -> %s",
                        task_name, current, db_status,
                    )
                    updated += 1
                break  # Mot task chi can cap nhat 1 lan

    if updated:
        logger.info("Da dong bo %d status_changed tu Sheet vao Postgres", updated)
    return updated


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

    # 4. Phan loai cac thay doi
    all_changes = tasks_changes + sheets_changes
    completed_changes      = [c for c in all_changes   if c["type"] == "completed"]
    tasks_completed        = [c for c in tasks_changes  if c["type"] == "completed"]
    sheets_completed       = [c for c in sheets_changes if c["type"] == "completed"]
    sheets_status_changed  = [c for c in sheets_changes if c["type"] == "status_changed"]

    # 4a. Dong bo completions -> Postgres (tat ca nguon)
    db_synced = await _sync_completion_to_db(completed_changes)

    # 4b. Tasks tick done -> cap nhat 'Done' vao Sheet
    #     (in-memory sheets_snapshot se duoc cap nhat de snapshot luu dung)
    tasks_to_sheet = 0
    try:
        tasks_to_sheet = await _sync_tasks_completion_to_sheet(
            tasks_completed, sheets_snapshot, loop
        )
    except Exception as e:
        logger.error("Loi sync Tasks->Sheet: %s", e, exc_info=True)

    # 4c. Sheet Done -> danh dau completed trong Google Tasks
    #     (in-memory tasks_snapshot se duoc cap nhat)
    sheets_to_tasks = 0
    try:
        sheets_to_tasks = await _sync_sheets_completion_to_tasks(
            sheets_completed, tasks_snapshot, loop
        )
    except Exception as e:
        logger.error("Loi sync Sheet->Tasks: %s", e, exc_info=True)

    # 4d. Sheet status_changed (Reschedule/Pending/Skip) -> Postgres
    try:
        await _sync_status_changes_to_db(sheets_status_changed)
    except Exception as e:
        logger.error("Loi sync status_changed->DB: %s", e, exc_info=True)

    # 5. Thong bao (dedup cung task tu nhieu nguon)
    raw_notify = [
        c for c in all_changes
        if c["type"] in ("completed", "new_task", "removed", "status_changed")
    ]
    notify_changes = _dedup_changes(raw_notify)
    if notify_changes:
        await _notify_changes(notify_changes)

    # 6. Luu snapshots (ke ca phan da duoc cap nhat in-memory o 4b/4c)
    # (Deadline alert da chuyen sang send_risk_alert() trong APScheduler)
    await save_sync_state("google_tasks", tasks_snapshot)
    await save_sync_state("google_sheets", sheets_snapshot)
    logger.info("Da luu sync snapshots moi")

    # 7. Log
    try:
        from services.database import log_agent
        await log_agent(
            agent_name="sync",
            input_summary=(
                f"Tasks: {len(tasks_snapshot['tasks'])}, "
                f"Sheets: {len(sheets_snapshot['tasks'])}"
            ),
            output_summary=(
                f"Changes: tasks={len(tasks_changes)}, sheets={len(sheets_changes)} | "
                f"DB synced={db_synced}, Tasks->Sheet={tasks_to_sheet}, "
                f"Sheet->Tasks={sheets_to_tasks}"
            ),
        )
    except Exception:
        pass

    result = {
        "tasks_changes": len(tasks_changes),
        "sheets_changes": len(sheets_changes),
        "db_synced": db_synced,
        "tasks_to_sheet": tasks_to_sheet,
        "sheets_to_tasks": sheets_to_tasks,
        "total_tasks_snapshot": len(tasks_snapshot["tasks"]),
        "total_sheets_snapshot": len(sheets_snapshot["tasks"]),
    }
    logger.info("SyncAgent hoan thanh: %s", result)
    return result


async def _notify_changes(changes: list[dict]):
    """
    Luu thong bao thay doi vao DB va gui web push notification.
    Khong gui Telegram de giam tai (tru cac loi nghiem trong).
    """
    from services.database import save_web_notification
    from services.web_push import send_push_notification

    lines: list[str] = []

    for c in changes[:15]:  # Gioi han 15 thay doi moi lan
        task = c["task"]
        source = c["source"].replace("google_", "").replace("_", " ").title()
        ctype = c["type"]
        name = _clean_task_name(task.get("title", "") or task.get("task", "?"))

        if ctype == "completed":
            lines.append(f"[x] {name} (tu {source})")
        elif ctype == "new_task":
            lines.append(f"[+] {name} (them moi tu {source})")
        elif ctype == "removed":
            lines.append(f"[-] {name} (xoa tu {source})")
        elif ctype == "status_changed":
            old_s = c.get("old_status", "?").capitalize()
            new_s = c.get("new_status", "?").capitalize()
            lines.append(f"[~] {name} ({source}: {old_s} -> {new_s})")

    if len(changes) > 15:
        lines.append(f"... va {len(changes) - 15} thay doi khac")

    if not lines:
        return

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
