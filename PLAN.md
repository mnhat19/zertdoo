# KE HOACH DU AN ZERTDOO

## Tong quan ky thuat

| Hang muc | Lua chon |
|---|---|
| Ngon ngu | Python 3.11+ |
| Web framework | FastAPI + Uvicorn |
| LLM chinh | Gemini 2.0 Flash (fallback: Groq Llama 3.3 70B) |
| Database | PostgreSQL (Neon - serverless, free tier) |
| Deploy | Render free (512MB RAM, 24/7 voi UptimeRobot pinger) |
| Cron/Scheduler | APScheduler (trong process) |
| Reverse proxy | Render tu cung cap HTTPS + domain .onrender.com |

---

## Cau truc thu muc

```
zertdoo/
  main.py                  # FastAPI entry point, khoi dong APScheduler
  config.py                # Bien moi truong, Pydantic Settings
  .env                     # Secrets (khong commit)
  Dockerfile               # Build image cho Render
  render.yaml              # Cau hinh Render deploy (Infrastructure as Code)
  requirements.txt         # Dependencies
  agents/
    scheduler.py           # SchedulerAgent - len lich hang ngay
    telegram.py            # TelegramAgent - tuong tac 2 chieu
    sync.py                # SyncAgent - dong bo trang thai
    report.py              # ReportAgent - bao cao dinh ky
  services/
    llm.py                 # Gemini + Groq client, retry, fallback
    google_sheets.py       # Doc Google Sheet (xu ly merged cells)
    google_tasks.py        # CRUD Google Tasks
    google_calendar.py     # CRUD Google Calendar
    gmail.py               # Gui email voi attachment
    notion.py              # Doc Notion databases
    database.py            # PostgreSQL connection, queries
  models/
    schemas.py             # Pydantic models cho task, event, log
    db_models.py           # Database schema definitions
  prompts/
    scheduler.txt          # System prompt cho SchedulerAgent
    telegram.txt           # System prompt cho TelegramAgent
    report.txt             # System prompt cho ReportAgent
  utils/
    sheet_parser.py        # Forward-fill merged cells, validate rows
    time_utils.py          # Timezone, format ngay gio VN
  tests/
    test_sheets.py
    test_tasks.py
    test_calendar.py
    test_notion.py
    test_llm.py
    test_scheduler.py
    test_telegram.py
    test_sync.py
    test_report.py
```

---

## Cac giai doan thuc hien

### Giai doan 0: Ha tang va khung du an

**Muc tieu:** Render chay duoc FastAPI server 24/7, Neon PostgreSQL ket noi duoc, project co cau truc.

**Viec can lam:**

