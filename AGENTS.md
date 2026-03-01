# AGENTS.md - Zertdoo

## Tổng quan

**Tên dự án:** Zertdoo

**Mục tiêu cốt lõi:** Xây dựng một hệ thống AI agent cá nhân, hoàn toàn tự động hóa quy trình lên lịch và quản lý nhiệm vụ hằng ngày. Người dùng chỉ cần ghi chú thô và trao đổi qua Telegram, mọi phân tích, lên lịch, nhắc nhở và báo cáo đều do hệ thống tự xử lý dựa trên LLM làm trung tâm điều khiển.

**Triết lý thiết kế:**
- LLM (Gemini/Groq) là bộ não, không xây dựng thuật toán thủ công
- Mọi output phải trả lời được: tại sao thứ tự này, tại sao khung giờ này, tại sao chắc chắn hoàn thành được trước deadline
- Miễn phí hoàn toàn
- Deploy tối giản, vận hành ổn định trên 3 thiết bị: điện thoại, laptop, PC lab
- Không icon, không emoji trong toàn bộ giao diện và tin nhắn

---

## Kiến trúc tổng thể

```
INPUT
  Google Sheet   : nhiệm vụ có cấu trúc, nhiều worksheet
  Notion         : ghi chú tự do, đa dạng, nhiều database

BRAIN
  Gemini API / Groq API
  PostgreSQL     : lịch sử hành vi, thói quen, log hoạt động

OUTPUT
  Google Tasks     : daily todolist theo từng ngày
  Google Calendar  : sự kiện, họp, sinh hoạt quan trọng
  Gmail            : báo cáo tuần/tháng kèm ảnh vision
  Telegram         : tương tác 2 chiều, nhắc nhở, xác nhận
  Web dashboard    : phân tích chuyên sâu
```

---

## Luồng dữ liệu chính (Main Pipeline)

### Pipeline hằng ngày (chạy sáng sớm, ví dụ 6:00 AM)

```
1. Thu thập dữ liệu
   - Đọc tất cả worksheet từ Google Sheet
   - Đọc tất cả notes từ Notion (các database được kết nối)
   - Truy vấn PostgreSQL lấy lịch sử hành vi 30 ngày gần nhất
   - Lấy danh sách tasks hiện tại từ Google Tasks
   - Lấy sự kiện hiện tại từ Google Calendar

2. Phân tích bằng LLM
   - Truyền toàn bộ dữ liệu vào Gemini với system prompt chứa:
     + Hồ sơ hành vi người dùng (từ Postgres)
     + Danh sách nhiệm vụ chưa hoàn thành
     + Ghi chú liên quan
     + Ngữ cảnh thời gian, mùa, lịch học/làm
   - LLM trả về: danh sách tasks được sắp xếp ưu tiên có lý giải,
     sự kiện cần tạo, cảnh báo rủi ro, câu hỏi cần xác nhận với người dùng

3. Ghi output
   - Tạo hoặc cập nhật task list trong Google Tasks
     (ví dụ: "Thu 26/2" gồm n tasks theo thứ tự ưu tiên)
   - Tạo hoặc cập nhật sự kiện trong Google Calendar
   - Lưu log vào PostgreSQL

4. Tương tác xác nhận
   - Gửi Telegram: tóm tắt lịch ngày hôm nay kèm lý giải
   - Nêu những điểm cần xác nhận (nếu có)
   - Chờ phản hồi
```

### Telegram bot xử lý real-time

```
Người dùng nhắn bất kỳ lúc nào:
  - "dời task X sang chiều"            -> agent điều chỉnh Tasks + Calendar
  - "hôm nay mệt, ưu tiên lại"        -> agent re-prioritize, giải thích lý do
  - "tại sao task A trước task B?"     -> agent trả lời với reasoning đầy đủ
  - "phương án B cho tuần này?"        -> agent đề xuất kế hoạch thay thế
  - "trạng thái tiến độ hôm nay"       -> agent tổng hợp từ Tasks + Calendar
  - cập nhật hoàn thành qua tin nhắn   -> agent cập nhật PostgreSQL

Agent chủ động nhắn khi:
  - Task quan trọng sắp đến deadline mà chưa started
  - Phát hiện conflict lịch
  - Cần xác nhận thay đổi tự động
  - Cuối ngày: review nhanh những gì chưa xong
```

### Báo cáo định kỳ (Gmail)

```
Chủ nhật hằng tuần:
  - Tổng hợp tuần: tỉ lệ hoàn thành, tasks bỏ qua, pattern hành vi
  - Đề xuất cải thiện cho tuần tới
  - Đính kèm ảnh year_vision.jpg
  - Gửi đến: nhatdm234112e@st.uel.edu.vn

Ngày 1 hằng tháng:
  - Phân tích tháng vừa qua
  - Tiến độ mục tiêu dài hạn
  - Đính kèm ảnh year_vision.jpg
  - Gửi đến: nhatdm234112e@st.uel.edu.vn
```

---

## Cấu trúc dữ liệu Google Sheet

Sheet có nhiều worksheet. Mỗi worksheet đại diện cho một ngữ cảnh (ví dụ: In_class, Self-study, Skills, Research, Orientation, Support).

