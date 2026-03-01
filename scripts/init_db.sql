-- ============================================================
-- ZERTDOO - KHOI TAO DATABASE
-- ============================================================
-- Chay file nay de tao cac bang can thiet:
--   psql -U zertdoo -d zertdoo -f scripts/init_db.sql
-- ============================================================

-- Bang 1: Lich su tasks (moi task duoc tao/cap nhat boi he thong)
CREATE TABLE IF NOT EXISTS task_logs (
    id SERIAL PRIMARY KEY,
    task_name TEXT NOT NULL,
    source TEXT NOT NULL,                -- 'sheet', 'tasks', 'telegram', 'notion'
    sheet_name TEXT,                     -- ten worksheet (neu tu Google Sheet)
    category TEXT,                       -- category/domain (neu tu Sheet)
    priority TEXT,                       -- 'High', 'Medium', 'Low'
    status TEXT DEFAULT 'pending',       -- 'pending', 'done', 'skipped', 'rescheduled'
    scheduled_date DATE,                -- ngay duoc len lich
    scheduled_time_slot TEXT,           -- khung gio (VD: '08:00 - 09:30')
    duration_minutes INTEGER,           -- thoi luong du kien (phut)
    completed_at TIMESTAMPTZ,           -- thoi diem hoan thanh
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index de truy van nhanh theo ngay va trang thai
CREATE INDEX IF NOT EXISTS idx_task_logs_date ON task_logs (scheduled_date);
CREATE INDEX IF NOT EXISTS idx_task_logs_status ON task_logs (status);

-- Bang 2: Lich su hanh vi nguoi dung
-- Ghi lai moi hanh dong de LLM hoc thoi quen, pattern
CREATE TABLE IF NOT EXISTS behavior_logs (
    id SERIAL PRIMARY KEY,
    action_type TEXT NOT NULL,           -- 'task_completed', 'task_skipped', 'reschedule',
                                         -- 'reprioritize', 'plan_confirmed', 'plan_rejected'
    context JSONB,                       -- thong tin bo sung (task nao, ly do, ...)
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_behavior_logs_time ON behavior_logs (timestamp);
CREATE INDEX IF NOT EXISTS idx_behavior_logs_type ON behavior_logs (action_type);

-- Bang 3: Log moi lan agent chay
-- De debug, phan tich hieu suat, theo doi chi phi LLM
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,            -- 'scheduler', 'telegram', 'sync', 'report'
    input_summary TEXT,                  -- tom tat input da gui cho LLM
    output_summary TEXT,                 -- tom tat output LLM tra ve
    reasoning TEXT,                      -- ly giai chi tiet cua LLM
    llm_model TEXT,                      -- 'gemini-2.0-flash', 'llama-3.3-70b-versatile'
    tokens_used INTEGER,                 -- so token da dung
    duration_ms INTEGER,                 -- thoi gian xu ly (millisecond)
    error TEXT,                          -- thong bao loi (neu co)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_name ON agent_logs (agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_logs_time ON agent_logs (created_at);

-- Bang 4: Ke hoach hang ngay
-- Moi ngay 1 ban ke hoach, chua JSON day du tu LLM
CREATE TABLE IF NOT EXISTS daily_plans (
    id SERIAL PRIMARY KEY,
    plan_date DATE NOT NULL UNIQUE,      -- moi ngay chi co 1 plan
    plan_json JSONB NOT NULL,            -- toan bo output cua SchedulerAgent
    confirmed BOOLEAN DEFAULT FALSE,     -- nguoi dung da xac nhan chua
    confirmed_at TIMESTAMPTZ,            -- thoi diem xac nhan
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans (plan_date);

-- Bang 5: Trang thai dong bo
-- Luu snapshot de phat hien thay doi giua cac lan sync
CREATE TABLE IF NOT EXISTS sync_states (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,                -- 'google_tasks', 'google_sheet', 'google_calendar'
    state_snapshot JSONB NOT NULL,       -- snapshot trang thai tai thoi diem sync
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_states_source ON sync_states (source);
CREATE INDEX IF NOT EXISTS idx_sync_states_time ON sync_states (synced_at);

-- ============================================================
-- Xac nhan
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE 'Zertdoo: Tao 5 bang thanh cong (task_logs, behavior_logs, agent_logs, daily_plans, sync_states)';
END $$;
