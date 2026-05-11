# CALES BREATHE

現代化美容／熱蠟除毛預約平台，支援線上預約、會員與 OAuth 登入、**Google Calendar** 同步、**LINE Messaging** 通知與 Webhook，以及業主端預約／顧客管理相關 API。本專案為 **monorepo**：前後端分離，並以 **GitHub Actions CI/CD**、**Docker** 與 **Google Cloud Run／Vercel** 完成可重現的開發與部署流程。

---

## Tech Stack

### Frontend

| 項目 | 技術 |
|------|------|
| Framework | React + Vite |
| Styling | Tailwind CSS |
| Routing | React Router |
| State | Context API、React Hooks |
| HTTP Client | Axios |
| Deployment | Vercel |

### Backend

| 項目 | 技術 |
|------|------|
| Framework | FastAPI |
| Language | Python 3 |
| ORM | SQLAlchemy |
| Migration | Alembic |
| Validation | Pydantic |
| ASGI Server | Uvicorn |
| Authentication | JWT（**HttpOnly Cookie**：access／refresh；refresh 於 DB 記錄以利撤銷與輪替） |
| OAuth Login | Google OAuth、LINE Login |
| Webhook | LINE Messaging API（驗簽、事件處理／冪等紀錄） |
| Calendar | Google Calendar API（與預約生命週期同步） |
| Rate Limit | 登入等路徑可使用 **Redis**（Token Bucket，`429` + `Retry-After`） |

### Database

- **PostgreSQL**（正式環境如 Supabase；本機 Docker Compose 對齊 Postgres）
- 本機僅跑 API、不經 Compose 時可改 **SQLite**（透過 `DATABASE_URL`）

### DevOps / Cloud

| 項目 | 技術 |
|------|------|
| Backend Hosting | Google Cloud Run |
| Frontend Hosting | Vercel |
| CI/CD | GitHub Actions（`api-ci.yml`：pytest；`api-cd.yml`：建映像、OIDC／WIF 部署 Cloud Run） |
| Containerization | Docker、Docker Compose（本機 Postgres + API + NGINX gateway） |

---

## System Architecture

對外慣例：**瀏覽器／LINE** → 前端（Vercel，透過同網域 **`/api`** 轉發）→ **FastAPI**（Cloud Run）→ **PostgreSQL**；並串 **Google Calendar**、**LINE Platform**；登入限流可經 **Redis**。

```
Frontend (React / Vite @ Vercel)
        │
        ▼  （/api 反代，與後端同源較利於 Cookie／OAuth callback）
 FastAPI Backend API (Cloud Run)
        │
 ┌──────┼──────────────────┬─────────────┐
 ▼      ▼                  ▼             ▼
PostgreSQL        Google Calendar API   LINE Messaging
        │                                     ▲
        ▼                                     │
 JWT / OAuth／Session（Cookie）      Webhook / Push
        │
        ▼
Redis（選用，例如登入限流）
```

---

## Features

### User Features

- 線上預約（服務組合、時段與不可預約時段查詢）
- Google／LINE 第三方登入（與帳密登入並存）
- 以 **JWT + HttpOnly Cookie** 為主的受保護資源存取
- 預約建立／查詢／取消；商業規則含**時段重疊拒絕**（`409`）、**取消時間窗**（逾時回 `400`）等
- 響應式前端介面（Tailwind）

### Admin / Owner Features

- 業主視角訂單／預約列表與代客建立預約（**owner** 與 **customer** 角色分流）
- 顧客搜尋相關端點
- Google Calendar 與預約狀態對齊（`bookings.google_calendar_event_id`）
- LINE Webhook 接收與通知／回覆（依環境變數啟用）

### Engineering Features

- REST 風格 API（路由集中於 `app/main.py`，OAuth 於 `app/oauth.py`）
- Alembic schema 遷移
- SQLAlchemy ORM；敏感設定經環境變數注入（**`.env` 勿提交**）
- Docker 映像與 Compose 本機整合（`docker-compose.yml`、`deploy/` NGINX）
- GitHub Actions：**pytest** 與 **映像建置／部署 Cloud Run**

---

## Frontend Structure

實際路徑：`cales-breathe-v2-vite/`（對照常見 `frontend/` 命名）

```
cales-breathe-v2-vite/
├── src/
│   ├── api/
│   ├── components/
│   ├── pages/
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── public/
├── index.html
└── vite.config.js
```

