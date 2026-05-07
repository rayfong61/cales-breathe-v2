# 開發計畫：JWT Refresh、Android LINE 登入、資料庫版本控制

本文件整理 **認證強化**、**LINE OAuth 於 Android 瀏覽器的相容**、以及 **schema 演進與 Supabase 同步** 的目標、現況與建議工作順序。實作時以 repo 內實際程式為準。

**相關程式位置概覽**

| 項目 | 路徑 |
|------|------|
| JWT／Cookie／Refresh | [`cales-breathe-v2-api/app/auth_session.py`](../cales-breathe-v2-api/app/auth_session.py)；[`main.py`](../cales-breathe-v2-api/app/main.py) 掛載 `/auth/refresh`、`/auth/logout`；[`oauth.py`](../cales-breathe-v2-api/app/oauth.py) 成功後 `issue_auth_session` |
| Google／LINE OAuth | [`cales-breathe-v2-api/app/oauth.py`](../cales-breathe-v2-api/app/oauth.py)（`line_callback`、`_oauth_success_redirect`） |
| 前端登入導向 | [`cales-breathe-v2-vite/src/pages/Login.jsx`](../cales-breathe-v2-vite/src/pages/Login.jsx)、[`Booking-step3.jsx`](../cales-breathe-v2-vite/src/pages/Booking-step3.jsx) |
| DB 初始化 | [`cales-breathe-v2-api/app/database.py`](../cales-breathe-v2-api/app/database.py)（`create_all`） |
| Alembic 說明（筆記） | [`cales-breathe-v2-api/docs/Postgres筆記.md`](../cales-breathe-v2-api/docs/Postgres筆記.md) |

---

## 1. JWT：導入 Refresh Token

### 1.1 現況（已實作）

- **短效 access** JWT（`purpose: access`）於 HttpOnly **`cb_access_token`**（`ACCESS_TOKEN_TTL_MINUTES`，預設 60 分）。
- **Refresh** opaque token 於 HttpOnly **`cb_refresh_token`**；`refresh_tokens` 表仅存 **hash**、可輪替；`POST /auth/refresh`；登出撤銷並清 cookie。

### 1.2 目標

- **Access**：短效（例如 15–60 分鐘），降低外洩後可用時間。
- **Refresh**：長效（例如 7–30 天），僅用於換發新 access（建議 **輪替**：每次 refresh 作廢舊 refresh）。

### 1.3 建議實作要點

| 項目 | 說明 |
|------|------|
| 簽章／ claims | Access 與 Refresh 分開辨識（例如不同 `purpose`／`aud`）；Refresh 建議含 **`jti`**。 |
| 儲存 | DB 表（例：`refresh_tokens`）：`user_id`、`jti`、**只存 hash**、`expires_at`、`revoked_at`；登入寫入、refresh 驗證＋輪替、logout 撤銷。 |
| API | `POST /auth/refresh`（讀 refresh cookie，回應設新 access／新 refresh cookie）；`POST /auth/logout` 清 cookie 並撤銷 DB。 |
| 前端 | `axios`／`fetch` 遇 401 時呼叫 refresh 後重試一次（避免無限迴圈）。 |
| 環境變數 | 例如 `ACCESS_TOKEN_TTL_MINUTES`、`REFRESH_TOKEN_TTL_DAYS`、refresh cookie 名稱。 |
| 上線相容 | 舊使用者僅帶長效舊 cookie 時，可過渡期相容或要求重新登入一次。 |

---

## 2. Android 瀏覽器：LINE 登入（iOS 可、Android 異常）

### 2.1 可能原因（依常見度）

1. **OAuth 完成頁依賴前端 JS 機制（歷史作法）**  
   Android（含 LINE 內建瀏覽器／部分 WebView）常出現 opener 不可用、`window.close()` 受限，造成使用者卡頁或狀態不同步。現已改為後端成功回應直接 `302` 導回前端（`_oauth_success_redirect`），降低相容性風險。
2. **前端與 API 不同站**  
   跨站請求需帶 cookie 時，生產環境通常需 **`Secure` + `SameSite=None`**；若設定與實際網址不符，可能出現平台差異。見 `COOKIE_SECURE`、`COOKIE_SAMESITE` 與 CORS `allow_credentials`。
3. **LINE Developers Callback URL**  
   須與程式實際 `redirect_uri`（`API_PUBLIC_BASE_URL` + `/auth/line/callback`）**完全一致**（含 https、path、是否帶 `/api` 前綴）。

### 2.2 建議工作

