# TIEN DO DU AN ZERTDOO

> File nay duoc cap nhat tu dong sau moi lan thuc thi lenh.
> Tham chieu: AGENTS.md (nguon su that), PLAN.md (ke hoach chi tiet).

---

## Trang thai tong the

| Giai doan | Trang thai | Ghi chu |
|---|---|---|
| 0 - Ha tang va khung du an | HOAN THANH | Render + Neon + UptimeRobot da hoat dong |
| 1 - Lop doc du lieu (Readers) | HOAN THANH | 5 readers + parser + schemas + database service |
| 2 - LLM Integration va Prompts | HOAN THANH | Gemini 2.5 Flash + Groq Llama 3.1 8B, 3 prompts, retry + fallback |
| 3 - Lop ghi du lieu va SchedulerAgent | HOAN THANH | SchedulerAgent full pipeline + APScheduler cron 6:00 AM |
| 4 - TelegramAgent | HOAN THANH | Webhook + handle_message + 3 notification jobs + action execution |
| 5 - SyncAgent | HOAN THANH | Polling 15 phut, change detection, dong bo Tasks/Sheet -> Postgres, deadline alerts |
| 6 - ReportAgent va Gmail | HOAN THANH | Gmail API + ReportAgent + cron tuan/thang |
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

- [x] services/llm.py - Gemini (google-genai SDK) + Groq client, retry 3 lan, exponential backoff, auto fallback
- [x] prompts/scheduler.txt - System prompt SchedulerAgent (uu tien, khung gio, reasoning)
- [x] prompts/telegram.txt - System prompt TelegramAgent (9 intents, action params)
- [x] prompts/report.txt - System prompt ReportAgent (bao cao tuan/thang)
- [x] Validation layer: _extract_json + _parse_and_validate trong llm.py
- [x] call_llm() - JSON output + Pydantic validation
- [x] call_llm_text() - Plain text output (cho ReportAgent)
- [x] tests/test_llm.py - 5 tests OK (extract, parse, Gemini JSON, Groq fallback, text)
- [x] tests/test_scheduler_prompt.py - Test voi du lieu mau, output chat luong

### Giai doan 3: Lop ghi du lieu va SchedulerAgent

- [x] services/google_tasks.py - Cac ham write + clear_task_list (idempotent) - da lam trong GD1
- [x] services/google_calendar.py - Cac ham write (create, update, delete) - da lam trong GD1
- [x] services/database.py - Cac ham write (save plan UPSERT, log task, log agent) - da lam trong GD1
- [x] agents/scheduler.py - SchedulerAgent hoan chinh (6 buoc: collect -> context -> LLM -> parse -> write -> summary)
- [x] APScheduler trong main.py: cron job 6:00 AM + endpoint /api/scheduler/run
- [x] tests/test_scheduler.py + tests/run_scheduler_now.py
- [x] Test thu cong 3 lan: du lieu that, LLM that, Tasks that, DB that, idempotent OK

### Giai doan 4: TelegramAgent

- [x] Tao bot qua BotFather, lay token + chat_id -> .env
- [x] services/telegram_sender.py - send_message (auto split >4096), set_webhook, delete_webhook
- [x] agents/telegram.py - TelegramAgent hoan chinh (context -> LLM -> actions -> reply)
- [x] Xu ly 9 intents: reschedule, reprioritize, query, mark_complete, add_task, cancel_task, alternative_plan, adjust_duration, general
- [x] Action execution: complete_task, create_task, delete_task, create_event, reschedule_plan
- [x] Route POST /webhook/telegram trong main.py (xac thuc secret token + ALLOWED_CHAT_ID)
- [x] Thong bao chu dong: 6:15 AM (morning summary), 12:00 PM (afternoon reminder), 9:00 PM (evening review)
- [x] APScheduler 3 cron jobs cho notifications
- [x] Bao mat: chi xu ly ALLOWED_CHAT_ID
- [x] Manual trigger endpoints: /api/telegram/test, /api/telegram/morning, /api/telegram/afternoon, /api/telegram/evening
- [x] models/schemas.py - TelegramAction + TelegramResponse Pydantic models
- [x] SchedulerAgent cap nhat: gui summary qua Telegram sau khi chay
- [x] tests/test_telegram.py - 3 tests OK (send, handle_message, morning summary)
- [x] tests/test_telegram_advanced.py - 3 kich ban phuc tap OK (reprioritize, reasoning, add_task)

### Giai doan 5: SyncAgent

- [x] agents/sync.py - SyncAgent hoan chinh (snapshot -> compare -> sync -> alert)
- [x] Snapshot Google Tasks: 135 tasks tu tat ca lists
- [x] Snapshot Google Sheets: 49 tasks tu tat ca worksheets
- [x] Change detection: so sanh snapshot cu vs moi, phat hien completed/new/removed
- [x] Dong bo completions vao Postgres task_logs (update_task_status)
- [x] Canh bao deadline: Priority High, due trong 24h, chua done -> gui Telegram
- [x] Thong bao thay doi quan trong qua Telegram
- [x] Luu sync_states snapshot vao Postgres sau moi lan chay
- [x] APScheduler IntervalTrigger moi 15 phut trong main.py
- [x] Manual trigger endpoint: POST /api/sync/run
- [x] Log agent_logs sau moi lan chay
- [x] tests/test_sync.py - 2 lan chay OK (tao snapshot + so sanh)
- [x] tests/test_sync_change.py - Mo phong tick completed -> phat hien 1 change, dong bo 1 task

### Giai doan 6: ReportAgent va Gmail

