"""
Database service cho Zertdoo.
Su dung asyncpg connection pool (async) cho cac operations trong FastAPI.
Su dung psycopg (sync) cho scripts va testing.

Cung cap:
- init_pool / close_pool: quan ly connection pool lifecycle
- get_pool: lay pool hien tai
- Cac ham query: task logs, behavior stats, daily plans, agent logs
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import asyncpg

from config import settings

logger = logging.getLogger("zertdoo.database")

# === Connection Pool (global) ===
_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    """
    Khoi tao async connection pool.
    Goi 1 lan trong lifespan cua FastAPI.
    """
    global _pool

    # asyncpg khong ho tro tham so channel_binding
    # Neon connection string co the chua &channel_binding=require
    # Can loai bo truoc khi truyen vao asyncpg
    dsn = settings.database_url
    if "channel_binding" in dsn:
        # Loai bo channel_binding parameter
        parts = dsn.split("?")
        if len(parts) == 2:
            base = parts[0]
            params = [p for p in parts[1].split("&") if not p.startswith("channel_binding")]
            dsn = base + ("?" + "&".join(params) if params else "")

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    logger.info("Database connection pool da khoi tao (min=1, max=5).")
    return _pool


async def close_pool():
    """Dong connection pool. Goi khi server shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool da dong.")


def get_pool() -> asyncpg.Pool:
    """Lay pool hien tai. Raise neu chua init."""
    if _pool is None:
        raise RuntimeError("Database pool chua duoc khoi tao. Goi init_pool() truoc.")
    return _pool


async def ensure_pool() -> Optional[asyncpg.Pool]:
    """
    Dam bao pool san sang. Neu chua init hoac da dong, thu khoi tao lai.
    Tra ve pool hoac None neu khong the ket noi.
    """
    global _pool
    if _pool is not None:
        return _pool
    try:
        logger.info("Pool chua san sang, thu khoi tao lai...")
        await init_pool()
        return _pool
    except Exception as e:
        logger.error("Khong the khoi tao lai pool: %s", e)
        return None


async def check_db_health() -> dict:
    """
    Kiem tra tinh trang ket noi database.
    Tra ve dict voi status, latency, pool size.
    """
    if _pool is None:
        return {"status": "disconnected", "error": "Pool chua khoi tao"}
    try:
        import time
        start = time.time()
        val = await _pool.fetchval("SELECT 1")
        latency_ms = round((time.time() - start) * 1000, 1)
        return {
            "status": "connected",
            "latency_ms": latency_ms,
            "pool_size": _pool.get_size(),
            "pool_free": _pool.get_idle_size(),
            "pool_min": _pool.get_min_size(),
            "pool_max": _pool.get_max_size(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============================================================
# QUERY: Task Logs
# ============================================================

async def get_recent_task_logs(days: int = 30) -> list[dict]:
    """
    Lay lich su tasks trong N ngay gan nhat.
    Tra ve list[dict] de LLM doc duoc.
    """
    pool = get_pool()
    since = date.today() - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT id, task_name, source, sheet_name, category, priority,
               status, scheduled_date, scheduled_time_slot,
               duration_minutes, completed_at, created_at
        FROM task_logs
        WHERE scheduled_date >= $1
           OR created_at >= $2
        ORDER BY scheduled_date DESC NULLS LAST, created_at DESC
        """,
        since,
        datetime(since.year, since.month, since.day),
    )
    return [dict(r) for r in rows]


async def get_pending_tasks() -> list[dict]:
    """Lay tat ca tasks chua hoan thanh (pending, rescheduled)."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, task_name, source, sheet_name, category, priority,
               status, scheduled_date, scheduled_time_slot,
               duration_minutes, created_at
        FROM task_logs
        WHERE status IN ('pending', 'rescheduled')
        ORDER BY scheduled_date ASC NULLS LAST
        """
    )
    return [dict(r) for r in rows]


# ============================================================
# QUERY: Behavior Stats
# ============================================================

async def get_behavior_stats(days: int = 30) -> dict:
    """
    Tinh thong ke hanh vi nguoi dung tu task_logs va behavior_logs.
    Dung de cung cap context cho LLM.
    """
    pool = get_pool()
    since = date.today() - timedelta(days=days)

    # Thong ke tu task_logs
    stats_row = await pool.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'done') as done,
            COUNT(*) FILTER (WHERE status = 'skipped') as skipped,
            COUNT(*) FILTER (WHERE status = 'rescheduled') as rescheduled
        FROM task_logs
        WHERE scheduled_date >= $1 OR created_at >= $2
        """,
        since,
        datetime(since.year, since.month, since.day),
    )

    total = stats_row["total"] or 0
    done = stats_row["done"] or 0
    skipped = stats_row["skipped"] or 0
    rescheduled = stats_row["rescheduled"] or 0

    # Khung gio hoan thanh nhieu nhat
    productive_rows = await pool.fetch(
        """
        SELECT scheduled_time_slot, COUNT(*) as cnt
        FROM task_logs
        WHERE status = 'done'
          AND scheduled_time_slot IS NOT NULL
          AND (scheduled_date >= $1 OR created_at >= $2)
        GROUP BY scheduled_time_slot
        ORDER BY cnt DESC
        LIMIT 5
        """,
        since,
        datetime(since.year, since.month, since.day),
    )

    # So ngay co task
    days_with_tasks = await pool.fetchval(
        """
        SELECT COUNT(DISTINCT scheduled_date)
        FROM task_logs
        WHERE scheduled_date >= $1
        """,
        since,
    )
    active_days = days_with_tasks or 1

    return {
        "total_tasks_30d": total,
        "completed_tasks_30d": done,
        "skipped_tasks_30d": skipped,
        "rescheduled_tasks_30d": rescheduled,
        "completion_rate": round(done / total, 2) if total > 0 else 0.0,
        "avg_tasks_per_day": round(total / active_days, 1),
        "most_productive_hours": [r["scheduled_time_slot"] for r in productive_rows],
    }


# ============================================================
# QUERY: Daily Plans
# ============================================================

async def get_latest_daily_plan(plan_date: date) -> Optional[dict]:
    """Lay ke hoach cua 1 ngay cu the."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, plan_date, plan_json, confirmed, confirmed_at, created_at
        FROM daily_plans
        WHERE plan_date = $1
        """,
        plan_date,
    )
    return dict(row) if row else None


