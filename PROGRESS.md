# TIEN DO DU AN ZERTDOO

> File nay duoc cap nhat tu dong sau moi lan thuc thi lenh.
> Tham chieu: AGENTS.md (nguon su that), PLAN.md (ke hoach chi tiet).

---

## Trang thai tong the

| Giai doan | Trang thai | Ghi chu |
|---|---|---|
| 0 - Ha tang va khung du an | HOAN THANH | Render + Neon + UptimeRobot da hoat dong |
| 1 - Lop doc du lieu (Readers) | HOAN THANH | 5 readers + parser + schemas + database service |
| 2 - LLM Integration va Prompts | Chua bat dau | Gemini/Groq client, prompt engineering |
| 3 - Lop ghi du lieu va SchedulerAgent | Chua bat dau | Writers + pipeline len lich hang ngay |
| 4 - TelegramAgent | Chua bat dau | Tuong tac 2 chieu, thong bao chu dong |
| 5 - SyncAgent | Chua bat dau | Dong bo trang thai giua cac nguon |
| 6 - ReportAgent va Gmail | Chua bat dau | Bao cao dinh ky, gui email |
| 7 - Deploy, Hardening, Dashboard | Chua bat dau | Systemd, monitoring, web UI |

---

## Chi tiet tien do

### Giai doan 0: Ha tang va khung du an

- [x] Dang ky Neon (neon.tech) - tao PostgreSQL database (Singapore, PostgreSQL 17.8)
- [x] Chay init_db.sql tren Neon (5 bang: task_logs, behavior_logs, agent_logs, daily_plans, sync_states)
- [x] Tao Dockerfile cho deploy
- [x] Tao render.yaml (Render blueprint)
- [x] Dang ky Render (render.com) bang GitHub
- [x] Deploy len Render tu GitHub repo - /health tra ve OK
- [x] Dang ky UptimeRobot - ping /health moi 5 phut
- [x] Khoi tao cau truc project (agents/, services/, models/, prompts/, utils/, tests/, scripts/, credentials/)
- [x] Tao requirements.txt (18 packages)
- [x] Tao config.py (Pydantic Settings, doc .env, singleton)
- [x] Tao .env.example (co huong dan chi tiet tung bien)
- [x] Tao main.py (FastAPI + /health + /webhook/telegram placeholder + lifespan)
- [x] Tao init_db.sql (5 bang + indexes)
- [x] Tao .gitignore
- [x] Tao utils/time_utils.py (timezone VN, format ngay, parse date)
- [x] Test: config.py doc duoc cau hinh -> OK
- [x] Test: FastAPI server chay, /health tra ve {"status": "ok"} -> OK
- [x] Test: time_utils format dung gio VN -> OK
- [x] Tao Dockerfile cho deploy
- [x] Cap nhat config.py: ho tro Google credentials base64 (cho cloud)
- [x] Cap nhat main.py: goi setup_google_credentials khi khoi dong
- [x] Cap nhat .env.example: them bien base64 cho cloud deploy
- [x] Tao render.yaml (Render blueprint)
- [x] Cau hinh bien moi truong tren Render (DATABASE_URL)
- [x] Kiem tra: FastAPI /health qua URL cong khai Render -> OK
- [x] Fix PORT env var: Render dung $PORT dong, khong hardcode 8000

### Giai doan 1: Lop doc du lieu

- [x] models/schemas.py - 12 Pydantic models (TaskItem, NotionNote, GoogleTask, CalendarEvent, BehaviorStats, ...)
- [x] services/database.py - asyncpg pool + CRUD + stats queries (Neon compatible)
- [x] services/google_auth.py - OAuth 2.0 helper, 4 scopes, token refresh
- [x] utils/sheet_parser.py - forward-fill merged cells + auto-detect column layout (2 layouts)
- [x] services/google_sheets.py - Doc Sheet, 6 worksheets, 49 tasks
- [x] services/google_tasks.py - Doc + ghi Google Tasks, 12 lists, 164 tasks
- [x] services/google_calendar.py - Doc + ghi Google Calendar, 2 events
- [x] services/notion.py - Doc Notion databases + pages, 1 db, 1 page
- [x] main.py updated - DB pool init/close trong lifespan
- [x] tests/test_database.py - OK
- [x] tests/test_sheets.py - OK (49 tasks, 6 sheets)
- [x] tests/test_tasks.py - OK (164 tasks, 12 lists)
- [x] tests/test_calendar.py - OK (2 events)
- [x] tests/test_notion.py - OK (1 database, 1 page)

### Giai doan 2: LLM Integration va Prompts

- [ ] services/llm.py - Gemini + Groq client voi retry va fallback
- [ ] prompts/scheduler.txt - System prompt SchedulerAgent
- [ ] prompts/telegram.txt - System prompt TelegramAgent
- [ ] prompts/report.txt - System prompt ReportAgent
- [ ] Validation layer: parse + validate JSON tu LLM
- [ ] tests/test_llm.py

### Giai doan 3: Lop ghi du lieu va SchedulerAgent

- [x] services/google_tasks.py - Cac ham write (create, complete, delete) - da lam trong GD1
- [x] services/google_calendar.py - Cac ham write (create, update, delete) - da lam trong GD1
- [x] services/database.py - Cac ham write (save plan, log task, log agent) - da lam trong GD1
- [ ] agents/scheduler.py - SchedulerAgent hoan chinh
- [ ] Dang ky APScheduler cron job 6:00 AM
- [ ] tests/test_scheduler.py
- [ ] Kiem tra: chay thu cong, xac nhan output dung

### Giai doan 4: TelegramAgent