Cấu trúc cột chuẩn của mỗi worksheet:

```
Cột A : Category / Domain  (ô merge theo nhóm - phải kế thừa giá trị trên khi đọc)
Cột B : Task               (tên công việc chính)
Cột C : Priority           (High / Medium / Low hoặc số)
Cột D : Start date
Cột E : Due date
Cột F : Status             (Done / Pending / Reschedule / trống)
Cột G : Notes
Cột H : Notes (tiếp)
```

Lưu ý khi đọc sheet:
- Dữ liệu bắt đầu từ hàng 2
- Cột A bị merge nhiều hàng, phải forward-fill giá trị Category
- Bỏ qua hàng trống hoặc hàng phân cách
- Mỗi hàng hợp lệ là một task độc lập: (sheet_name, category, task, metadata)

---

## Cấu trúc dữ liệu Notion

- Nhiều database kết nối đến 1 Notion integration
- Mỗi note liên quan đến: ghi chép bài giảng, ý tưởng, tư duy, brainstorm, ...
- Agent đọc tất cả pages, trích xuất context và liên kết với tasks tương ứng trong Sheet

---

## Các agent trong hệ thống

### SchedulerAgent
- Chạy hằng ngày lúc 6:00 AM
- Đọc toàn bộ input, gọi LLM phân tích, ghi output vào Tasks và Calendar
- Lưu reasoning vào Postgres

### TelegramAgent
- Lắng nghe webhook 24/7
- Phân loại intent của tin nhắn người dùng
- Gọi LLM với đầy đủ ngữ cảnh: lịch sử, hành vi, tasks hiện tại
- Thực thi thay đổi và phản hồi
- Chủ động push notification sáng, trưa, tối

### ReportAgent
- Chạy theo cron: chủ nhật 8:00 PM và ngày 1 hằng tháng 8:00 AM
- Tổng hợp dữ liệu từ Postgres
- Gọi LLM viết báo cáo
- Đính kèm ảnh year_vision
- Gửi Gmail

### SyncAgent
- Polling Google Tasks và Google Sheet mỗi 15 phút
- Phát hiện thay đổi, cập nhật Postgres
- Phát hiện conflict hoặc task bị bỏ qua, trigger TelegramAgent nhắc nhở

---

## Xác nhận hoàn thành task

Hệ thống nhận tín hiệu hoàn thành từ 3 nguồn:

1. Google Tasks: người dùng tick checkbox trực tiếp, webhook hoặc polling 15 phút để đồng bộ về Postgres
2. Google Sheet: người dùng điền "Done" vào cột F, polling hoặc Apps Script trigger để đồng bộ
3. Telegram: người dùng nhắn báo hoàn thành, agent cập nhật Tasks, Sheet và Postgres

---

## Hệ thống nói chung

- Đồng bộ hóa những sự kiện và nhiệm vụ của hệ thống đặt ra lẫn của người dùng thiết lập thủ công
- Lấy ngữ cảnh, đọc các ghi chú và nhiệm vụ sơ bộ từ Sheet cùng dữ liệu lịch sử từ Postgres, dùng tư duy của LLM phân tích, lên lịch và truyền vào các nền tảng tương ứng, trao đổi với người dùng về những điều quan trọng cần xác nhận (hệ thống tự chọn lọc), sau đó đồng bộ, cập nhật và theo dõi tiến độ công việc, đánh giá khả năng và linh hoạt thay đổi khi người dùng nhắn tin cung cấp thông tin và yêu cầu hỗ trợ như sắp xếp lại, phương án B, điều chỉnh lại thời lượng hoặc khung giờ, cuối cùng báo cáo định kỳ, tổng hợp và thực hiện các phân tích nâng cao nhằm tăng hiệu suất của người dùng
- LLM là trung tâm điều khiển toàn bộ hệ thống, không sa đà vào xây dựng thuật toán
- Hệ thống agent tự động hóa quy trình lên lịch và thiết lập thời gian biểu hằng ngày, việc của người dùng chỉ là nháp tác vụ, ghi chú và trao đổi với agent qua Telegram
- Tận dụng thông báo đẩy để tránh quên hoặc bỏ qua nhiệm vụ và sự kiện
- Không icon, không emoji
- Deploy tối giản
- Hoàn toàn miễn phí

---

## Quy ước làm việc của coding agent

- Thực hiện từng bước một và tương tác với người dùng trước khi sang bước tiếp theo
- Trước khi yêu cầu người dùng làm gì thủ công như lấy API key, điền .env, test, giải thích rõ: làm gì, tại sao, làm thế nào cụ thể
- Sử dụng tiếng Việt xuyên suốt
- Không tạo code chưa test được, luôn kèm lệnh để người dùng chạy thử
- Khi gặp nhiều lựa chọn kỹ thuật, giải thích ngắn gọn và đưa ra khuyến nghị rõ ràng thay vì để người dùng tự chọn
- Thiên về trình bày cho người low-tech, low-code: giải thích khái niệm trước khi viết code
- File này là nguồn sự thật duy nhất về trạng thái dự án, cập nhật khi có thay đổi kiến trúc hoặc quyết định kỹ thuật quan trọng
