"""
Zertdoo - He thong AI Agent ca nhan
Entry point: FastAPI server + APScheduler
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings, setup_google_credentials
from services.database import init_pool, close_pool

# === Logging ===
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("zertdoo")

# === APScheduler (global) ===
scheduler = BackgroundScheduler()


# === Lifecycle: khoi dong va tat ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Chay khi server khoi dong va khi server tat.
    - Khoi dong: ket noi database, khoi dong APScheduler
    - Tat: dong ket noi, dung scheduler
    """
    logger.info("Zertdoo dang khoi dong...")

    # Tao file Google credentials tu env var (cho cloud deploy)
    setup_google_credentials()

    # Ket noi PostgreSQL connection pool
    try:
        await init_pool()
        logger.info("Database pool da san sang.")
    except Exception as e:
        logger.error("Khong the ket noi database: %s", e)
        logger.warning("Server se chay KHONG co database.")

    # Khoi dong APScheduler
    _setup_scheduler()
    scheduler.start()
    logger.info("APScheduler da khoi dong.")

    # TODO [Giai doan 4]: Dang ky Telegram webhook

    logger.info("Zertdoo da san sang.")
    yield

    # Shutdown
    logger.info("Zertdoo dang tat...")
    scheduler.shutdown(wait=False)
    logger.info("APScheduler da dung.")
    await close_pool()
    logger.info("Zertdoo da tat.")


# === FastAPI app ===
app = FastAPI(
    title="Zertdoo API",
    description="He thong AI Agent ca nhan - Quan ly lich trinh va nhiem vu",
    version="0.1.0",
    lifespan=lifespan,
)


# === Health check ===
@app.get("/health")
async def health_check():
    """
    Kiem tra trang thai he thong.
    Dung cho monitoring (VD: UptimeRobot).
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "debug": settings.debug,
    }


# === Placeholder: Telegram webhook ===
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Nhan Update tu Telegram.
    Se duoc implement day du o Giai doan 4.
    """
    # TODO [Giai doan 4]: Xu ly Telegram Update
    body = await request.json()
    logger.info("Nhan Telegram update: %s", body)
    return JSONResponse(content={"ok": True})


# === Scheduler manual trigger ===
@app.post("/api/scheduler/run")
async def trigger_scheduler():
    """
    Chay SchedulerAgent thu cong (khong doi APScheduler cron).
    Dung de test hoac khi can len lai lich giua ngay.
    """
    from agents.scheduler import run as scheduler_run

    try:
        result = await scheduler_run()
        return {
            "status": "ok",
            "tasks_count": len(result["plan"].daily_tasks),
            "events_count": len(result["event_ids"]),
            "plan_id": result["plan_id"],
            "summary": result["summary"][:2000],
        }
    except Exception as e:
        logger.error("Scheduler manual run loi: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# === APScheduler setup ===
def _setup_scheduler():
    """Dang ky cac cron jobs vao APScheduler."""
    from agents.scheduler import run_scheduled

    # SchedulerAgent: chay moi ngay luc 6:00 AM VN
    scheduler.add_job(
        run_scheduled,
        trigger=CronTrigger(
            hour=settings.scheduler_hour,
            minute=settings.scheduler_minute,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="scheduler_daily",
        name="SchedulerAgent daily run",
        replace_existing=True,
    )
    logger.info(
        "Da dang ky cron job: SchedulerAgent chay luc %02d:%02d moi ngay",
        settings.scheduler_hour,
        settings.scheduler_minute,
    )

    # TODO [Phase 4]: Them cac notification jobs (6:15, 12:00, 21:00)
    # TODO [Phase 5]: Them SyncAgent polling job (moi 15 phut)
    # TODO [Phase 6]: Them ReportAgent cron (Chu nhat 20:00, ngay 1 hang thang 08:00)


# === Chay truc tiep ===
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
