"""
Google Tasks reader/writer cho Zertdoo.
Doc va quan ly task lists va tasks.
"""

import logging
from typing import Optional

from models.schemas import GoogleTask
from services.google_auth import build_service

logger = logging.getLogger("zertdoo.google_tasks")


def _get_tasks_service():
    """Tao Google Tasks API service."""
    return build_service("tasks", "v1")


# ============================================================
# READ
# ============================================================

def get_all_task_lists() -> list[dict]:
    """
    Lay danh sach tat ca task lists.

    Returns:
        list[dict] voi keys: id, title, updated
    """
    service = _get_tasks_service()
    results = service.tasklists().list(maxResults=100).execute()
    items = results.get("items", [])
    logger.info("Tim thay %d task lists.", len(items))
    return [
        {
            "id": item["id"],
            "title": item.get("title", ""),
            "updated": item.get("updated", ""),
        }
        for item in items
    ]


def get_tasks_from_list(
    task_list_id: str,
    task_list_title: str = "",
    show_completed: bool = True,
    show_hidden: bool = True,
) -> list[GoogleTask]:
    """
    Doc tat ca tasks tu 1 task list.

    Args:
        task_list_id: ID cua task list
        task_list_title: Ten task list (de gan vao model)
        show_completed: Hien thi tasks da hoan thanh
        show_hidden: Hien thi tasks bi an

    Returns:
        list[GoogleTask]
    """
    service = _get_tasks_service()
    tasks = []
    page_token = None

    while True:
        result = service.tasks().list(
            tasklist=task_list_id,
            maxResults=100,
            showCompleted=show_completed,
            showHidden=show_hidden,
            pageToken=page_token,
        ).execute()

        for item in result.get("items", []):
            tasks.append(GoogleTask(
                task_id=item["id"],
                task_list_id=task_list_id,
                task_list_title=task_list_title,
                title=item.get("title", ""),
                notes=item.get("notes", ""),
                status=item.get("status", "needsAction"),
                due=item.get("due"),
                completed=item.get("completed"),
                position=item.get("position", ""),
                updated=item.get("updated"),
            ))

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    logger.debug("Task list '%s': %d tasks.", task_list_title, len(tasks))
    return tasks


def read_all_tasks() -> list[GoogleTask]:
    """
    Doc tat ca tasks tu tat ca task lists.

    Returns:
        list[GoogleTask] tu moi task list gop lai
    """
    task_lists = get_all_task_lists()
    all_tasks: list[GoogleTask] = []

    for tl in task_lists:
        try:
            tasks = get_tasks_from_list(
                task_list_id=tl["id"],
                task_list_title=tl["title"],
            )
            all_tasks.extend(tasks)
        except Exception as e:
            logger.error("Loi khi doc task list '%s': %s", tl["title"], e)

    logger.info("Tong cong: %d tasks tu %d lists.", len(all_tasks), len(task_lists))
    return all_tasks


def read_tasks_summary() -> str:
    """
    Doc tat ca tasks va tra ve dang text tom tat cho LLM.

    Returns:
        str
    """
    all_tasks = read_all_tasks()

    if not all_tasks:
        return "Khong co task nao trong Google Tasks."

    # Nhom theo task list
    by_list: dict[str, list[GoogleTask]] = {}
    for t in all_tasks:
        by_list.setdefault(t.task_list_title, []).append(t)

    lines = []
    for list_title, tasks in by_list.items():
        pending = [t for t in tasks if t.status == "needsAction"]
        lines.append(f"\n[{list_title}] ({len(tasks)} tasks, {len(pending)} chua xong)")
        for t in tasks:
            status_mark = "[x]" if t.status == "completed" else "[ ]"
            due_str = f" | Due: {t.due[:10]}" if t.due else ""
            lines.append(f"  {status_mark} {t.title}{due_str}")

    return "\n".join(lines)


# ============================================================
# WRITE (se dung o Giai doan 3+)
# ============================================================

def create_task_list(title: str) -> dict:
    """Tao task list moi. Tra ve dict voi id va title."""
    service = _get_tasks_service()
    result = service.tasklists().insert(body={"title": title}).execute()
    logger.info("Da tao task list: '%s' (id=%s)", title, result["id"])
    return {"id": result["id"], "title": result.get("title", title)}


def create_task(
    task_list_id: str,
    title: str,
    notes: str = "",
    due: str = None,
) -> dict:
    """
    Tao 1 task trong task list.

    Args:
        task_list_id: ID cua task list
        title: Tieu de task
        notes: Ghi chu
        due: Han chot (RFC 3339 format, VD: '2026-03-01T00:00:00.000Z')

    Returns:
        dict voi id, title, status
    """
    service = _get_tasks_service()
    body = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due

    result = service.tasks().insert(tasklist=task_list_id, body=body).execute()
    logger.info("Da tao task: '%s' trong list %s", title, task_list_id)
    return {
        "id": result["id"],
        "title": result.get("title", title),
        "status": result.get("status", "needsAction"),
    }


def complete_task(task_list_id: str, task_id: str) -> bool:
    """Danh dau 1 task la hoan thanh."""
    service = _get_tasks_service()
    service.tasks().update(
        tasklist=task_list_id,
        task=task_id,
        body={"id": task_id, "status": "completed"},
    ).execute()
    logger.info("Da hoan thanh task %s", task_id)
    return True


def delete_task(task_list_id: str, task_id: str) -> bool:
    """Xoa 1 task."""
    service = _get_tasks_service()
    service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
    logger.info("Da xoa task %s", task_id)
    return True
