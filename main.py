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

    # Dang ky Telegram webhook
    if settings.telegram_bot_token:
        try:
            from services.telegram_sender import set_webhook
            webhook_ok = await set_webhook()
            if webhook_ok:
                logger.info("Telegram webhook da dang ky.")
            else:
                logger.warning("Khong dang ky duoc Telegram webhook.")
        except Exception as e:
            logger.error("Loi dang ky Telegram webhook: %s", e)
    else:
        logger.info("Chua cau hinh TELEGRAM_BOT_TOKEN, bo qua webhook.")

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


# === Telegram webhook ===
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Nhan Update tu Telegram Bot API.
    Xac thuc bang secret token header.
    Chi xu ly message text tu ALLOWED_CHAT_ID.
    """
    # Xac thuc secret token
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.telegram_webhook_secret:
            logger.warning("Webhook secret khong khop: %s", secret[:10])
            return JSONResponse(status_code=403, content={"ok": False})

    body = await request.json()
    logger.debug("Telegram update: %s", body)

    # Parse message
    message = body.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))

    if not text or not chat_id:
        # Khong phai text message (sticker, photo, ...) -> bo qua
        return JSONResponse(content={"ok": True})

    # Xu ly async (khong block webhook response)
    import asyncio
    from agents.telegram import handle_message

    # Tao background task de xu ly tin nhan
    asyncio.create_task(_process_telegram_message(text, chat_id))

    return JSONResponse(content={"ok": True})


async def _process_telegram_message(text: str, chat_id: str):
    """Background task xu ly tin nhan Telegram."""
    try:
        from agents.telegram import handle_message
        await handle_message(text, chat_id)
    except Exception as e:
        logger.error("Loi xu ly Telegram message: %s", e, exc_info=True)


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


# === Telegram manual triggers ===
@app.post("/api/telegram/test")
async def test_telegram_message():
    """Gui tin nhan test den Telegram."""
    from services.telegram_sender import send_message
    results = await send_message("Zertdoo test: he thong dang hoat dong.")
    return {"status": "ok", "messages_sent": len(results)}


@app.post("/api/telegram/morning")
async def trigger_morning_summary():
    """Chay morning summary thu cong."""
    from agents.telegram import send_morning_summary
    await send_morning_summary()
    return {"status": "ok"}


@app.post("/api/telegram/afternoon")
async def trigger_afternoon_reminder():
    """Chay afternoon reminder thu cong."""
    from agents.telegram import send_afternoon_reminder
    await send_afternoon_reminder()
    return {"status": "ok"}


@app.post("/api/telegram/evening")
async def trigger_evening_review():
    """Chay evening review thu cong."""
    from agents.telegram import send_evening_review
    await send_evening_review()
    return {"status": "ok"}


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

    # Telegram notification jobs
    if settings.telegram_bot_token:
        from agents.telegram import (
            run_morning_summary,
            run_afternoon_reminder,
            run_evening_review,
        )

        # 6:15 AM: tom tat lich ngay (sau khi SchedulerAgent chay)
        scheduler.add_job(
            run_morning_summary,
            trigger=CronTrigger(hour=6, minute=15, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_morning",
            name="Telegram morning summary",
            replace_existing=True,
        )

        # 12:00 PM: nhac tasks buoi chieu
        scheduler.add_job(
            run_afternoon_reminder,
            trigger=CronTrigger(hour=12, minute=0, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_afternoon",
            name="Telegram afternoon reminder",
            replace_existing=True,
        )

        # 21:00: review cuoi ngay
        scheduler.add_job(
            run_evening_review,
            trigger=CronTrigger(hour=21, minute=0, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_evening",
            name="Telegram evening review",
            replace_existing=True,
        )

        logger.info("Da dang ky 3 Telegram notification jobs (6:15, 12:00, 21:00)")

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
