"""
Test Phase 5: SyncAgent

Test 1: Chay SyncAgent lan dau (tao snapshot dau tien)
Test 2: Chay lai lan 2 (so sanh voi snapshot cu -> phat hien diff)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from services.database import init_pool, close_pool
    from agents.sync import run

    print("Phase 5 - SyncAgent Test")
    print("=" * 50)

    await init_pool()
    try:
        # Lan 1: Tao snapshot dau tien
        print("\n=== LAN CHAY 1 (tao snapshot dau tien) ===")
        result1 = await run()
        print(f"Ket qua:")
        for k, v in result1.items():
            print(f"  {k}: {v}")

        print("\nNghi 3 giay truoc khi chay lan 2...")
        await asyncio.sleep(3)

        # Lan 2: Co snapshot cu de so sanh
        print("\n=== LAN CHAY 2 (so sanh voi snapshot cu) ===")
        result2 = await run()
        print(f"Ket qua:")
        for k, v in result2.items():
            print(f"  {k}: {v}")

        print("\n" + "=" * 50)
        print("SyncAgent test hoan thanh.")
        print(f"  Lan 1: {result1['total_tasks_snapshot']} G-Tasks, {result1['total_sheets_snapshot']} Sheet tasks")
        print(f"  Lan 2: {result2['tasks_changes']} Tasks changes, {result2['sheets_changes']} Sheets changes")

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