1. **Neon PostgreSQL (database mien phi):**
   - Truy cap https://neon.tech va dang ky bang GitHub
   - Tao project moi, chon region gan nhat (Singapore)
   - Copy connection string (dang: postgresql://user:pass@host/dbname?sslmode=require)
   - Chay file `scripts/init_db.sql` de tao 5 bang

2. **Khoi tao project (da hoan thanh):**
   - Cau truc thu muc, requirements.txt, config.py, .env.example, main.py
   - PostgreSQL schema: init_db.sql
   - Utils: time_utils.py

3. **Dockerfile cho Render:**
   - Base image: python:3.11-slim
   - Copy code, cai dependencies, chay uvicorn
   - Render se build tu Dockerfile nay

4. **Render (hosting mien phi):**
   - Truy cap https://render.com va dang ky bang GitHub, KHONG can credit card
   - Tao Web Service moi, tro den GitHub repo
   - Chon Docker runtime
   - Cau hinh bien moi truong (tu .env)
   - Render tu dong cung cap domain HTTPS (vd: zertdoo.onrender.com)
   - Van de: free tier ngu sau 15 phut idle
   - Giai phap: dung UptimeRobot (mien phi) ping /health moi 5 phut -> server khong ngu
   - 750 gio free/thang = du 24/7 (1 thang chi can 720 gio)

5. **UptimeRobot (giu server song):**
   - Truy cap https://uptimerobot.com va dang ky (mien phi)
   - Tao monitor moi: HTTP(s), URL = https://zertdoo.onrender.com/health
   - Interval: 5 phut
   - Server se khong bao gio ngu

6. **Google credentials:**
   - Luu credentials duoi dang bien moi truong (base64 encode) thay vi file
   - Render khong co filesystem co dinh, phai doc tu env var
   - Code se decode va tao file tam khi khoi dong

4. **PostgreSQL schema ban dau:**
   ```sql
   CREATE TABLE task_logs (
       id SERIAL PRIMARY KEY,
       task_name TEXT NOT NULL,
       source TEXT NOT NULL,           -- 'sheet', 'tasks', 'telegram'
       sheet_name TEXT,
       category TEXT,
       priority TEXT,
       status TEXT DEFAULT 'pending',  -- 'pending', 'done', 'skipped', 'rescheduled'
       scheduled_date DATE,
       scheduled_time_slot TEXT,
       completed_at TIMESTAMPTZ,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE behavior_logs (
       id SERIAL PRIMARY KEY,
       action_type TEXT NOT NULL,      -- 'task_completed', 'task_skipped', 'reschedule', ...
       context JSONB,
       timestamp TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE agent_logs (
       id SERIAL PRIMARY KEY,
       agent_name TEXT NOT NULL,       -- 'scheduler', 'telegram', 'sync', 'report'
       input_summary TEXT,
       output_summary TEXT,
       reasoning TEXT,
       llm_model TEXT,
       tokens_used INTEGER,
       duration_ms INTEGER,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE daily_plans (
       id SERIAL PRIMARY KEY,
       plan_date DATE NOT NULL UNIQUE,
       plan_json JSONB NOT NULL,
       confirmed BOOLEAN DEFAULT FALSE,
       confirmed_at TIMESTAMPTZ,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE sync_states (
       id SERIAL PRIMARY KEY,
       source TEXT NOT NULL,           -- 'google_tasks', 'google_sheet'
       state_snapshot JSONB NOT NULL,
       synced_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

5. **Google credentials:**
   - Luu credentials duoi dang bien moi truong (base64 encode) thay vi file
   - Koyeb khong co filesystem co dinh, phai doc tu env var
   - Code se decode va tao file tam khi khoi dong

**Tieu chi hoan thanh:**
- Neon PostgreSQL ket noi duoc, 5 bang da tao
- Render deploy thanh cong, truy cap `https://zertdoo.onrender.com/health` tra ve ok
- UptimeRobot ping thanh cong, server khong bi ngu
- Bien moi truong cau hinh dung tren Render
- Truy cap `https://zertdoo.onrender.com/docs` thay FastAPI Swagger UI

---

### Giai doan 1: Lop doc du lieu (Data Readers)

**Muc tieu:** Doc duoc toan bo du lieu tu moi nguon input, chuan hoa thanh Pydantic models.

**Viec can lam:**

1. **Google Sheets reader** (`services/google_sheets.py`):
   - Xac thuc bang credentials
   - Lay danh sach tat ca worksheets trong spreadsheet
   - Doc du lieu tu hang 2 tro di moi worksheet
   - Forward-fill cot A (Category) khi gap o merge/trong
   - Bo qua hang trong, hang phan cach
   - Tra ve: `list[TaskItem]` voi `TaskItem` la Pydantic model

2. **Notion reader** (`services/notion.py`):
   - Xac thuc bang Notion integration token
   - List tat ca databases duoc share voi integration
   - Doc toan bo pages tu moi database
   - Trich xuat: title, noi dung (plain text), properties
   - Tra ve: `list[NotionNote]`

3. **Google Tasks reader** (`services/google_tasks.py`):
   - List tat ca task lists
   - Doc tasks tu moi list (bao gom completed va incomplete)
   - Tra ve: `list[GoogleTask]`

4. **Google Calendar reader** (`services/google_calendar.py`):
   - Doc events trong khoang: hom nay den 7 ngay toi
   - Tra ve: `list[CalendarEvent]`

5. **PostgreSQL reader** (`services/database.py`):
   - Ket noi async voi asyncpg
   - Cac ham query:
     - `get_recent_task_logs(days=30)` -> lich su task
     - `get_behavior_stats(days=30)` -> thong ke hanh vi
     - `get_latest_daily_plan(date)` -> ke hoach hom nay
   - Connection pool de tai su dung ket noi

6. **Pydantic models** (`models/schemas.py`):
   ```python
   class TaskItem:       # Tu Google Sheet
   class NotionNote:     # Tu Notion
   class GoogleTask:     # Tu Google Tasks
   class CalendarEvent:  # Tu Google Calendar
   class BehaviorStats:  # Tu PostgreSQL
   ```

**Tieu chi hoan thanh:**
- Moi reader co test rieng, chay voi du lieu that, in ra console dung
- Du lieu duoc chuan hoa thanh Pydantic models, khong co loi validation
- Forward-fill Category hoat dong dung voi merged cells

---

### Giai doan 2: LLM Integration va Prompt Engineering

**Muc tieu:** LLM nhan du lieu, tra ve lich trinh co ly giai, format JSON chuan.

**Viec can lam:**

1. **LLM client** (`services/llm.py`):
   - Gemini client:
     - Model: `gemini-2.0-flash`
     - Config: temperature thap (0.2-0.3) cho ket qua on dinh
     - Structured output: yeu cau tra JSON
   - Groq client:
     - Model: `llama-3.3-70b-versatile`
     - Fallback khi Gemini bi rate limit hoac loi
   - Logic chung:
     - Ham `call_llm(system_prompt, user_content, response_schema)` -> dict
     - Retry 3 lan voi exponential backoff
     - Tu dong chuyen sang Groq neu Gemini fail
     - Log moi lan goi: model, tokens, duration -> `agent_logs`

2. **Prompt SchedulerAgent** (`prompts/scheduler.txt`):
   - Role: AI scheduler ca nhan, hieu nguoi dung sau nhieu ngay quan sat
   - Input: tasks chua xong, notes, lich su 30 ngay, events hien tai, ngay/thu hien tai
   - Rang buoc:
     - Moi task phai co reasoning tai sao o vi tri nay
     - Phai tinh due date, khong de qua han
     - Phai tinh thoi luong thuc te dua tren lich su hoan thanh
     - Neu co conflict, phai canh bao
     - Neu co dieu khong chac, phai dua vao `questions_for_user`
   - Output JSON schema:
     ```json
     {
       "daily_tasks": [
         {
           "title": "string",
           "source": "string (sheet_name/category)",
           "priority_rank": "number",
           "time_slot": "string (HH:MM - HH:MM)",
           "duration_minutes": "number",
           "reasoning": "string"
         }
       ],
       "events_to_create": [
         {
           "title": "string",
           "start": "ISO datetime",
           "end": "ISO datetime",
           "description": "string"
         }
       ],
       "risks": ["string"],
       "questions_for_user": ["string"],
       "overall_reasoning": "string"
     }
     ```

3. **Prompt TelegramAgent** (`prompts/telegram.txt`):
   - Role: tro ly thong minh, giao tiep bang tieng Viet, khong emoji
   - Input: tin nhan nguoi dung, tasks hom nay, lich su, events
   - Phan loai intent va quyet dinh hanh dong
   - Output JSON schema:
     ```json
     {
       "intent": "string",
       "response_message": "string",
       "actions": [
         {
           "type": "string (update_task/create_event/reschedule/...)",
           "params": {}
         }
       ]
     }
     ```

4. **Prompt ReportAgent** (`prompts/report.txt`):
   - Role: nha phan tich nang suat ca nhan
   - Input: thong ke tuan/thang tu Postgres
   - Output: bao cao dang text, co cau truc, thuc te, truc tiep

5. **Validation layer:**
   - Parse JSON tu LLM response
   - Validate bang Pydantic models tuong ung
   - Neu parse loi: retry voi prompt bo sung yeu cau sua format
   - Neu retry van loi: log va thong bao loi

**Tieu chi hoan thanh:**
- Goi Gemini voi du lieu mau, nhan JSON hop le
- Fallback sang Groq hoat dong khi tat Gemini
- Retry logic hoat dong dung
- Prompt tra ve reasoning co y nghia, khong chung chung

---

### Giai doan 3: Lop ghi du lieu va SchedulerAgent

**Muc tieu:** He thong tu dong tao lich hang ngay, ghi vao Google Tasks + Calendar + Postgres.

**Viec can lam:**

1. **Google Tasks writer** (bo sung `services/google_tasks.py`):
   - `create_task_list(title)` -> tao list moi theo ngay
   - `add_task(list_id, title, notes, due)` -> them task vao list
   - `update_task_status(list_id, task_id, completed)` -> cap nhat trang thai
   - `delete_task(list_id, task_id)` -> xoa task
   - Xu ly trung lap: kiem tra list + task da ton tai truoc khi tao

2. **Google Calendar writer** (bo sung `services/google_calendar.py`):
   - `create_event(summary, start, end, description)` -> tao event
   - `update_event(event_id, ...)` -> sua event
   - `delete_event(event_id)` -> xoa event
   - Xu ly trung lap: kiem tra event cung title + thoi gian

3. **PostgreSQL writer** (bo sung `services/database.py`):
   - `save_daily_plan(date, plan_json)` -> luu ke hoach ngay
   - `log_task(task_name, source, ...)` -> luu task log
   - `log_agent_run(agent_name, ...)` -> luu agent log
   - `log_behavior(action_type, context)` -> luu hanh vi

4. **SchedulerAgent hoan chinh** (`agents/scheduler.py`):
   - Luong xu ly:
     ```
     1. Thu thap: goi tat ca readers (Sheet, Notion, Postgres, Tasks, Calendar)
     2. Xay dung context: gop du lieu thanh chuoi/JSON cho LLM
     3. Goi LLM: truyen system prompt + context
     4. Parse response: validate JSON
     5. Ghi output: tao Tasks, tao Calendar events, luu Postgres
     6. Tra ve summary: de gui Telegram o buoc tiep theo
     ```
   - Dang ky APScheduler: `CronTrigger(hour=6, minute=0, timezone='Asia/Ho_Chi_Minh')`
   - Error handling: neu bat ky buoc nao loi, log va gui Telegram thong bao

**Tieu chi hoan thanh:**
- Chay `SchedulerAgent.run()` thu cong
- Google Tasks co task list moi voi cac task dung thu tu
- Google Calendar co events dung
- Postgres co daily_plan, task_logs, agent_logs
- Chay lai khong tao trung

---

### Giai doan 4: TelegramAgent

**Muc tieu:** Nguoi dung tuong tac 2 chieu qua Telegram, he thong hieu va thuc thi.

**Viec can lam:**

1. **Tao Telegram bot:**
   - Nhan tin @BotFather tren Telegram, tao bot moi
   - Lay BOT_TOKEN, luu vao `.env`
   - Set webhook URL: `https://domain/webhook/telegram`

2. **Webhook endpoint** (`main.py`):
   - Route `POST /webhook/telegram`
   - Xac thuc: chi xu ly update tu Telegram (kiem tra secret token)
   - Parse Update object, chuyen den TelegramAgent

3. **TelegramAgent** (`agents/telegram.py`):
   - Bao mat: chi xu ly message tu `ALLOWED_CHAT_ID` (config trong .env)
   - Luong xu ly moi message:
     ```
     1. Nhan message text
     2. Lay context: daily_plan hom nay, tasks, events, lich su gan nhat
     3. Goi LLM voi TelegramAgent prompt + context + message
     4. Parse response: intent + actions + reply
     5. Thuc thi actions: goi writers tuong ung
     6. Gui reply ve Telegram
     ```
   - Cac intent ho tro:
     - `reschedule`: doi gio/ngay cua task
     - `reprioritize`: sap xep lai thu tu uu tien
     - `query_status`: hoi trang thai tien do
     - `query_reasoning`: hoi tai sao sap xep nhu vay
     - `mark_complete`: bao hoan thanh task
     - `alternative_plan`: yeu cau phuong an thay the
     - `general_chat`: hoi dap chung lien quan den cong viec
     - `update_info`: nguoi dung cung cap thong tin moi

4. **Thong bao chu dong** (APScheduler jobs):
   - 6:15 AM: tom tat lich ngay (sau khi SchedulerAgent chay)
   - 12:00 PM: nhac tasks buoi chieu
   - 9:00 PM: review cuoi ngay -- chua xong gi, de xuat xu ly
   - Khi SyncAgent phat hien van de: gui canh bao ngay

5. **Gui tin nhan** (`services/telegram_sender.py` hoac tich hop):
   - Ham `send_message(chat_id, text)` -- plain text, khong emoji
   - Ham `send_message_with_confirm(chat_id, text, options)` -- co nut xac nhan
   - Xu ly tin nhan dai: chia nho neu vuot 4096 ky tu

**Tieu chi hoan thanh:**
- Gui tin nhan cho bot, nhan phan hoi dung intent
- "doi task X sang chieu" -> Google Tasks + Calendar duoc cap nhat
- "trang thai hom nay" -> nhan tom tat chinh xac
- Thong bao chu dong gui dung gio

---

### Giai doan 5: SyncAgent

**Muc tieu:** Dong bo trang thai giua cac nguon, phat hien thay doi va conflict.

**Viec can lam:**

1. **SyncAgent** (`agents/sync.py`):
   - APScheduler interval job: chay moi 15 phut
   - Moi lan chay:
     ```
     1. Doc trang thai hien tai tu Google Tasks
     2. Doc trang thai hien tai tu Google Sheet (cot Status)
     3. So sanh voi sync_states moi nhat trong Postgres
     4. Phat hien thay doi:
        - Task duoc tick completed trong Tasks -> cap nhat Sheet + Postgres
        - Task duoc danh "Done" trong Sheet -> cap nhat Tasks + Postgres
        - Task bi xoa/sua trong Calendar -> log + thong bao
     5. Luu sync_states moi vao Postgres
     ```

2. **Change detection:**
   - Luu state snapshot (JSON) sau moi lan sync
   - So sanh snapshot cu vs moi -> tim diff
   - Danh dau nguon thay doi (`changed_by: 'user' | 'system'`) de tranh vong lap

3. **Conflict handling:**
   - Neu cung 1 task co trang thai khac nhau o 2 nguon -> log conflict
   - Gui Telegram: trinh bay conflict, hoi nguoi dung chon
   - Neu nguoi dung khong tra loi trong 1h -> dung trang thai moi nhat (theo timestamp)

4. **Canh bao:**
   - Task priority High, due trong 24h, status chua done -> gui Telegram
   - Phat hien pattern: 3 ngay lien tiep co task bi skip -> gui phan tich

**Tieu chi hoan thanh:**
- Tick task trong Google Tasks -> 15 phut sau Postgres cap nhat, Sheet cap nhat
- Dien "Done" trong Sheet -> Tasks va Postgres dong bo
- Conflict duoc phat hien va thong bao qua Telegram

---

### Giai doan 6: ReportAgent va Gmail

**Muc tieu:** Bao cao dinh ky tu dong, gui email co dinh kem.

**Viec can lam:**

1. **Gmail sender** (`services/gmail.py`):
   - Xac thuc bang Google OAuth credentials (scope: gmail.send)
   - Tao email MIME:
     - To: `nhatdm234112e@st.uel.edu.vn`
     - Subject: "[Zertdoo] Bao cao tuan DD/MM - DD/MM" hoac "Bao cao thang MM/YYYY"
     - Body: HTML formatted
     - Attachment: `year_vision.jpg`
   - Gui bang Gmail API (khong phai SMTP)

2. **ReportAgent** (`agents/report.py`):
   - Cron jobs:
     - Chu nhat 8:00 PM: bao cao tuan
     - Ngay 1 hang thang 8:00 AM: bao cao thang
   - Luong xu ly:
     ```
     1. Query Postgres: task_logs, behavior_logs, agent_logs trong ky
     2. Tinh toan: ti le hoan thanh, tasks skip, pattern gio lam viec, ...
     3. Goi LLM voi ReportAgent prompt + data
     4. Nhan bao cao text
     5. Format thanh HTML
     6. Gui email voi attachment
     7. Log vao agent_logs
     ```

3. **Noi dung bao cao tuan:**
   - Tong so tasks: hoan thanh / tong
   - Ti le hoan thanh theo category
   - Tasks bi bo qua hoac reschedule nhieu lan
   - Pattern hanh vi: gio nao lam viec hieu qua nhat, ngay nao hay skip
   - De xuat cu the cho tuan toi

4. **Noi dung bao cao thang:**
   - Tat ca noi dung tuan + tong hop
   - Tien do muc tieu dai han (neu co trong Sheet/Notion)
   - So sanh voi thang truoc
   - Xu huong tich cuc va tieu cuc

**Tieu chi hoan thanh:**
- Trigger thu cong: nhan email voi noi dung bao cao + attachment
- HTML format doc duoc, khong loi hien thi
- Noi dung phan tich co y nghia, khong chung chung

---

### Giai doan 7: Deploy, Hardening va Web Dashboard

**Muc tieu:** He thong chay on dinh 24/7, co monitoring.

**Viec can lam:**

1. **Render auto-deploy:**
   - Ket noi GitHub repo, moi lan push code Render tu build lai
   - Health check endpoint /health de Render detect loi
   - Render tu dong restart khi container crash
   - UptimeRobot ping moi 5 phut giu server song

2. **Error handling toan he thong:**
   - Moi agent co try-except bao quanh
   - Khi loi nghiem trong: gui Telegram thong bao ngay
   - Rate limit: implement token bucket cho moi API
   - Graceful degradation: neu Google Sheets loi, van doc duoc tu Postgres cache

3. **Health check endpoint:**
   - `GET /health` -> tra ve trang thai moi service (da co)
   - Dung de monitoring tu ben ngoai (UptimeRobot free)

4. **Web dashboard** (uu tien thap, lam sau cung):
   - FastAPI + Jinja2 templates (hoac static HTML + JS)
   - Trang chinh: tasks hom nay, ti le hoan thanh, upcoming deadlines
   - Trang phan tich: bieu do theo tuan, pattern hanh vi
   - Bao mat: basic auth hoac xac thuc qua Telegram

**Tieu chi hoan thanh:**
- He thong chay lien tuc 72h khong loi
- Tu khoi dong khi container crash
- Telegram thong bao khi co loi
- Health check endpoint tra ve dung trang thai

---

## Nguyen tac xuyen suot

1. **LLM la trung tam:** Khong xay thuat toan sap xep/uu tien thu cong. Moi quyet dinh logic do LLM dua ra.
2. **Moi output co reasoning:** Task nao cung phai di kem ly do tai sao o vi tri do.
3. **Khong emoji, khong icon:** Toan bo tin nhan, bao cao, giao dien deu plain text.
4. **Mien phi 100%:** Chi dung free tier cua moi dich vu.
5. **Test truoc khi di tiep:** Moi giai doan phai dat tieu chi hoan thanh truoc khi sang giai doan ke.
6. **AGENTS.md la nguon su that:** Moi thay doi kien truc phai cap nhat vao AGENTS.md.

---

## Phu thuoc giua cac giai doan

```
Giai doan 0 (Ha tang)
    |
    v
Giai doan 1 (Readers)
    |
    v
Giai doan 2 (LLM + Prompts)
    |
    v
Giai doan 3 (Writers + SchedulerAgent)  -->  Giai doan 4 (TelegramAgent)
                                                  |
                                                  v
                                             Giai doan 5 (SyncAgent)
                                                  |
                                                  v
                                             Giai doan 6 (ReportAgent)
                                                  |
                                                  v
                                             Giai doan 7 (Deploy + Dashboard)
```

Giai doan 3 va 4 co the lam song song mot phan (Writers dung chung).
Giai doan 5, 6, 7 phu thuoc vao cac giai doan truoc nhung doc lap voi nhau.
