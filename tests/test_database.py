"""Test database service."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def test():
    from services.database import init_pool, close_pool, save_task_log, get_recent_task_logs, get_behavior_stats

    pool = await init_pool()
    print("Pool khoi tao OK")

    # Test save 1 task log
    tid = await save_task_log(
        task_name="Test task Phase 1",
        source="test",
        priority="High",
        status="pending",
    )
    print(f"Saved task log id={tid}")

    # Test query
    logs = await get_recent_task_logs(days=1)
    print(f"Recent logs: {len(logs)} ban ghi")
    for log in logs:
        print(f"  - id={log['id']}, name={log['task_name']}, source={log['source']}")

    # Test behavior stats
    stats = await get_behavior_stats(days=30)
    print(f"Stats: {stats}")

    await close_pool()
    print("Pool dong OK")

asyncio.run(test())
