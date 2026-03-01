"""
Test toan bo Phase 1 readers.
Chay: python tests/test_readers.py

Can cau hinh trong .env:
- GOOGLE_SPREADSHEET_ID (bat buoc cho Sheets test)
- credentials/credentials.json + credentials/token.json (bat buoc cho Google APIs)
- NOTION_TOKEN (bat buoc cho Notion test)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_schemas():
    """Test import va validation cac Pydantic models."""
    print("\n=== TEST: Pydantic Schemas ===")
    from models.schemas import (
        TaskItem, NotionNote, GoogleTask, CalendarEvent,
        BehaviorStats, TaskLog, AgentLog, DailyPlan,
        ScheduledTask, EventToCreate, DailyPlanOutput,
    )

    # Test tao instance
    task = TaskItem(sheet_name="Self-study", task="Hoc Python", priority="High")
    print(f"  TaskItem OK: {task.sheet_name}/{task.task} [{task.priority}]")

    note = NotionNote(page_id="abc", database_id="def", title="Ghi chu test")
    print(f"  NotionNote OK: {note.title}")

    gtask = GoogleTask(
        task_id="123", task_list_id="456",
        title="Test task", status="needsAction"
    )
    print(f"  GoogleTask OK: {gtask.title} [{gtask.status}]")

    event = CalendarEvent(
        event_id="789", summary="Hop nhom",
        start="2026-03-01T10:00:00+07:00",
        end="2026-03-01T11:00:00+07:00"
    )
    print(f"  CalendarEvent OK: {event.summary} ({event.start})")

    plan = DailyPlanOutput(
        daily_tasks=[ScheduledTask(
            title="Test", source="test", priority_rank=1,
            time_slot="08:00 - 09:00", duration_minutes=60,
            reasoning="Day la test"
        )],
        overall_reasoning="Test plan"
    )
    print(f"  DailyPlanOutput OK: {len(plan.daily_tasks)} tasks")

    print("  -> Tat ca schemas OK!")


def test_sheet_parser():
    """Test forward-fill va parse rows."""
    print("\n=== TEST: Sheet Parser ===")
    from utils.sheet_parser import forward_fill_column, is_valid_row, parse_sheet_rows

    # Test forward-fill
    rows = [
        ["Math", "Bai tap 1", "High", "", "01/03/2026", ""],
        ["", "Bai tap 2", "Medium", "", "02/03/2026", ""],
        ["", "Bai tap 3", "Low", "", "", "Done"],
        ["Physics", "Lab report", "High", "", "05/03/2026", ""],
        ["", "", "", "", "", ""],  # Hang trong
    ]
    filled = forward_fill_column(rows, 0)
    assert filled[1][0] == "Math", f"Forward-fill sai: {filled[1][0]}"
    assert filled[2][0] == "Math", f"Forward-fill sai: {filled[2][0]}"
    assert filled[3][0] == "Physics", f"Forward-fill sai: {filled[3][0]}"
    print("  Forward-fill: OK")

    # Test is_valid_row
    assert is_valid_row(["Cat", "Task name"]) == True
    assert is_valid_row(["Cat", ""]) == False
    assert is_valid_row([""]) == False
    assert is_valid_row(["---", "---"]) == False
    print("  is_valid_row: OK")

    # Test parse_sheet_rows
    tasks = parse_sheet_rows(rows, "Test_Sheet")
    assert len(tasks) == 4, f"Expected 4 tasks, got {len(tasks)}"
    assert tasks[0].category == "Math"
    assert tasks[1].category == "Math"
    assert tasks[2].status == "Done"
    assert tasks[3].category == "Physics"
    print(f"  parse_sheet_rows: {len(tasks)} tasks parsed OK")

    print("  -> Sheet Parser: OK!")


def test_google_sheets():
    """Test doc du lieu tu Google Sheets that."""
    print("\n=== TEST: Google Sheets Reader ===")
    from config import settings
    if not settings.google_spreadsheet_id:
        print("  SKIP: GOOGLE_SPREADSHEET_ID chua cau hinh")
        return False

    try:
        from services.google_sheets import get_all_worksheet_names, read_all_sheets

        names = get_all_worksheet_names()
        print(f"  Worksheets: {names}")

        tasks = read_all_sheets()
        print(f"  Tong tasks: {len(tasks)}")
        for t in tasks[:5]:
            print(f"    [{t.sheet_name}] {t.category}/{t.task} - {t.priority} - {t.status}")
        if len(tasks) > 5:
            print(f"    ... va {len(tasks) - 5} tasks nua")

        print("  -> Google Sheets: OK!")
        return True
    except Exception as e:
        print(f"  LOI: {e}")
        return False


def test_google_tasks():
    """Test doc du lieu tu Google Tasks that."""
    print("\n=== TEST: Google Tasks Reader ===")
    try:
        from services.google_tasks import get_all_task_lists, read_all_tasks

        lists = get_all_task_lists()
        print(f"  Task lists: {len(lists)}")
        for tl in lists:
            print(f"    - {tl['title']} (id: {tl['id'][:20]}...)")

        tasks = read_all_tasks()
        print(f"  Tong tasks: {len(tasks)}")
        for t in tasks[:5]:
            status = "[x]" if t.status == "completed" else "[ ]"
            print(f"    {status} [{t.task_list_title}] {t.title}")
        if len(tasks) > 5:
            print(f"    ... va {len(tasks) - 5} tasks nua")

        print("  -> Google Tasks: OK!")
        return True
    except Exception as e:
        print(f"  LOI: {e}")
        return False


def test_google_calendar():
    """Test doc su kien tu Google Calendar that."""
    print("\n=== TEST: Google Calendar Reader ===")
    try:
        from services.google_calendar import get_upcoming_events

        events = get_upcoming_events(days=7)
        print(f"  Su kien 7 ngay toi: {len(events)}")
        for e in events[:5]:
            time_str = e.start[:16] if len(e.start) > 10 else e.start
            print(f"    [{time_str}] {e.summary}")
        if len(events) > 5:
            print(f"    ... va {len(events) - 5} events nua")

        print("  -> Google Calendar: OK!")
        return True
    except Exception as e:
        print(f"  LOI: {e}")
        return False


def test_notion():
    """Test doc du lieu tu Notion that."""
    print("\n=== TEST: Notion Reader ===")
    from config import settings
    if not settings.notion_token:
        print("  SKIP: NOTION_TOKEN chua cau hinh")
        return False

    try:
        from services.notion import get_all_databases, read_all_notes

        dbs = get_all_databases()
        print(f"  Databases: {len(dbs)}")
        for db in dbs:
            print(f"    - {db['title']} (id: {db['id'][:20]}...)")

        notes = read_all_notes(fetch_content=False)  # Khong doc content de nhanh
        print(f"  Tong notes: {len(notes)}")
        for n in notes[:5]:
            print(f"    [{n.database_name}] {n.title}")
        if len(notes) > 5:
            print(f"    ... va {len(notes) - 5} notes nua")

        print("  -> Notion: OK!")
        return True
    except Exception as e:
        print(f"  LOI: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("ZERTDOO - Phase 1 Readers Test")
    print("=" * 50)

    # Tests khong can credentials
    test_schemas()
    test_sheet_parser()

    # Tests can credentials - chay tung cai
    results = {}
    results["Google Sheets"] = test_google_sheets()
    results["Google Tasks"] = test_google_tasks()
    results["Google Calendar"] = test_google_calendar()
    results["Notion"] = test_notion()

    # Tong ket
    print("\n" + "=" * 50)
    print("TONG KET:")
    print("  Schemas: OK")
    print("  Sheet Parser: OK")
    for name, ok in results.items():
        status = "OK" if ok else "SKIP/LOI"
        print(f"  {name}: {status}")
    print("=" * 50)
