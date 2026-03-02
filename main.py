"""
Zertdoo - He thong AI Agent ca nhan
Entry point: FastAPI server + APScheduler (AsyncIO)
"""

import logging
import time as _time
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings, setup_google_credentials
from services.database import init_pool, close_pool, check_db_health, create_notifications_tables

# === Logging ===
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("zertdoo")

# === APScheduler (AsyncIO - dung chung event loop voi FastAPI) ===
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

# === Jinja2 Templates ===
templates = Jinja2Templates(directory="templates")

# === Thoi gian khoi dong (de tinh uptime) ===
_start_time = _time.time()


# ============================================================
# API AUTHENTICATION
# ============================================================

async def verify_api_key(request: Request):
    """
    Dependency xac thuc API key cho cac endpoint /api/*.
    Neu API_SECRET_KEY chua cau hinh -> bo qua (dev mode).
    Neu da cau hinh -> yeu cau header Authorization: Bearer <key>.
    """
    if not settings.api_secret_key:
        return  # Dev mode, khong can auth

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thieu Authorization header")

    token = auth_header[7:]  # Bo "Bearer "
    if token != settings.api_secret_key:
        raise HTTPException(status_code=403, detail="API key khong hop le")


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
        # Tao bang web push neu chua ton tai
        try:
            await create_notifications_tables()
        except Exception as e:
            logger.warning("Khong the tao notification tables: %s", e)
    except Exception as e:
        logger.error("Khong the ket noi database: %s", e)
        logger.warning("Server se chay KHONG co database.")

    # Khoi dong APScheduler (AsyncIO - dung chung event loop)
    _setup_scheduler()
    scheduler.start()
    logger.info("APScheduler (AsyncIO) da khoi dong voi %d jobs.", len(scheduler.get_jobs()))

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
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (Service Worker, v.v.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Service Worker phai o root path de co scope /
# Phuc vu /sw.js truc tiep tu thu muc static
@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    """Phuc vu Service Worker o root path (bat buoc de SW co scope /)."""
    from fastapi.responses import FileResponse
    return FileResponse("static/sw.js", media_type="application/javascript")


# ============================================================
# GLOBAL EXCEPTION HANDLER
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Bat tat ca exception chua duoc xu ly, log va tra ve 500."""
    logger.error(
        "Unhandled exception: %s %s -> %s: %s",
        request.method, request.url.path,
        type(exc).__name__, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Loi he thong noi bo"},
    )


# === Health check ===
@app.get("/health")
async def health_check():
    """
    Kiem tra trang thai he thong chi tiet.
    Tra ve trang thai database, scheduler, uptime.
    """
    uptime_seconds = int(_time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Database health
    db_health = await check_db_health()

    # Scheduler health
    jobs = scheduler.get_jobs()
    scheduler_info = {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(getattr(job, "next_run_time", None)),
            }
            for job in jobs
        ],
    }

    # Overall status
    overall = "ok"
    if db_health.get("status") != "connected":
        overall = "degraded"
    if not scheduler.running:
        overall = "degraded"

    return {
        "status": overall,
        "service": settings.app_name,
        "version": "1.0.0",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_seconds,
        "database": db_health,
        "scheduler": scheduler_info,
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
@app.post("/api/scheduler/run", dependencies=[Depends(verify_api_key)])
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
@app.post("/api/telegram/test", dependencies=[Depends(verify_api_key)])
async def test_telegram_message():
    """Gui tin nhan test den Telegram."""
    from services.telegram_sender import send_message
    results = await send_message("Zertdoo test: hệ thống đang hoạt động.")
    return {"status": "ok", "messages_sent": len(results)}


@app.post("/api/telegram/morning", dependencies=[Depends(verify_api_key)])
async def trigger_morning_summary():
    """Chay morning summary thu cong."""
    from agents.telegram import send_morning_summary
    await send_morning_summary()
    return {"status": "ok"}


@app.post("/api/telegram/afternoon", dependencies=[Depends(verify_api_key)])
async def trigger_afternoon_reminder():
    """Chay afternoon reminder thu cong."""
    from agents.telegram import send_afternoon_reminder
    await send_afternoon_reminder()
    return {"status": "ok"}


@app.post("/api/telegram/evening", dependencies=[Depends(verify_api_key)])
async def trigger_evening_review():
    """Chay evening review thu cong."""
    from agents.telegram import send_evening_review
    await send_evening_review()
    return {"status": "ok"}


# === SyncAgent manual trigger ===
@app.post("/api/sync/run", dependencies=[Depends(verify_api_key)])
async def trigger_sync():
    """Chay SyncAgent thu cong."""
    from agents.sync import run as sync_run

    try:
        result = await sync_run()
        return {"status": "ok", **result}
    except Exception as e:
        logger.error("Sync manual run loi: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# ============================================================
# WEB PUSH ENDPOINTS
# ============================================================

@app.get("/vapid-public-key", include_in_schema=False)
async def get_vapid_public_key():
    """Tra ve VAPID public key cho JavaScript subscribeuser."""
    if not settings.vapid_public_key:
        raise HTTPException(status_code=404, detail="Web push chua cau hinh")
    return {"publicKey": settings.vapid_public_key}


@app.post("/api/push/subscribe")
async def subscribe_push(request: Request):
    """
    Dang ky browser push subscription.
    Body: {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
    Khong yeu cau Bearer token de JavaScript goi duoc.
    """
    try:
        body = await request.json()
        endpoint = body.get("endpoint", "")
        keys = body.get("keys", {})
        p256dh = keys.get("p256dh", "")
        auth = keys.get("auth", "")

        if not endpoint or not p256dh or not auth:
            raise HTTPException(status_code=400, detail="Thieu truong bat buoc")

        from services.database import save_push_subscription
        sub_id = await save_push_subscription(endpoint, p256dh, auth)
        logger.info("Da luu push subscription id=%d: %s...", sub_id, endpoint[:50])
        return {"status": "ok", "id": sub_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Loi luu push subscription: %s", e)
        return JSONResponse(status_code=500, content={"status": "error"})


@app.delete("/api/push/unsubscribe")
async def unsubscribe_push(request: Request):
    """
    Huy dang ky push subscription.
    Body: {"endpoint": "..."}
    """
    try:
        body = await request.json()
        endpoint = body.get("endpoint", "")
        if not endpoint:
            raise HTTPException(status_code=400, detail="Thieu endpoint")
        from services.database import remove_push_subscription
        await remove_push_subscription(endpoint)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Loi xoa push subscription: %s", e)
        return JSONResponse(status_code=500, content={"status": "error"})


@app.get("/api/notifications")
async def get_notifications(unread: bool = False, limit: int = 30):
    """
    Lay danh sach thong bao dong bo.
    ?unread=true  -> chi tra ve chua doc
    ?limit=N      -> gioi han so luong (max 100)
    """
    try:
        from services.database import get_web_notifications
        limit = min(limit, 100)
        items = await get_web_notifications(limit=limit, unread_only=unread)
        # Convert datetime sang string
        for item in items:
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
        unread_count = sum(1 for i in items if not i.get("is_read"))
        return {"status": "ok", "notifications": items, "unread_count": unread_count}
    except Exception as e:
        logger.error("Loi lay notifications: %s", e)
        return JSONResponse(status_code=500, content={"status": "error"})


@app.post("/api/notifications/read-all")
async def mark_all_read():
    """Danh dau tat ca thong bao la da doc."""
    try:
        from services.database import mark_all_notifications_read
        await mark_all_notifications_read()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Loi mark all read: %s", e)
        return JSONResponse(status_code=500, content={"status": "error"})


# === ReportAgent manual triggers ===
@app.post("/api/report/weekly", dependencies=[Depends(verify_api_key)])
async def trigger_weekly_report():
    """Chay bao cao tuan thu cong."""
    from agents.report import run_weekly_report

    try:
        result = await run_weekly_report()
        return {
            "status": "ok",
            "type": result["type"],
            "email_id": result.get("email_id"),
            "report_length": result["report_length"],
        }
    except Exception as e:
        logger.error("Weekly report loi: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


@app.post("/api/report/monthly", dependencies=[Depends(verify_api_key)])
async def trigger_monthly_report():
    """Chay bao cao thang thu cong."""
    from agents.report import run_monthly_report

    try:
        result = await run_monthly_report()
        return {
            "status": "ok",
            "type": result["type"],
            "email_id": result.get("email_id"),
            "report_length": result["report_length"],
        }
    except Exception as e:
        logger.error("Monthly report loi: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )


# ============================================================
# WEB DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Web dashboard - trang tong quan he thong.
    Hien thi: tasks hom nay, ti le hoan thanh, deadlines, agent logs.
    """
    from services.database import ensure_pool

    # Du lieu mac dinh khi DB khong kha dung
    context = {
        "request": request,
        "db_available": False,
        "today_tasks": [],
        "stats": {
            "total_tasks_30d": 0,
            "completed_tasks_30d": 0,
            "completion_rate": 0,
            "avg_tasks_per_day": 0,
        },
        "recent_agents": [],
        "pending_tasks": [],
        "uptime_seconds": int(_time.time() - _start_time),
        "scheduler_running": scheduler.running,
        "scheduler_jobs": len(scheduler.get_jobs()),
    }

    pool = await ensure_pool()
    if pool:
        try:
            context["db_available"] = True

            # Tasks hom nay
            today = date.today()
            today_rows = await pool.fetch(
                """
                SELECT task_name, source, category, priority, status,
                       scheduled_time_slot, duration_minutes
                FROM task_logs
                WHERE scheduled_date = $1
                ORDER BY scheduled_time_slot ASC NULLS LAST
                """,
                today,
            )
            context["today_tasks"] = [dict(r) for r in today_rows]

            # Thong ke 30 ngay
            from services.database import get_behavior_stats
            context["stats"] = await get_behavior_stats(30)

            # Agent logs gan nhat (10 entries)
            agent_rows = await pool.fetch(
                """
                SELECT agent_name, llm_model, duration_ms, error,
                       created_at AT TIME ZONE 'Asia/Ho_Chi_Minh' as created_at_vn
                FROM agent_logs
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            context["recent_agents"] = [dict(r) for r in agent_rows]

            # Tasks chua xong (pending/rescheduled) voi deadline gan
            pending_rows = await pool.fetch(
                """
                SELECT task_name, source, category, priority,
                       scheduled_date, status
                FROM task_logs
                WHERE status IN ('pending', 'rescheduled')
                  AND scheduled_date IS NOT NULL
                ORDER BY scheduled_date ASC
                LIMIT 15
                """
            )
            context["pending_tasks"] = [dict(r) for r in pending_rows]

        except Exception as e:
            logger.error("Dashboard query loi: %s", e)
            context["db_error"] = str(e)

    return templates.TemplateResponse("dashboard.html", context)


# === APScheduler setup ===
def _setup_scheduler():
    """Dang ky cac cron/interval jobs vao AsyncIOScheduler."""
    from agents.scheduler import run_scheduled_async

    # SchedulerAgent: chay moi ngay luc 6:00 AM VN
    scheduler.add_job(
        run_scheduled_async,
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
            run_morning_summary_async,
            run_afternoon_reminder_async,
            run_evening_review_async,
        )

        # 6:15 AM: tom tat lich ngay (sau khi SchedulerAgent chay)
        scheduler.add_job(
            run_morning_summary_async,
            trigger=CronTrigger(hour=6, minute=15, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_morning",
            name="Telegram morning summary",
            replace_existing=True,
        )

        # 12:00 PM: nhac tasks buoi chieu
        scheduler.add_job(
            run_afternoon_reminder_async,
            trigger=CronTrigger(hour=12, minute=0, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_afternoon",
            name="Telegram afternoon reminder",
            replace_existing=True,
        )

        # 21:00: review cuoi ngay
        scheduler.add_job(
            run_evening_review_async,
            trigger=CronTrigger(hour=21, minute=0, timezone="Asia/Ho_Chi_Minh"),
            id="telegram_evening",
            name="Telegram evening review",
            replace_existing=True,
        )

        logger.info("Da dang ky 3 Telegram notification jobs (6:15, 12:00, 21:00)")

    # SyncAgent: polling moi 15 phut
    from agents.sync import run_scheduled_async as sync_run_async

    scheduler.add_job(
        sync_run_async,
        trigger=IntervalTrigger(minutes=15, timezone="Asia/Ho_Chi_Minh"),
        id="sync_polling",
        name="SyncAgent polling (15 min)",
        replace_existing=True,
    )
    logger.info("Da dang ky SyncAgent polling moi 15 phut")

    # ReportAgent cron jobs
    from agents.report import run_weekly_scheduled_async, run_monthly_scheduled_async

    # Chu nhat 20:00: bao cao tuan
    scheduler.add_job(
        run_weekly_scheduled_async,
        trigger=CronTrigger(
            day_of_week="sun", hour=20, minute=0,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="report_weekly",
        name="ReportAgent weekly (Sun 20:00)",
        replace_existing=True,
    )

    # Ngay 1 hang thang 08:00: bao cao thang
    scheduler.add_job(
        run_monthly_scheduled_async,
        trigger=CronTrigger(
            day=1, hour=8, minute=0,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="report_monthly",
        name="ReportAgent monthly (1st 08:00)",
        replace_existing=True,
    )

    logger.info("Da dang ky ReportAgent cron: tuan (CN 20:00), thang (ngay 1 08:00)")


# === Chay truc tiep ===
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
