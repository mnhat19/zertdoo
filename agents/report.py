"""
ReportAgent - Tao va gui bao cao dinh ky qua Gmail.

Cron jobs:
- Chu nhat 20:00: bao cao tuan
- Ngay 1 hang thang 08:00: bao cao thang

Luong xu ly:
1. Query Postgres: task_logs, behavior_logs trong ky
2. Tinh toan thong ke
3. Goi LLM voi report prompt + data
4. Nhan bao cao text
5. Format thanh HTML
6. Gui email voi attachment year_vision.jpg
7. Gui Telegram thong bao
8. Log vao agent_logs
"""

import asyncio
import logging
import os
from datetime import date, timedelta

from config import settings
from services.llm import call_llm_text
from services.gmail import send_email, format_report_html
from utils.time_utils import today_vn, now_vn, format_date_vn

logger = logging.getLogger("zertdoo.report")

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
    "report.txt",
)


def _load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# THU THAP DU LIEU
# ============================================================

async def _collect_weekly_data() -> dict:
    """Thu thap du lieu cho bao cao tuan (7 ngay)."""
    from services.database import get_recent_task_logs, get_behavior_stats

    today = today_vn()
    # Tuan: 7 ngay gan nhat
    start_date = today - timedelta(days=7)

    logs = await get_recent_task_logs(days=7)
    stats = await get_behavior_stats(days=7)

    # Phan loai theo status
    total = len(logs)
    done = sum(1 for l in logs if l.get("status") == "done")
    pending = sum(1 for l in logs if l.get("status") == "pending")
    skipped = sum(1 for l in logs if l.get("status") == "skipped")
    rescheduled = sum(1 for l in logs if l.get("status") == "rescheduled")

    # Phan loai theo category
    by_category = {}
    for l in logs:
        cat = l.get("category") or l.get("sheet_name") or "Không phân loại"
        by_category.setdefault(cat, {"total": 0, "done": 0})
        by_category[cat]["total"] += 1
        if l.get("status") == "done":
            by_category[cat]["done"] += 1

    # Phan loai theo ngay
    by_date = {}
    for l in logs:
        d = l.get("scheduled_date")
        if d:
            key = str(d)
            by_date.setdefault(key, {"total": 0, "done": 0})
            by_date[key]["total"] += 1
            if l.get("status") == "done":
                by_date[key]["done"] += 1

    return {
        "period": "tuần",
        "start_date": str(start_date),
        "end_date": str(today),
        "total_tasks": total,
        "done": done,
        "pending": pending,
        "skipped": skipped,
        "rescheduled": rescheduled,
        "completion_rate": f"{(done/total*100):.1f}%" if total > 0 else "N/A",
        "by_category": by_category,
        "by_date": by_date,
        "behavior_stats": stats,
    }


async def _collect_monthly_data() -> dict:
    """Thu thap du lieu cho bao cao thang (30 ngay)."""
    from services.database import get_recent_task_logs, get_behavior_stats

    today = today_vn()
    start_date = today - timedelta(days=30)

    logs = await get_recent_task_logs(days=30)
    stats = await get_behavior_stats(days=30)

    total = len(logs)
    done = sum(1 for l in logs if l.get("status") == "done")
    pending = sum(1 for l in logs if l.get("status") == "pending")
    skipped = sum(1 for l in logs if l.get("status") == "skipped")
    rescheduled = sum(1 for l in logs if l.get("status") == "rescheduled")

    by_category = {}
    for l in logs:
        cat = l.get("category") or l.get("sheet_name") or "Không phân loại"
        by_category.setdefault(cat, {"total": 0, "done": 0})
        by_category[cat]["total"] += 1
        if l.get("status") == "done":
            by_category[cat]["done"] += 1

    # Theo tuan (4 tuan)
    by_week = {}
    for l in logs:
        d = l.get("scheduled_date")
        if d:
            week_num = (d - start_date).days // 7 + 1
            key = f"Tuần {week_num}"
            by_week.setdefault(key, {"total": 0, "done": 0})
            by_week[key]["total"] += 1
            if l.get("status") == "done":
                by_week[key]["done"] += 1

    by_date = {}
    for l in logs:
        d = l.get("scheduled_date")
        if d:
            key = str(d)
            by_date.setdefault(key, {"total": 0, "done": 0})
            by_date[key]["total"] += 1
            if l.get("status") == "done":
                by_date[key]["done"] += 1

    return {
        "period": "tháng",
        "start_date": str(start_date),
        "end_date": str(today),
        "total_tasks": total,
        "done": done,
        "pending": pending,
        "skipped": skipped,
        "rescheduled": rescheduled,
        "completion_rate": f"{(done/total*100):.1f}%" if total > 0 else "N/A",
        "by_category": by_category,
        "by_week": by_week,
        "by_date": by_date,
        "behavior_stats": stats,
    }


# ============================================================
# GOI LLM
# ============================================================

async def _generate_report(data: dict) -> str:
    """Goi LLM voi report prompt + data, nhan bao cao text."""
    import json

    system_prompt = _load_prompt()
    user_content = f"""Dữ liệu thống kê {data['period']}:
Từ {data['start_date']} đến {data['end_date']}

{json.dumps(data, ensure_ascii=False, indent=2, default=str)}

Viết báo cáo {data['period']} dựa trên dữ liệu trên.
"""

    report_text = await call_llm_text(
        system_prompt=system_prompt,
        user_content=user_content,
        agent_name="report",
        log_to_db=True,
    )

    logger.info("LLM tra ve bao cao: %d ky tu", len(report_text))
    return report_text