- [x] services/gmail.py - Gmail API sender (OAuth 2.0, scope gmail.send), send_email + format_report_html
- [x] agents/report.py - ReportAgent hoan chinh (collect data -> LLM -> format HTML -> send email -> Telegram notify -> log)
- [x] format_report_html: chuyen plain text -> HTML voi CSS inline (heading detection, list items, paragraphs)
- [x] _build_mime_message: MIME multipart + attachment (year_vision.jpg neu co)
- [x] _collect_weekly_data: query 7 ngay, phan loai theo category/date/status
- [x] _collect_monthly_data: query 30 ngay, phan loai theo category/week/date/status
- [x] run_weekly_report: full pipeline tuan (data -> LLM report.txt prompt -> HTML -> email -> Telegram)
- [x] run_monthly_report: full pipeline thang (tuong tu)
- [x] APScheduler 2 cron jobs: Chu nhat 20:00 (tuan), ngay 1 hang thang 08:00 (thang)
- [x] Manual trigger endpoints: POST /api/report/weekly, POST /api/report/monthly
- [x] Graceful handling: year_vision.jpg chua ton tai -> skip attachment, log warning
- [x] tests/test_report.py - 3 tests OK (format HTML, send email, full weekly pipeline)

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
| 01/03/2026 | GD2: Tao services/llm.py - Gemini (google-genai) + Groq client, retry + fallback. |
| 01/03/2026 | GD2: Tao 3 system prompts: scheduler.txt, telegram.txt, report.txt. |
| 01/03/2026 | GD2: Test OK: Gemini JSON, Groq fallback, text mode, scheduler prompt voi du lieu mau. |
| 01/03/2026 | Quyet dinh: Doi google-generativeai (deprecated) sang google-genai (SDK moi). |
| 01/03/2026 | Quyet dinh: Doi model tu gemini-2.0-flash sang gemini-2.5-flash, groq tu llama-3.3-70b sang llama-3.1-8b-instant. |
| 01/03/2026 | GD2: Phase 2 HOAN THANH. |
| 01/03/2026 | GD3: Tao agents/scheduler.py - full pipeline 6 buoc. |
| 01/03/2026 | GD3: Tich hop APScheduler vao main.py, cron 6:00 AM + /api/scheduler/run endpoint. |
| 01/03/2026 | GD3: Test 3 lan thanh cong: 10K ky tu context, Gemini xep 2-5 tasks, Google Tasks tao that, Postgres luu that. |
| 01/03/2026 | GD3: Fix idempotent: clear_task_list xoa tasks cu truoc khi tao lai. |
| 01/03/2026 | GD3: Phase 3 HOAN THANH. |
| 01/03/2026 | GD4: Tao services/telegram_sender.py - httpx async, send_message, set_webhook. |
| 01/03/2026 | GD4: Them TelegramAction + TelegramResponse vao schemas.py. |
| 01/03/2026 | GD4: Tao agents/telegram.py - handle_message (context -> LLM -> actions -> reply), 3 notifications (morning, afternoon, evening). |
| 01/03/2026 | GD4: Cap nhat main.py - webhook handler + 3 APScheduler notification jobs + 4 manual trigger endpoints. |
| 01/03/2026 | GD4: Test OK: gui tin nhan, phan tich intent (query/reprioritize/add_task), morning summary. |
| 01/03/2026 | GD4: Phase 4 HOAN THANH. |
| 01/03/2026 | GD5: Tao agents/sync.py - snapshot Tasks + Sheets, change detection, dong bo Postgres, deadline alerts. |
| 01/03/2026 | GD5: Cap nhat main.py - IntervalTrigger 15 phut + /api/sync/run endpoint. |
| 01/03/2026 | GD5: Test OK: snapshot 135 Tasks + 49 Sheet tasks, phat hien 1 change khi tick completed, dong bo 1 task vao DB. |
| 01/03/2026 | GD5: Phase 5 HOAN THANH. |
| 01/03/2026 | GD6: Tao services/gmail.py - Gmail API sender (OAuth 2.0, send_email + format_report_html + MIME attachment). |
| 01/03/2026 | GD6: Tao agents/report.py - ReportAgent (collect data -> LLM -> HTML -> email -> Telegram -> log). |
| 01/03/2026 | GD6: Cap nhat main.py - 2 cron jobs (CN 20:00 tuan, ngay 1 08:00 thang) + 2 manual trigger endpoints. |
| 01/03/2026 | GD6: Test OK: format HTML (1699 chars), send email (message_id OK), full weekly pipeline (10 tasks, 1327 chars report). |
| 01/03/2026 | GD6: Phase 6 HOAN THANH. |

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
| google-genai thay google-generativeai | google-generativeai da deprecated, google-genai la SDK moi chinh thuc |
| gemini-2.5-flash | Model moi nhat, ho tro JSON output tot, thinking mode |
| llama-3.1-8b-instant (Groq fallback) | Nho, nhanh, du cho fallback, free tier cao |
| clear_task_list truoc khi tao moi | Dam bao idempotent: chay lai khong tao trung tasks |
| Daily plan UPSERT | ON CONFLICT plan_date -> cap nhat thay vi tao moi |
| httpx cho Telegram API | Nhe hon python-telegram-bot, chi can gui tin nhan + webhook, khong can framework nang |
| Background task cho webhook | asyncio.create_task xu ly tin nhan -> tra 200 OK ngay cho Telegram (tranh timeout) |
| Webhook secret token | X-Telegram-Bot-Api-Secret-Token header xac thuc, tranh fake requests |
| Snapshot-based sync | Luu JSON snapshot toan bo trang thai, so sanh cu-moi de phat hien diff, tranh polling tung task |
| IntervalTrigger 15 phut | Can bang giua realtime va API quota, du nhanh cho use case ca nhan |

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
| google-generativeai FutureWarning deprecated | Chuyen sang google-genai==1.65.0 (SDK moi) |

## Van de dang gap

(Chua co)
