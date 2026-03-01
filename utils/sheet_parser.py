"""
Tien ich xu ly du lieu tu Google Sheet.
Xu ly merged cells (forward-fill), loc hang trong, chuan hoa du lieu.
Ho tro nhieu cau truc cot khac nhau giua cac worksheets.
"""

import logging
from typing import Optional

from models.schemas import TaskItem

logger = logging.getLogger("zertdoo.sheet_parser")


def forward_fill_column(rows: list[list], col_index: int) -> list[list]:
    """
    Forward-fill 1 cot trong danh sach hang.

    Google Sheets merge cells chi giu gia tri o hang dau tien,
    cac hang tiep theo trong vung merge la chuoi rong "".
    Ham nay dien gia tri tu hang tren xuong cho cac o trong.

    Args:
        rows: Danh sach cac hang (moi hang la list cac gia tri)
        col_index: Chi so cot can forward-fill (0-based)

    Returns:
        Danh sach hang da forward-fill
    """
    last_value = ""
    for row in rows:
        if col_index < len(row):
            cell = str(row[col_index]).strip()
            if cell:
                last_value = cell
            else:
                row[col_index] = last_value
        else:
            # Hang ngan hon col_index, bo qua
            pass
    return rows


def detect_column_layout(header: list) -> dict:
    """
    Phat hien cau truc cot tu header row.

    Co 2 layout:
    1. In_class: [Deadlines, (Category), Task, Prior, Start date, Due date, Status, Notes]
       -> Category o cot B (index 1), Task o cot C (index 2)
    2. Cac sheet khac: [(Category), Task, Prior, Start date, Due date, Status, Notes]
       -> Category o cot A (index 0), Task o cot B (index 1)

    Returns:
        dict voi keys: category_col, task_col, priority_col,
                       start_col, due_col, status_col, notes_col, extra_col
    """
    header_lower = [str(h).strip().lower() for h in header]

    # Tim vi tri cot "Task" lam neo
    task_col = -1
    for i, h in enumerate(header_lower):
        if h == "task":
            task_col = i
            break

    if task_col == -1:
        # Fallback: neu khong co header "Task", dung layout mac dinh
        logger.warning("Khong tim thay cot 'Task' trong header: %s. Dung layout mac dinh.", header)
        return {
            "category_col": 0,
            "task_col": 1,
            "priority_col": 2,
            "start_col": 3,
            "due_col": 4,
            "status_col": 5,
            "notes_col": 6,
            "extra_col": None,
        }

    # Category la cot ngay truoc Task
    category_col = task_col - 1 if task_col > 0 else None

    # Extra column (vi du: Deadlines) la cot truoc Category
    extra_col = None
    if category_col is not None and category_col > 0:
        extra_col = 0  # Deadlines o cot A

    return {
        "category_col": category_col,
        "task_col": task_col,
        "priority_col": task_col + 1,
        "start_col": task_col + 2,
        "due_col": task_col + 3,
        "status_col": task_col + 4,
        "notes_col": task_col + 5,
        "extra_col": extra_col,
    }


def is_valid_row(row: list, task_col: int) -> bool:
    """
    Kiem tra hang co du lieu hop le khong.
    Hang hop le: co task name (o task_col) khong trong.
    """
    if len(row) <= task_col:
        return False

    task_name = str(row[task_col]).strip()
    if not task_name:
        return False

    # Bo qua cac hang separator
    if task_name.startswith("---") or task_name.startswith("==="):
        return False

    return True


def parse_sheet_data(
    header: list,
    rows: list[list],
    sheet_name: str,
) -> list[TaskItem]:
    """
    Parse du lieu tu 1 worksheet thanh list[TaskItem].
    Tu dong phat hien cau truc cot tu header.

    Args:
        header: Hang header (hang 1)
        rows: Du lieu tu hang 2 tro di
        sheet_name: Ten cua worksheet

    Returns:
        list[TaskItem] da chuan hoa
    """
    if not rows:
        return []

    layout = detect_column_layout(header)
    cat_col = layout["category_col"]
    task_col = layout["task_col"]
    prio_col = layout["priority_col"]
    start_col = layout["start_col"]
    due_col = layout["due_col"]
    status_col = layout["status_col"]
    notes_col = layout["notes_col"]

    # Forward-fill Category column
    if cat_col is not None:
        rows = forward_fill_column(rows, cat_col)

    tasks = []
    for i, row in enumerate(rows):
        if not is_valid_row(row, task_col):
            continue

        def get_cell(idx: int) -> str:
            if idx is not None and idx < len(row):
                val = row[idx]
                return str(val).strip() if val is not None else ""
            return ""

        category = get_cell(cat_col) if cat_col is not None else ""
        notes = get_cell(notes_col)

        try:
            task = TaskItem(
                sheet_name=sheet_name,
                category=category,
                task=get_cell(task_col),
                priority=get_cell(prio_col),
                start_date=get_cell(start_col) or None,
                due_date=get_cell(due_col) or None,
                status=get_cell(status_col),
                notes=notes,
            )
            tasks.append(task)
        except Exception as e:
            logger.warning(
                "Khong parse duoc hang %d trong sheet '%s': %s | Row: %s",
                i + 2, sheet_name, e, row[:4]
            )

    logger.info(
        "Sheet '%s': layout=%s, parse %d tasks tu %d hang.",
        sheet_name,
        f"cat={cat_col},task={task_col}",
        len(tasks), len(rows)
    )
    return tasks


# === Backward compatibility ===
def parse_sheet_rows(rows: list[list], sheet_name: str) -> list[TaskItem]:
    """Wrapper cho test - dung layout mac dinh (cat=0, task=1)."""
    header = ["", "Task", "Prior", "Start date", "Due date", "Status", "Notes"]
    return parse_sheet_data(header, rows, sheet_name)
