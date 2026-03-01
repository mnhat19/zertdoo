"""Quick test: chay full SchedulerAgent pipeline."""
import asyncio, sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

async def main():
    from services.database import init_pool, close_pool
    from agents.scheduler import run

    await init_pool()
    try:
        result = await run()
        plan = result["plan"]
        print()
        print("=" * 60)
        print("KET QUA")
        print("=" * 60)
        print(f"Tasks: {len(plan.daily_tasks)}")
        print(f"Events: {len(result['event_ids'])}")
        print(f"Plan ID: {result['plan_id']}")
        print(f"Task list ID: {result['task_list_id']}")
        print()
        print(result["summary"])
    finally:
        await close_pool()

asyncio.run(main())
