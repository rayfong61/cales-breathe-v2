# cales-breathe-v2

**正式部署**：**Vercel**（前端 SPA）＋ **Google Cloud Run**（FastAPI）＋ **Supabase**（PostgreSQL）。細節見 **[docs/本地與雲端部署.md](docs/本地與雲端部署.md)**、[docs/cloud run筆記.md](docs/cloud%20run筆記.md)。

**本機整合測試**：**Docker Compose**（Postgres + API + NGINX gateway），完整路線見 **[docs/DOCKER_DEVELOPMENT_PLAN.md](docs/DOCKER_DEVELOPMENT_PLAN.md)**。曾評估以 GCP VM 自架與 compose 類似架構，已不採用。

目錄：

- `cales-breathe-v2-api` — FastAPI
- `cales-breathe-v2-vite` — Vite + React
- `deploy/` — 對外 NGINX（靜態 + `/api/` 反代）
- `docker-compose.yml` — Postgres + API + gateway

## 前置

- 安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（或 Docker Engine）並**啟動**。
- 在 `cales-breathe-v2-api/` 準備好 `.env`（可由 `.env.example` 複製）。**勿將 `.env` 提交版本控制。**

## 根目錄環境變數（可選）

複製根目錄 `.env.example` 為 `.env`，可依需求修改 `POSTGRES_*`、`VITE_API_BASE`、`GATEWAY_HTTP_PORT`。

Compose 會用 `POSTGRES_*` 組出 `DATABASE_URL` 覆寫後端連線（**不使用** api 內的 SQLite）。

## 經由 Docker 測試（瀏覽器打 gateway）

1. 後端 `.env` 請與 **同網域** 一致（例：gateway 走 `http://localhost`）：

   - `FRONTEND_PUBLIC_ORIGIN=http://localhost`
   - `API_PUBLIC_BASE_URL=http://localhost/api`
   - 本機 HTTP：`COOKIE_SECURE=false`、`COOKIE_SAMESITE=lax`

2. 建置並啟動：

   ```bash
   cd cales-breathe-v2
   docker compose up --build -d
   ```

3. 瀏覽器開：`http://localhost`（若 `GATEWAY_HTTP_PORT=8080` 則為 `http://localhost:8080`）。

4. API 健康檢查：`http://localhost/api/health`

根目錄 `.env` 的 `VITE_API_BASE` 須與實際網址一致（含埠），修改後需 **`docker compose build gateway --no-cache`** 再 `up`。

## Google / LINE 登入（本機）

在 Google Cloud Console、LINE Developers 登記的 **Redirect / Callback URL** 須與 `API_PUBLIC_BASE_URL` 一致，例如：

- `http://localhost/api/auth/google/callback`
- `http://localhost/api/auth/line/callback`

若使用 `127.0.0.1` 或加埠，請與後端 `.env` 完全一致，勿混用 `localhost` 與 `127.0.0.1`。

## CI/CD 現況

- API CI：`.github/workflows/api-ci.yml` 會在 PR 或 push（`main`/`master`）時跑 `pytest`。
- Path 篩選：僅當變更包含 `cales-breathe-v2-api/**` 或 `.github/workflows/api-ci.yml` 才觸發；只改前端時不觸發屬預期。
- API CD：`.github/workflows/api-cd.yml` 已串接 GitHub Actions + OIDC/WIF，流程為 build image -> push Artifact Registry -> deploy Cloud Run。

## Production API 文件存取

- 在 `ENVIRONMENT=production`（或 `APP_ENV=production`）時，若未設定 `DOCS_BASIC_USER`/`DOCS_BASIC_PASSWORD`，`/docs`、`/redoc`、`/openapi.json` 預設關閉。
- 若設定上述帳密，則改為 HTTP Basic 保護。
- 可用 `DISABLE_API_DOCS=1` 強制關閉 API 文件端點。

## 登入限流（Rate Limit）

- `POST /login` 已啟用 Redis Token Bucket 限流（key：IP + contact_mail）。
- 超限回應 `429`，並帶 `Retry-After`。

## LINE Messaging Webhook

LINE 伺服器需 **HTTPS 公網網址**；本機請用 **ngrok** 等隧道，Webhook 設為：

`https://<隧道網域>/api/line/webhook`

## 開發時不跑 Docker

可照常於前端 `npm run dev`（埠 3000）、後端 `uvicorn`（埠 8000），此時 `VITE_API_BASE` 與 OAuth 網址請改回對應本機埠（見各專案 `.env.example`）。
