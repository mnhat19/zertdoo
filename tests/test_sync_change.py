"""
Test SyncAgent - mo phong thay doi.

1. Tick 1 task completed trong Google Tasks
2. Chay SyncAgent -> phat hien thay doi + gui Telegram
3. Uncomplete lai task do (cleanup)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from services.database import init_pool, close_pool
    from services.google_tasks import (
        get_all_task_lists, get_tasks_from_list, complete_task,
    )
    from agents.sync import run
    from utils.time_utils import format_date_vn, today_vn

    print("Test SyncAgent - Mo phong thay doi")
    print("=" * 50)

    await init_pool()
    try:
        # Tim task list hom nay
        today_title = format_date_vn(today_vn())
        print(f"Tim list: '{today_title}'")

        lists = get_all_task_lists()
        target_list = None
        for tl in lists:
            if tl["title"] == today_title:
                target_list = tl
                break

        if not target_list:
            print(f"Khong tim thay list '{today_title}'. Bo qua test nay.")
            return

        # Lay task dau tien chua completed
        tasks = get_tasks_from_list(target_list["id"], target_list["title"])
        target_task = None
        for t in tasks:
            if t.status == "needsAction":
                target_task = t
                break

        if not target_task:
            print("Khong co task nao chua completed. Bo qua.")
            return

        print(f"Task de test: '{target_task.title}' (id={target_task.task_id})")

        # Tick completed
        print("\n1. Tick task completed...")
        complete_task(target_list["id"], target_task.task_id)
        print("   Da tick completed.")

        # Chay SyncAgent
        print("\n2. Chay SyncAgent...")
        result = await run()
        print(f"   Ket qua: {result}")

        # Uncomplete (khoi phuc)
        print("\n3. Khoi phuc task (uncomplete)...")
        from services.google_tasks import _get_tasks_service
        service = _get_tasks_service()
        service.tasks().update(
            tasklist=target_list["id"],
            task=target_task.task_id,
            body={"id": target_task.task_id, "status": "needsAction"},
        ).execute()
        print("   Da khoi phuc.")

        print("\n" + "=" * 50)
        print(f"Tasks changes detected: {result['tasks_changes']}")
        print(f"DB synced: {result['db_synced']}")
        if result['tasks_changes'] > 0:
            print("THANH CONG: SyncAgent phat hien thay doi!")
        else:
            print("Khong phat hien thay doi (co the snapshot chua cap nhat)")

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