# ============================================================
# GUI BAO CAO
# ============================================================

async def _send_report_email(
    report_text: str,
    subject: str,
    title: str,
) -> dict:
    """Format HTML va gui email."""
    html = format_report_html(report_text, title)

    # Attachment: year_vision.jpg (neu co)
    attachment = None
    if settings.year_vision_path and os.path.exists(settings.year_vision_path):
        attachment = settings.year_vision_path

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: send_email(
            subject=subject,
            body_html=html,
            attachment_path=attachment,
        ),
    )

    logger.info("Da gui email bao cao: %s", subject)
    return result


# ============================================================
# MAIN: BAO CAO TUAN
# ============================================================

async def run_weekly_report() -> dict:
    """
    Tao va gui bao cao tuan.
    Chay Chu nhat 20:00.
    """
    logger.info("=" * 50)
    logger.info("ReportAgent: Bao cao TUAN")
    logger.info("=" * 50)

    today = today_vn()
    start = today - timedelta(days=7)

    # 1. Thu thap du lieu
    logger.info("Thu thap du lieu tuan...")
    data = await _collect_weekly_data()
    logger.info("Du lieu: %d tasks", data["total_tasks"])

    # 2. Goi LLM
    logger.info("Goi LLM tao bao cao...")
    report_text = await _generate_report(data)

    # 3. Xac dinh subject
    subject = f"[Zertdoo] Báo cáo tuần {format_date_vn(start)} - {format_date_vn(today)}"
    title = f"Báo cáo tuần {format_date_vn(start)} - {format_date_vn(today)}"

    # 4. Gui email
    logger.info("Gui email...")
    email_result = await _send_report_email(report_text, subject, title)

    # 5. Gui Telegram thong bao
    if settings.telegram_bot_token:
        try:
            from services.telegram_sender import send_message
            summary = report_text[:2000] if len(report_text) > 2000 else report_text
            await send_message(
                f"BÁO CÁO TUẦN đã gửi qua email.\n\n---\n\n{summary}"
            )
        except Exception as e:
            logger.error("Loi gui Telegram: %s", e)

    # 6. Log
    try:
        from services.database import log_agent
        await log_agent(
            agent_name="report_weekly",
            input_summary=f"Tuan {start} - {today}: {data['total_tasks']} tasks",
            output_summary=report_text[:500],
        )
    except Exception:
        pass

    logger.info("Bao cao tuan hoan thanh.")
    return {
        "type": "weekly",
        "email_id": email_result.get("id"),
        "report_length": len(report_text),
        "data": data,
    }


async def run_monthly_report() -> dict:
    """
    Tao va gui bao cao thang.
    Chay ngay 1 hang thang 08:00.
    """
    logger.info("=" * 50)
    logger.info("ReportAgent: Bao cao THANG")
    logger.info("=" * 50)

    today = today_vn()
    now = now_vn()
    month_str = now.strftime("%m/%Y")

    # 1. Thu thap du lieu
    logger.info("Thu thap du lieu thang...")
    data = await _collect_monthly_data()
    logger.info("Du lieu: %d tasks", data["total_tasks"])

    # 2. Goi LLM
    logger.info("Goi LLM tao bao cao...")
    report_text = await _generate_report(data)

    # 3. Gui email
    subject = f"[Zertdoo] Báo cáo tháng {month_str}"
    title = f"Báo cáo tháng {month_str}"

    logger.info("Gui email...")
    email_result = await _send_report_email(report_text, subject, title)

    # 4. Gui Telegram
    if settings.telegram_bot_token:
        try:
            from services.telegram_sender import send_message
            summary = report_text[:2000] if len(report_text) > 2000 else report_text
            await send_message(
                f"BÁO CÁO THÁNG đã gửi qua email.\n\n---\n\n{summary}"
            )
        except Exception as e:
            logger.error("Loi gui Telegram: %s", e)

    # 5. Log
    try:
        from services.database import log_agent
        await log_agent(
            agent_name="report_monthly",
            input_summary=f"Thang {month_str}: {data['total_tasks']} tasks",
            output_summary=report_text[:500],
        )
    except Exception:
        pass

    logger.info("Bao cao thang hoan thanh.")
    return {
        "type": "monthly",
        "email_id": email_result.get("id"),
        "report_length": len(report_text),
        "data": data,
    }


# ============================================================
# APSCHEDULER WRAPPERS (async - dung voi AsyncIOScheduler)
# ============================================================

async def run_weekly_scheduled_async():
    """Async wrapper cho AsyncIOScheduler - bao cao tuan."""
    logger.info("APScheduler trigger: bao cao tuan")
    try:
        result = await run_weekly_report()
        logger.info("Bao cao tuan xong: email_id=%s", result.get("email_id"))
    except Exception as e:
        logger.error("ReportAgent (tuan) loi: %s", e, exc_info=True)
        try:
            from services.telegram_sender import send_message
            await send_message(
                f"[LỖI] ReportAgent tuần thất bại: {type(e).__name__}: {e}"
            )
        except Exception:
            pass


async def run_monthly_scheduled_async():
    """Async wrapper cho AsyncIOScheduler - bao cao thang."""
    logger.info("APScheduler trigger: bao cao thang")
    try:
        result = await run_monthly_report()
        logger.info("Bao cao thang xong: email_id=%s", result.get("email_id"))
    except Exception as e:
        logger.error("ReportAgent (thang) loi: %s", e, exc_info=True)
        try:
            from services.telegram_sender import send_message
            await send_message(
                f"[LỖI] ReportAgent tháng thất bại: {type(e).__name__}: {e}"
            )
        except Exception:
            pass