async def save_daily_plan(plan_date: date, plan_json: dict) -> int:
    """
    Luu ke hoach ngay moi. Neu da co plan cho ngay do, cap nhat.
    Tra ve id cua plan.
    """
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO daily_plans (plan_date, plan_json)
        VALUES ($1, $2::jsonb)
        ON CONFLICT (plan_date)
        DO UPDATE SET plan_json = $2::jsonb, created_at = NOW()
        RETURNING id
        """,
        plan_date,
        __import__("json").dumps(plan_json, ensure_ascii=False, default=str),
    )
    return row["id"]


async def confirm_daily_plan(plan_date: date) -> bool:
    """Danh dau ke hoach ngay la da xac nhan."""
    pool = get_pool()
    result = await pool.execute(
        """
        UPDATE daily_plans
        SET confirmed = TRUE, confirmed_at = NOW()
        WHERE plan_date = $1
        """,
        plan_date,
    )
    return "UPDATE 1" in result


# ============================================================
# WRITE: Task Logs
# ============================================================

async def save_task_log(
    task_name: str,
    source: str,
    sheet_name: str = None,
    category: str = None,
    priority: str = None,
    status: str = "pending",
    scheduled_date: date = None,
    scheduled_time_slot: str = None,
    duration_minutes: int = None,
) -> int:
    """Them 1 task log moi. Tra ve id."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO task_logs
            (task_name, source, sheet_name, category, priority,
             status, scheduled_date, scheduled_time_slot, duration_minutes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """,
        task_name, source, sheet_name, category, priority,
        status, scheduled_date, scheduled_time_slot, duration_minutes,
    )
    return row["id"]


async def update_task_status(task_id: int, new_status: str) -> bool:
    """Cap nhat trang thai cua 1 task. Neu done, ghi completed_at."""
    pool = get_pool()
    if new_status == "done":
        result = await pool.execute(
            """
            UPDATE task_logs
            SET status = $1, completed_at = NOW()
            WHERE id = $2
            """,
            new_status, task_id,
        )
    else:
        result = await pool.execute(
            """
            UPDATE task_logs
            SET status = $1
            WHERE id = $2
            """,
            new_status, task_id,
        )
    return "UPDATE 1" in result


# ============================================================
# WRITE: Behavior Logs
# ============================================================

async def log_behavior(action_type: str, context: dict = None) -> int:
    """Ghi 1 hanh vi vao behavior_logs."""
    pool = get_pool()
    import json
    row = await pool.fetchrow(
        """
        INSERT INTO behavior_logs (action_type, context)
        VALUES ($1, $2::jsonb)
        RETURNING id
        """,
        action_type,
        json.dumps(context or {}, ensure_ascii=False, default=str),
    )
    return row["id"]


# ============================================================
# WRITE: Agent Logs
# ============================================================

async def log_agent(
    agent_name: str,
    input_summary: str = None,
    output_summary: str = None,
    reasoning: str = None,
    llm_model: str = None,
    tokens_used: int = None,
    duration_ms: int = None,
    error: str = None,
) -> int:
    """Ghi log 1 lan agent chay."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO agent_logs
            (agent_name, input_summary, output_summary, reasoning,
             llm_model, tokens_used, duration_ms, error)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        agent_name, input_summary, output_summary, reasoning,
        llm_model, tokens_used, duration_ms, error,
    )
    return row["id"]


# ============================================================
# QUERY: Sync States
# ============================================================

async def get_latest_sync_state(source: str) -> Optional[dict]:
    """Lay snapshot dong bo gan nhat cua 1 nguon."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, source, state_snapshot, synced_at
        FROM sync_states
        WHERE source = $1
        ORDER BY synced_at DESC
        LIMIT 1
        """,
        source,
    )
    return dict(row) if row else None


async def save_sync_state(source: str, state_snapshot: dict) -> int:
    """Luu snapshot dong bo moi."""
    pool = get_pool()
    import json
    row = await pool.fetchrow(
        """
        INSERT INTO sync_states (source, state_snapshot)
        VALUES ($1, $2::jsonb)
        RETURNING id
        """,
        source,
        json.dumps(state_snapshot, ensure_ascii=False, default=str),
    )
    return row["id"]
