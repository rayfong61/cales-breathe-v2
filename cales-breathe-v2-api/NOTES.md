## 專案構想總結：LINE 熱蠟工作室預約系統

- **開發規格書**：階段拆解、驗收條件、API 現況與進度表見 [docs/SPECIFICATION.md](./docs/SPECIFICATION.md)（依此檔按表開發即可）。
- **目標**：將原本以網站為主的預約系統，演進成「網站以展示為主、預約改由 LINE Bot 完成」，並同時練習 FastAPI、Git/GitHub、PostgreSQL、SQLAlchemy、pytest、Docker、CI/CD、JWT/OAuth 等技術，作為可展示的面試專案。
- **現況**：
  - 已有舊專案（Node + Express + React + PostgreSQL）網站版：[CALES-BREATHE 熱蠟美肌預約系統](https://github.com/rayfong61/CALES-BREATHE)。
  - 客人不習慣透過網站預約，希望改成以 LINE 為主要預約入口。
  - 舊網站未來傾向保留為「品牌展示頁」，主要引導客人加入 LINE。

---

## 新系統角色與整體架構

- **角色**
  - **客人 (Customer)**：透過 LINE 官方帳號與機器人互動進行預約與查詢。
  - **業主 / 店家 (Owner)**：太太，可用 LINE 幫客戶手動預約與查看排程。
  - **系統後端 (Backend)**：以 FastAPI + PostgreSQL + SQLAlchemy 建構的 API。
  - **外部服務**：
    - LINE Messaging API / LIFF：負責聊天互動與前端 UI。
    - Google Calendar API：同步所有預約到 Google 行事曆。

- **主要組成**
  - **LINE Bot / LIFF 前端**
    - 接收客人文字或按鈕操作，引導完成預約流程。
    - 可提供 LIFF 小網頁作為「簡易後台」給業主使用。
  - **FastAPI 後端**
    - 路由範例：`/line/webhook`, `/bookings`, `/services`, `/users`, `/admin/...`。
    - 處理預約流程、時間衝突檢查、身分驗證、權限控管。
    - 與 PostgreSQL、Google Calendar、LINE API 溝通。
  - **PostgreSQL + SQLAlchemy**
    - 核心資料表構想：
      - `users`：包含客人與業主（可用 `role` 區分），可加上 `line_user_id`。
      - `services`：服務項目（部位、價格、所需時間等）。
      - `bookings`：預約紀錄（時間、項目、客戶、建立者、狀態等）。
  - **Google Calendar**
    - 每筆預約對應一個 Calendar Event。
    - 建立 / 更新 / 取消預約時，同步操作 Calendar 事件。

---

## 功能需求整理

1. **客人透過 LINE 預約**
   - 加入 LINE 官方帳號後，傳訊息（例如「預約」）觸發流程。
   - 後端透過 `/line/webhook` 收到訊息，辨識 `line_user_id`，必要時自動建立 `user`。
   - 引導客人依序選擇：日期 → 時間 → 項目。
   - 最後由前端（LINE / LIFF）呼叫後端 `/bookings` API 建立預約。
   - 後端需檢查時間是否可預約、寫入 DB、同步 Google Calendar，並回傳成功訊息給客人。

2. **LINE 自動提醒功能**
   - 在 `bookings` 中記錄預約時間與狀態。
   - 規劃排程任務（例如每天固定時間）：
     - 掃描「隔天要到店的預約」。
     - 透過 LINE Messaging API 對客人發送提醒訊息。
   - 日後可引入 APScheduler / Celery 等排程工具實作。

3. **Google 行事曆整合**
   - 新增預約：呼叫 Google Calendar API 建立事件，儲存 `event_id` 至 `bookings`。
   - 修改預約：依 `event_id` 更新行事曆事件。
   - 取消預約：刪除對應 `event_id` 事件。
   - 使用 Service Account 或 OAuth，將 Service Account 加入店家行事曆以授權操作。

4. **業主使用 LINE 幫客人手動預約**
   - 在 `users` 表中以 `role` 區分業主與一般客人。
   - 若由業主觸發預約流程，機器人需先取得客戶資訊（姓名、電話、LINE ID 等）。
   - 最終同樣呼叫 `/bookings` API 建立預約，只是 `created_by` 或 `role` 表示為業主建立。

5. **業主使用 LINE 作為「簡易後台」**
   - 文字指令版：
     - 例如輸入「查 2026-03-20」顯示當日預約清單。
     - 例如輸入「查 客人姓名」顯示該客人相關預約。
   - LIFF 小後台版（進階）：
     - LINE 內有一個「後台」按鈕，開啟 LIFF 網頁。
     - LIFF 透過 LINE Login 取得身分後，呼叫後端 `/admin/bookings` 等 API。
     - 顯示排程表、支援基本查詢或操作。

---

## 舊專案與新專案的關係

- **舊專案**：[CALES-BREATHE](https://github.com/rayfong61/CALES-BREATHE)
  - 技術：React + Vite, Node + Express, PostgreSQL。
  - 功能：網站首頁、服務介紹、線上預約、會員註冊登入（含 LINE/Google OAuth）、預約紀錄查詢等。
- **新專案的定位**
  - 延續舊專案的商業邏輯與資料模型（使用者、預約、服務項目等）。
  - 重新以 FastAPI + LINE Bot + Google Calendar 實作「預約」核心功能。
  - 舊網站調整為「品牌展示及導流到 LINE」：
    - 保留形象、服務介紹、顧客回饋等內容。
    - 原本的「線上預約」按鈕改為引導加入 LINE 官方帳號。

---

## 學習與實作路線（摘要）

1. **專案與版本控制**
   - 在目前工作資料夾建立新的 FastAPI 專案（或子資料夾）。
   - 初始化 Git，推到 GitHub（與舊專案並存，或作為 v2 版本）。

2. **FastAPI + PostgreSQL + SQLAlchemy 基礎**
   - 建立最小 API：`/health`、`/bookings`（先使用假資料，再接上 DB）。
   - Docker 建立 PostgreSQL（或使用本機安裝的 Postgres）。
   - 設計 `users`、`services`、`bookings` 三張主要資料表並實作 CRUD。

3. **JWT / OAuth2 身分驗證與權限**
   - 實作登入 / 取得當前使用者資訊的 API。
   - 區分客人與業主角色，針對 `/admin/...` 路由做權限限制。

4. **LINE Bot 整合**
   - 申請 LINE Messaging API channel。
   - 設定 Webhook 到 FastAPI 的 `/line/webhook`。
   - 預約流程：文字觸發 → 對話引導 → 呼叫後端 API 完成預約。

5. **Google Calendar 整合與自動提醒**
   - 與 Calendar API 串接：建立/修改/刪除預約事件。
   - 規劃排程任務，實作預約前提醒訊息（LINE push）。

6. **測試與 CI/CD（未來可逐步加入）**
   - 使用 pytest 為預約邏輯與 API 編寫測試。
   - 設置 GitHub Actions，自動跑測試與（選擇性）自動部署。

---

## 最小 MVP（SQLite 版本）- 已完成

- **技術**：FastAPI + SQLAlchemy + SQLite（單一檔案，零額外安裝）
- **資料表**：`users`、`services`、`bookings`、`booking_services`（多對多關聯）
- **API 端點**：
  - `GET /health`：健康檢查
  - `GET /services`：列出所有服務（依選單分類順序，24 筆）
  - `GET /services/by-category`：依分類分組（給 LINE Bot 選單用）
  - `POST /users`：建立使用者
  - `POST /bookings`：建立預約（`service_ids: [1, 5, 21]` 支援多服務，含 X選1 驗證與時段衝突檢查）
  - `GET /bookings?date=YYYY-MM-DD`：查詢預約（可選日期）
  - `GET /bookings/{id}`：取得單一預約（含 services、total_duration_minutes、total_price）

- **重要**：若已有舊版 `app.db`，Schema 變更後需刪除該檔再啟動，才會建立新表結構。

- **啟動方式**：
  ```bash
  pip install -r requirements.txt
  uvicorn app.main:app --reload
  ```
  開啟 http://127.0.0.1:8000/docs 可測試 Swagger UI。

- **後續升級**：要切換到 PostgreSQL 時，只需修改 `app/database.py` 的 `DATABASE_URL` 即可。

---

## 明天可以從哪裡繼續？

- **選項 A：補上 pytest 測試**  
  為 `POST /bookings`、時段衝突邏輯、`GET /bookings` 寫單元測試。
- **選項 B：接 LINE Webhook**  
  申請 LINE 官方帳號，設定 Webhook 到 FastAPI，先做「收到訊息回覆」的最小版。
- **選項 C：切換到 PostgreSQL + Docker**  
  用 Docker Compose 跑 PostgreSQL，調整連線字串，為之後部署做準備。

> 下次回來時，可以先看這份 `NOTES.md`，選一個想先做的選項，我可以再一步步帶你實作。