---

## Backend Structure

實際路徑：`cales-breathe-v2-api/`（對照常見 `backend/` 命名）

```
cales-breathe-v2-api/
├── app/
│   ├── main.py           # 主要 HTTP 路由
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── oauth.py          # Google / LINE OAuth
│   ├── auth_session.py   # JWT、Cookie、refresh 輪替
│   ├── google_calendar.py
│   ├── rate_limiter.py
│   └── …
├── alembic/
├── Dockerfile
└── requirements.txt
```

---

## Authentication Flow

### JWT 與 Cookie（主線）

1. 使用者透過 **Google／LINE OAuth** 或 **帳密 `/login`** 完成驗證。  
2. 後端簽發 **JWT**（access），並以 **HttpOnly Cookie** 下發；**refresh** 亦可經 Cookie，於伺服器端紀錄 hash 以支援撤銷與輪替。  
3. 前端以 **`credentials: 'include'`** 呼叫受保護 API（非典型「Bearer 存 localStorage」模式）。  
4. **`/auth/refresh`**、**`/auth/logout`** 維護會話。

### OAuth Login

- Google OAuth 2.0  
- LINE Login  
- **`API_PUBLIC_BASE_URL`** 須與 OAuth Console 登記之 callback **字串完全一致**（含 `localhost`／埠、`/api` 前綴與否）

---

## Google Calendar Integration

預約建立／確認／取消流程中呼叫 **Google Calendar API**，將事件 id 寫回 **`bookings.google_calendar_event_id`**，與 DB 對齊；外部 API 失敗時的阻擋或僅紀錄策略以程式碼行為為準。

---

## LINE Webhook Integration

- 經 gateway 時公開路徑為 **`/api/line/webhook`**；LINE 要求 **HTTPS**，本機除錯常用隧道  
- **頻道簽章**驗證  
- **`line_webhook_events`** 表做事件去重，降低 LINE 重送造成重複副作用  
- 推播／回覆與 **`LINE_CHANNEL_SECRET`**、**`LINE_CHANNEL_ACCESS_TOKEN`**、**`OWNER_LINE_USER_ID`** 等相關  

---

## Database Design

| 表名 | 說明 |
|------|------|
| `users` | 使用者、OAuth 欄位、`owner`／`customer` |
| `bookings` | 預約主檔（時段、價格、狀態、`google_calendar_event_id`） |
| `services` | 服務項目 |
| `booking_services` | 預約與服務多對多 |
| `refresh_tokens` | Refresh token hash（撤銷／輪替） |
| `line_webhook_events` | LINE 事件冪等／去重 |

不可預約時段多由 API **計算／查詢**，不必獨立 `availability` 表。

---

## CI/CD Pipeline

```
Push／PR to GitHub（後端路徑變更觸發 CI）
       │
       ▼
GitHub Actions（api-ci.yml）
       │
       ├──────────────────┐
       ▼                  ▼
   Run pytest        （合併後 api-cd.yml）
                            │
                            ▼
                    Build Docker Image
                            │
                            ▼
                   Deploy to Cloud Run
```

---

## Environment Variables

後端於 **`cales-breathe-v2-api/.env`** 設定（**勿提交含真值之 `.env`** 至版本庫）。

**常見鍵名**

```
DATABASE_URL=
JWT_SECRET=
FRONTEND_PUBLIC_ORIGIN=
API_PUBLIC_BASE_URL=
COOKIE_SECURE=
COOKIE_SAMESITE=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_LOGIN_CHANNEL_ID=
LINE_LOGIN_CHANNEL_SECRET=
GOOGLE_SERVICE_ACCOUNT_JSON=
GOOGLE_CALENDAR_ID=
REDIS_URL=
```

**本機 HTTP**：`COOKIE_SECURE=false`、`COOKIE_SAMESITE=lax`。**HTTPS 正式站**：通常 `COOKIE_SECURE=true`，並依跨網域需求調整 `SameSite`。

**Docker Compose**：根目錄 compose 會以 **`POSTGRES_*`** 組出 **`DATABASE_URL`** 覆寫後端，使本機與正式環境同為 Postgres。

**Production API 文件**：`ENVIRONMENT=production` 時，未設 **`DOCS_BASIC_USER`／`DOCS_BASIC_PASSWORD`** 則 **`/docs`**、**`/openapi.json`** 預設關閉；可設帳密啟用 HTTP Basic，或以 **`DISABLE_API_DOCS=1`** 強制關閉。