| 階段 | 工作 |
|------|------|
| 重現 | Android **Chrome 一般分頁**、**In-App**、**LINE 內建瀏覽器**各試一次；記錄是否卡住 callback 頁、或回前端但 API 仍 401、或 URL 帶 `oauth_error`。 |
| 優先修正 | 將 LINE／Google **成功** callback 由 `HTMLResponse` 改為 **`RedirectResponse(302)`** 指向前端（`frontend_origin` + `redirect_path`），並在同一 response 上 **`Set-Cookie`**（與錯誤時 `_oauth_error_redirect` 對稱），**不依賴 JS**。 |
| 設定 | 正式站：`COOKIE_SECURE=true`、`COOKIE_SAMESITE=none`（全站 HTTPS）；`FRONTEND_PUBLIC_ORIGIN`、LINE console callback 與 `API_PUBLIC_BASE_URL` 一致。 |
| 次要 | 若 LINE 內建瀏覽器仍異常，登入頁可提示改以系統瀏覽器開啟。 |

---

## 3. 資料庫版本控制與 Supabase 同步

### 3.1 現況

- `init_db()` 使用 **`Base.metadata.create_all`**：僅會建立**尚不存在**的資料表，**不會**安全地變更欄位或索引。
- Repo 內**尚未**納入 Alembic 目錄；規格與筆記已預期以 migration 管理演進（見 [`SPECIFICATION.md`](../cales-breathe-v2-api/docs/SPECIFICATION.md)、`Postgres筆記.md`）。

### 3.2 目標

- 「本機改 schema」＝ **commit 可重現的 migration**；「同步 Supabase」＝ 對目標環境執行 **`alembic upgrade head`**。

### 3.3 建議流程

| 步驟 | 說明 |
|------|------|
| 初始化 Alembic | 在 `cales-breathe-v2-api` 內設定 `alembic/`，`env.py` 的 `target_metadata` 對齊 `Base.metadata`。 |
| Baseline | 若 Supabase **已有資料**：對現況做一次 **baseline**／`stamp`，避免第一次 `upgrade` 重複建立物件；之後僅新增 **incremental** revisions。 |
| 日常 | 修改 `models` → `alembic revision --autogenerate` → **人工檢查** diff → 本機測試 DB `upgrade head` → PR 帶上 `versions/*.py`。 |
| 同步遠端 | `DATABASE_URL=<Supabase 連線字串> alembic upgrade head`；DDL 建議使用 **直連／session pool**（避免僅支援交易模式的 pooler 造成遷移異常；參考 [`database.py`](../cales-breathe-v2-api/app/database.py) 內 Supabase pooler 註解）。 |
| 佈署 | 可選：部署流程中自動執行 migrate，或以 CI／手動在維護視窗執行。 |

---

## 4. 建議執行順序

1. **Android LINE**：OAuth 成功改 **302 redirect + Set-Cookie**（影響面集中、風險較低）。
2. **Alembic**：盡早導入，便於後續 refresh token 資料表等變更可追溯、可重跑。
3. **JWT Refresh**：新表／API／前端 401 重試與 cookie 策略一次到位。

---

## 5. 相關佈署筆記

- 本機與雲端總覽：[`docs/本地與雲端部署.md`](本地與雲端部署.md)
- Cloud Run／環境變數：[`docs/cloud run筆記.md`](cloud%20run筆記.md)
- Docker 本機整合：[`docs/DOCKER_DEVELOPMENT_PLAN.md`](DOCKER_DEVELOPMENT_PLAN.md)

---

## 6. 上線驗證 Checklist（5 分鐘）

### 6.1 部署前（環境變數）

- [ ] `FRONTEND_PUBLIC_ORIGIN=https://cales-breathe-v2.vercel.app`（或逗號分隔多個前端網域）
- [ ] `COOKIE_SECURE=true`
- [ ] `COOKIE_SAMESITE=none`
- [ ] `API_PUBLIC_BASE_URL` 與實際 API 外部網址一致（含 `/api` 規劃）
- [ ] LINE Developers callback URL = `{API_PUBLIC_BASE_URL}/auth/line/callback`

### 6.2 部署後（Android 實機）

- [ ] Android Chrome（一般分頁）可完成 LINE 登入並回到前端頁
- [ ] Android LINE 內建瀏覽器可完成 LINE 登入並回到前端頁
- [ ] callback 成功請求為 `302`，response 含 `Set-Cookie: cb_access_token`
- [ ] 回前端後呼叫需登入 API 時，request 有帶 cookie（非 401）
- [ ] 失敗情境會回前端並帶 `oauth_error`（非卡在 callback 空白頁）

---

## 7. Alembic 快速開始（已可執行）

> 目前可先獨立推進 Alembic，Android LINE 登入問題後續再處理。

1. 安裝依賴（API 專案根目錄）
   - `pip install -r requirements.txt`
2. 套用 baseline
   - `alembic upgrade head`
3. 日常新增 schema 變更
   - 調整 `app/models.py`
   - `alembic revision --autogenerate -m "your message"`
   - 檢查 `alembic/versions/*.py` 後再 `alembic upgrade head`
4. 若 Supabase 既有資料庫要先對齊版本（不重建）
   - `alembic stamp 20260409_000001`
