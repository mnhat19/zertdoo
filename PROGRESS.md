# TIEN DO DU AN ZERTDOO

> File nay duoc cap nhat tu dong sau moi lan thuc thi lenh.
> Tham chieu: AGENTS.md (nguon su that), PLAN.md (ke hoach chi tiet).

---

## Trang thai tong the

| Giai doan | Trang thai | Ghi chu |
|---|---|---|
| 0 - Ha tang va khung du an | DANG LAM | Code local xong, cho Koyeb + Neon PostgreSQL |
| 1 - Lop doc du lieu (Readers) | Chua bat dau | Google Sheets, Notion, Tasks, Calendar, Postgres readers |
| 2 - LLM Integration va Prompts | Chua bat dau | Gemini/Groq client, prompt engineering |
| 3 - Lop ghi du lieu va SchedulerAgent | Chua bat dau | Writers + pipeline len lich hang ngay |
| 4 - TelegramAgent | Chua bat dau | Tuong tac 2 chieu, thong bao chu dong |
| 5 - SyncAgent | Chua bat dau | Dong bo trang thai giua cac nguon |
| 6 - ReportAgent va Gmail | Chua bat dau | Bao cao dinh ky, gui email |
| 7 - Deploy, Hardening, Dashboard | Chua bat dau | Systemd, monitoring, web UI |

---

## Chi tiet tien do

### Giai doan 0: Ha tang va khung du an

- [ ] Dang ky Neon (neon.tech) - tao PostgreSQL database
- [ ] Chay init_db.sql tren Neon
- [ ] Tao Dockerfile cho Koyeb
- [ ] Dang ky Koyeb (app.koyeb.com) bang GitHub
- [ ] Deploy len Koyeb tu GitHub repo
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
- [ ] Cau hinh bien moi truong tren Koyeb
- [ ] Kiem tra: FastAPI /health qua URL cong khai Koyeb

### Giai doan 1: Lop doc du lieu

- [ ] models/schemas.py - Pydantic models
- [ ] services/google_sheets.py - Doc Sheet + forward-fill merged cells
- [ ] utils/sheet_parser.py - Xu ly merged cells
- [ ] services/notion.py - Doc Notion databases
- [ ] services/google_tasks.py - Doc Google Tasks
- [ ] services/google_calendar.py - Doc Google Calendar
- [ ] services/database.py - PostgreSQL connection + queries
- [ ] tests/test_sheets.py
- [ ] tests/test_notion.py
- [ ] tests/test_tasks.py
- [ ] tests/test_calendar.py

### Giai doan 2: LLM Integration va Prompts

- [ ] services/llm.py - Gemini + Groq client voi retry va fallback
- [ ] prompts/scheduler.txt - System prompt SchedulerAgent
- [ ] prompts/telegram.txt - System prompt TelegramAgent
- [ ] prompts/report.txt - System prompt ReportAgent
- [ ] Validation layer: parse + validate JSON tu LLM
- [ ] tests/test_llm.py

### Giai doan 3: Lop ghi du lieu va SchedulerAgent

- [ ] services/google_tasks.py - Them cac ham write (create, update, delete)
- [ ] services/google_calendar.py - Them cac ham write
- [ ] services/database.py - Them cac ham write (save plan, log task, log agent)
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

---

## Quyet dinh ky thuat

| Quyet dinh | Ly do |
|---|---|
| Python + FastAPI | Async native, ecosystem manh cho Google APIs va LLM |
| Koyeb (free nano) | 24/7, khong ngu, 256MB RAM, deploy tu GitHub, khong can credit card |
| Neon PostgreSQL | Free vinh vien, 0.5GB, 191h compute/thang, serverless |
| Gemini primary, Groq fallback | Gemini free tier lon (1500 req/ngay), context 1M tokens |
| APScheduler | Cron trong process, khong can Celery/Redis, giam phuc tap |

---

## Van de dang gap

(Chua co)