---

## Deployment

| 層級 | 平台 | 說明 |
|------|------|------|
| Frontend | Vercel | SPA；`/api` 轉發至後端 |
| Backend | Google Cloud Run | Docker 映像；連線 Supabase 等 PostgreSQL |

---

## API Example

經 **NGINX／Vercel gateway** 時對外為 **`/api/...`**；本機 **直連 Uvicorn** 則多為根路徑（無 `/api`），依 **`API_PUBLIC_BASE_URL`** 與前端 **`VITE_API_BASE`** 一致為準。

**建立預約**

```http
POST /api/bookings
Content-Type: application/json
```

（瀏覽器呼叫時由 **HttpOnly Cookie** 附帶登入狀態。）

```json
{
  "user_id": 1,
  "service_ids": [1, 2],
  "booking_date": "2026-05-10T14:00:00",
  "notes": "敏感肌，請留意"
}
```

**成功回應（節錄，`BookingRead`）**

```json
{
  "id": 42,
  "user_id": 1,
  "booking_date": "2026-05-10T14:00:00",
  "total_duration_minutes": 75,
  "total_price": 3200,
  "status": "pending",
  "google_calendar_event_id": null,
  "services": []
}
```

本機啟動 API 後可開 **`/docs`** 檢視完整 schema（正式環境可依上節設定關閉）。

---

## Security

- **HttpOnly Cookie** 降低 XSS 竊取會話  
- Google／LINE **OAuth 2.0**  
- 帳密密碼 **`passlib`** 雜湊  
- 敏感設定僅經環境變數注入  
- **HTTPS** 正式站；**CORS** 依 `FRONTEND_PUBLIC_ORIGIN` 收斂  
- **Pydantic** 輸入驗證  
- **登入 Rate limit**（Redis）  

---

## Performance & Scalability

- FastAPI 非同步與 ASGI 部署  
- Cloud Run **自動擴充**；後端盡量 **無狀態**（會話仰賴 Cookie + DB refresh 紀錄）  
- PostgreSQL；前端靜態由 **Vercel CDN** 派送  

---

## Future Improvements

- 更廣泛 **Redis** 快取與 session 策略  
- **Queue**（Celery／Cloud Tasks）做重試與非同步通知  
- Email／簡訊  
- 管理後台報表  
- AI 輔助排程  
- 金流（Stripe、TapPay 等）  

---

## Local Development

### Frontend

```bash
cd cales-breathe-v2-vite
npm install
npm run dev
```

### Backend

```bash
cd cales-breathe-v2-api
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker（本機 Postgres + API + gateway）

於 **monorepo 根目錄**：

1. 在 **`cales-breathe-v2-api/`** 準備 **`.env`**（鍵名見上節；與 gateway 同網域時常設 **`FRONTEND_PUBLIC_ORIGIN=http://localhost`**、**`API_PUBLIC_BASE_URL=http://localhost/api`**）。  
2. 可選：根目錄 **`.env`** 調整 **`POSTGRES_*`**、**`GATEWAY_HTTP_PORT`**。  
3. 執行：

```bash
docker compose up --build -d
```

**健康檢查**：`http://localhost/api/health`（若改埠則替換主機埠）。  
**OAuth callback** 須與 **`API_PUBLIC_BASE_URL`** 一致，例如 `http://localhost/api/auth/google/callback`。  
**LINE Webhook** 須 **HTTPS** 公網；本機除錯需隧道，路徑形如 **`https://<隧道>/api/line/webhook`**。

```bash
cd cales-breathe-v2-api
alembic upgrade head
```

---

## Monorepo 目錄

| 路徑 | 說明 |
|------|------|
| `cales-breathe-v2-api/` | FastAPI、Alembic、測試 |
| `cales-breathe-v2-vite/` | React 前端 |
| `deploy/` | 本機 NGINX（靜態 + `/api/` 反代） |
| `docker-compose.yml` | Postgres + API + gateway |

---

## Project Goals

**CALES BREATHE** 以可上線的預約網域為核心：把**衝突檢查**、**取消政策**、**身分與限流**做成可測試的 API，並整合 **LINE**、**Google Calendar** 與 **CI/CD**，展示從本機、測試到雲端交付的完整工程流程。
