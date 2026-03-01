"""
Google Sheets reader cho Zertdoo.
Doc toan bo worksheets tu 1 spreadsheet, parse thanh list[TaskItem].
"""

import logging
from typing import Optional

from models.schemas import TaskItem
from services.google_auth import build_service
from utils.sheet_parser import parse_sheet_data
from config import settings

logger = logging.getLogger("zertdoo.google_sheets")


def _get_sheets_service():
    """Tao Google Sheets API service."""
    return build_service("sheets", "v4")


def get_all_worksheet_names(spreadsheet_id: str = None) -> list[str]:
    """
    Lay danh sach ten tat ca worksheets trong spreadsheet.

    Args:
        spreadsheet_id: ID cua spreadsheet (mac dinh doc tu config)

    Returns:
        list[str] ten cac worksheet
    """
    sid = spreadsheet_id or settings.google_spreadsheet_id
    if not sid:
        raise ValueError("GOOGLE_SPREADSHEET_ID chua duoc cau hinh trong .env")

    service = _get_sheets_service()
    meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    sheets = meta.get("sheets", [])
    names = [s["properties"]["title"] for s in sheets]
    logger.info("Spreadsheet co %d worksheets: %s", len(names), names)
    return names


def read_worksheet(sheet_name: str, spreadsheet_id: str = None) -> list[TaskItem]:
    """
    Doc 1 worksheet va parse thanh list[TaskItem].
    Tu dong phat hien cau truc cot tu header.

    Args:
        sheet_name: Ten worksheet
        spreadsheet_id: ID spreadsheet (mac dinh tu config)

    Returns:
        list[TaskItem]
    """
    sid = spreadsheet_id or settings.google_spreadsheet_id
    if not sid:
        raise ValueError("GOOGLE_SPREADSHEET_ID chua duoc cau hinh trong .env")

    service = _get_sheets_service()

    # Doc toan bo du lieu bao gom header (A1:H)
    range_str = f"'{sheet_name}'!A1:H"
    result = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=range_str,
    ).execute()

    all_rows = result.get("values", [])
    if not all_rows:
        logger.warning("Sheet '%s': khong co du lieu.", sheet_name)
        return []

    # Tach header (hang 1) va data (hang 2+)
    header = all_rows[0]
    data_rows = all_rows[1:]
    logger.debug("Sheet '%s': header=%s, %d data rows.", sheet_name, header, len(data_rows))

    # Parse voi auto-detect column layout
    tasks = parse_sheet_data(header, data_rows, sheet_name)
    return tasks


def read_all_sheets(spreadsheet_id: str = None) -> list[TaskItem]:
    """
    Doc toan bo worksheets trong spreadsheet.
    Tra ve danh sach tat ca tasks tu moi sheet gop lai.

    Args:
        spreadsheet_id: ID spreadsheet (mac dinh tu config)

    Returns:
        list[TaskItem] tu tat ca worksheets
    """
    sid = spreadsheet_id or settings.google_spreadsheet_id
    sheet_names = get_all_worksheet_names(sid)

    all_tasks: list[TaskItem] = []
    for name in sheet_names:
        try:
            tasks = read_worksheet(name, sid)
            all_tasks.extend(tasks)
        except Exception as e:
            logger.error("Loi khi doc sheet '%s': %s", name, e)

    logger.info(
        "Tong cong: %d tasks tu %d worksheets.",
        len(all_tasks), len(sheet_names)
    )
    return all_tasks


def read_sheets_summary(spreadsheet_id: str = None) -> str:
    """
    Doc tat ca sheets va tra ve dang text tom tat.
    Dung de truyen vao prompt LLM.

    Returns:
        str: Tom tat dang text
    """
    all_tasks = read_all_sheets(spreadsheet_id)

    if not all_tasks:
        return "Khong co task nao trong Google Sheet."

    # Nhom theo sheet_name
    by_sheet: dict[str, list[TaskItem]] = {}
    for t in all_tasks:
        by_sheet.setdefault(t.sheet_name, []).append(t)

    lines = []
    for sheet_name, tasks in by_sheet.items():
        pending = [t for t in tasks if t.status.lower() not in ("done",)]
        lines.append(f"\n[{sheet_name}] ({len(tasks)} tasks, {len(pending)} chua xong)")
        for t in tasks:
            status_mark = "[x]" if t.status.lower() == "done" else "[ ]"
            due_str = f" | Due: {t.due_date}" if t.due_date else ""
            prio_str = f" | {t.priority}" if t.priority else ""
            lines.append(
                f"  {status_mark} {t.category}/{t.task}{prio_str}{due_str}"
            )

    return "\n".join(lines)
