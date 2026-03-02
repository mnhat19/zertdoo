-- Migration: them UNIQUE constraint cho task_logs
-- Chay 1 lan tren Neon PostgreSQL console

-- Buoc 1: Xoa cac ban ghi trung lap, giu lai ban ghi co id nho nhat
-- (ban ghi dau tien duoc tao, thuong la cai goc)
DELETE FROM task_logs
WHERE id NOT IN (
    SELECT MIN(id)
    FROM task_logs
    GROUP BY task_name, scheduled_date, source
);

-- Buoc 2: Them UNIQUE constraint de ON CONFLICT hoat dong
ALTER TABLE task_logs
    ADD CONSTRAINT uq_task_logs_name_date_source
    UNIQUE (task_name, scheduled_date, source);

-- Ket qua: moi cap (task_name, scheduled_date, source) chi co 1 ban ghi
-- SchedulerAgent chay lai nhieu lan se UPSERT thay vi INSERT moi