- [ ] Tao bot qua BotFather, lay token
- [ ] Route POST /webhook/telegram trong main.py
- [ ] agents/telegram.py - TelegramAgent hoan chinh
- [ ] Xu ly cac intent: reschedule, reprioritize, query, mark_complete, ...
- [ ] Thong bao chu dong: 6:15 AM, 12:00 PM, 9:00 PM
- [ ] Bao mat: chi xu ly ALLOWED_CHAT_ID
- [ ] tests/test_telegram.py

### Giai doan 5: SyncAgent

- [ ] agents/sync.py - SyncAgent
- [ ] Change detection logic (so sanh snapshot)
- [ ] Dong bo 2 chieu: Tasks <-> Sheet <-> Postgres
- [ ] Conflict detection va thong bao
- [ ] Canh bao task sap deadline
- [ ] tests/test_sync.py

### Giai doan 6: ReportAgent va Gmail

- [ ] services/gmail.py - Gui email voi attachment
- [ ] agents/report.py - ReportAgent
- [ ] Template bao cao tuan (HTML)
- [ ] Template bao cao thang (HTML)
- [ ] Cron: Chu nhat 8:00 PM, ngay 1 hang thang 8:00 AM
- [ ] tests/test_report.py

### Giai doan 7: Deploy, Hardening, Dashboard

- [ ] Tao systemd service (auto-restart)
- [ ] Error handling toan he thong
- [ ] Health check endpoint /health
- [ ] Rate limit handling cho moi API
- [ ] Graceful degradation
- [ ] Web dashboard (uu tien thap)
- [ ] Test on dinh 72h

---

## Nhat ky thay doi

| Ngay | Noi dung |
|---|---|
| 01/03/2026 | Tao PLAN.md va PROGRESS.md. Du an bat dau. |
| 01/03/2026 | GD0: Tao cau truc project, config.py, main.py, init_db.sql, .env.example, .gitignore, time_utils.py. Test FastAPI OK. |
| 01/03/2026 | Quyet dinh: Doi tu Oracle Cloud sang Koyeb + Neon (khong co credit card). |
| 01/03/2026 | GD0: Tao Dockerfile, cap nhat config.py cho cloud (base64 credentials). |
| 01/03/2026 | Quyet dinh: Koyeb cung yeu cau credit card. Doi sang Render + Neon + UptimeRobot. |
| 01/03/2026 | GD0: Tao render.yaml, cap nhat PLAN.md cho Render. |
| 01/03/2026 | GD0: Dang ky Neon, test connection OK, chay init_db.sql (5 bang). |
| 01/03/2026 | GD0: Push code len GitHub (mnhat19/zertdoo). Deploy Render. |
| 01/03/2026 | GD0: Fix psycopg-binary build, fix PORT env var. Render /health OK. |
| 01/03/2026 | GD0: UptimeRobot setup - ping /health moi 5 phut. Phase 0 HOAN THANH. |
| 02/03/2026 | GD1: Tao models/schemas.py (12 Pydantic models), services/database.py (asyncpg pool). Test DB OK. |
| 02/03/2026 | GD1: Tao services/google_auth.py. Re-auth OAuth voi 4 scopes moi. |
| 02/03/2026 | GD1: Tao utils/sheet_parser.py. Phat hien 2 column layout khac nhau giua In_class va cac sheet khac. |
| 02/03/2026 | GD1: Tao services/google_sheets.py - 6 worksheets, 49 tasks. Auto-detect column layout. |
| 02/03/2026 | GD1: Tao services/google_tasks.py (read+write) - 12 lists, 164 tasks. |
| 02/03/2026 | GD1: Tao services/google_calendar.py (read+write) - 2 events. |
| 02/03/2026 | GD1: Tao services/notion.py - 1 database "Semester 2", 1 page. |
| 02/03/2026 | GD1: Tat ca 5 readers test OK voi du lieu that. Phase 1 HOAN THANH. |

---

## Quyet dinh ky thuat

| Quyet dinh | Ly do |
|---|---|
| Python + FastAPI | Async native, ecosystem manh cho Google APIs va LLM |
| Render (free web service) | Khong can credit card, 750h free/thang, dung UptimeRobot ping giu song 24/7 |
| Neon PostgreSQL | Free vinh vien, 0.5GB, 191h compute/thang, serverless |
| Gemini primary, Groq fallback | Gemini free tier lon (1500 req/ngay), context 1M tokens |
| APScheduler | Cron trong process, khong can Celery/Redis, giam phuc tap |
| asyncpg thay psycopg | Nhanh hon, native async, tuong thich Neon (sau khi strip channel_binding) |
| Auto-detect column layout | In_class co 8 cot (them Deadlines), cac sheet khac 7 cot. Parser doc header row de xac dinh |
| Write methods trong Phase 1 | Tasks + Calendar + DB write methods lam luon trong GD1 de tien test va GD3 chi can focus SchedulerAgent |

---

## Van de da giai quyet

| Van de | Giai phap |
|---|---|
| Oracle Cloud yeu cau credit card | Doi sang Render + Neon + UptimeRobot |
| Koyeb cung yeu cau credit card | Doi sang Render |
| psycopg[binary] khong build tren Render slim image | Doi sang psycopg-binary==3.2.4 (prebuilt) |
| Render 503 - app bind sai port | Doi CMD dung `${PORT:-8000}` thay vi hardcode 8000 |
| asyncpg khong ho tro channel_binding param | Strip channel_binding tu Neon DSN truoc khi connect |
| OAuth invalid_scope (token cu thieu scopes) | Xoa token.json, re-auth voi 4 scopes day du |
| Google Sheets parse sai data (In_class khac layout) | Tao detect_column_layout() doc header row, tu dong map cot |

## Van de dang gap

(Chua co)
