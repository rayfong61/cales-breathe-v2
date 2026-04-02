# cales-breathe-v2 Docker 開發計畫

本文件描述 monorepo 內以 **Docker Compose** 進行本機整合測試、以及後續銜接 **GCP VM** 的開發路線；實作細節以根目錄 [`README.md`](../README.md)、[`docker-compose.yml`](../docker-compose.yml) 為準。

---

## 1. 目標

| 階段 | 目標 |
|------|------|
| **A. 本機 Docker** | 單一指令啟動 Postgres、FastAPI、NGINX（靜態 + `/api/` 反代），瀏覽器可驗證主要流程。 |
| **B. 本機 OAuth／Bot** | Google／LINE Login 以登記之 callback 測通；LINE Messaging Webhook 以 **HTTPS 隧道**（如 ngrok）測通。 |
| **C. 正式佈署** | 同一套 compose 概念遷至 GCP VM（或抽換為 production 設定）：網域、HTTPS、備份。 |

---

## 2. 架構概要

```mermaid
flowchart LR
  browser[Browser]
  gateway[gateway_NGINX]
  api[api_FastAPI]
  pg[(postgres)]
  vol[Volume_uploads]
  browser --> gateway
  gateway -->|"/api/"| api
  api --> pg
  api --> vol
```

gateway 同時於 `/` 提供 Vite 靜態檔（圖中略繪）。

- **gateway**：建置自 [`deploy/Dockerfile`](../deploy/Dockerfile)，內含 Vite `dist` 與 [`deploy/nginx.conf`](../deploy/nginx.conf)。
- **api**：[`cales-breathe-v2-api/Dockerfile`](../cales-breathe-v2-api/Dockerfile)；`DATABASE_URL` 由 Compose 覆寫為連 **postgres** 服務。
- **postgres**：資料持久化於 named volume `postgres_data`；上傳檔於 `api_uploads`。

---

## 3. 前置條件

- 已安裝並啟動 **Docker Desktop**（或相容的 Docker Engine + Compose plugin）。
- `cales-breathe-v2-api/.env` 已自 `.env.example` 建立，且**未**提交版本庫。
- （選用）根目錄 `.env`：自 [`.env.example`](../.env.example) 複製，用於 `POSTGRES_*`、`VITE_API_BASE`、`GATEWAY_HTTP_PORT`。

---

## 4. 本機 Docker 工作流程

### 4.1 首次或變更依賴後

```bash
cd cales-breathe-v2
docker compose up --build -d
```

### 4.2 僅變更後端程式

```bash
docker compose up -d --build api
```

### 4.3 變更前端或 `VITE_*` 建置參數

修改根目錄 `.env` 內 `VITE_API_BASE` / `VITE_LINE_ADD_FRIEND_URL` 後：

```bash
docker compose build gateway --no-cache
docker compose up -d gateway
```

### 4.4 經由 gateway 瀏覽時的環境變數（`cales-breathe-v2-api/.env`）

與「同網域」一致，例如 gateway 為 `http://localhost`：

- `FRONTEND_PUBLIC_ORIGIN=http://localhost`
- `API_PUBLIC_BASE_URL=http://localhost/api`
- 本機 HTTP：`COOKIE_SECURE=false`、`COOKIE_SAMESITE=lax`

若 `GATEWAY_HTTP_PORT=8080`，上述改為 `http://localhost:8080` 與 `http://localhost:8080/api`，並同步 `VITE_API_BASE`。

### 4.5 常用維運指令

| 指令 | 用途 |
|------|------|
| `docker compose ps` | 服務狀態 |
| `docker compose logs -f api` | 後端日誌 |
| `docker compose logs -f gateway` | 閘道日誌 |
| `docker stats` | 容器資源（小機器除錯時） |

---

## 5. 與「非 Docker」本機開發並存

- **前端**：`cales-breathe-v2-vite` 內 `npm run dev`（預設埠 3000）。
- **後端**：`uvicorn app.main:app --reload`（預設埠 8000）。

此時 `VITE_API_BASE`、`FRONTEND_PUBLIC_ORIGIN`、`API_PUBLIC_BASE_URL` 應指向對應埠，與 Docker gateway 模式**分開設定**；切換模式時請核对 OAuth 後台登記之 URL。

---

## 6. Google／LINE 與 LINE Bot

### 6.1 Login（本機 browser）

Redirect／Callback 須與 `API_PUBLIC_BASE_URL` 完全一致，例如：

- `{API_PUBLIC_BASE_URL}/auth/google/callback`
- `{API_PUBLIC_BASE_URL}/auth/line/callback`

避免混用 `localhost` 與 `127.0.0.1`、或漏／多斜線。

### 6.2 Messaging API Webhook

LINE 需 **HTTPS 公網**；本機請使用 **ngrok**、**Cloudflare Tunnel** 等，Webhook 路徑為：

`/api/line/webhook`（對外完整 URL 為 `https://<隧道>/api/line/webhook`）。

---

## 7. Git 分支建議

- 主線：`main`（可隨時本機／Docker 驗證通過之狀態）。
- Docker 相關開發：`feature/docker-local` 或 `chore/docker-compose`（依團隊習慣擇一）。

大規模搬目錄或僅調整 compose 時，建議**獨立 commit**，便於回溯。

---

## 8. 後續：GCP VM（概要）

- VM 安裝 Docker 與 Compose；上傳 monorepo 或部署產物。
- 防火牆開放 80／443；網域 DNS 指向 VM；憑證（如 Let’s Encrypt）。
- 正式環境：`COOKIE_SECURE=true`、正確之 `FRONTEND_PUBLIC_ORIGIN` / `API_PUBLIC_BASE_URL`。
- **e2-micro（1 GB）**：可當實驗；同機跑 Postgres 建議預留 **swap** 或升級機型；資源限制與 Postgres `max_connections` 須與後端連線池一併檢視。

詳細步驟可另見 `cales-breathe-v2-api/docs` 內既有佈署筆記（若與本計畫衝突，**以本 monorepo 根目錄 compose 為準**）。

---

## 9. 檢查清單（上線前）

- [ ] 根目錄與 `api` 之 `.env` 未提交版本庫。
- [ ] `docker compose up` 後 `/api/health` 可連線。
- [ ] 上傳／圖片（若 `STORAGE_BACKEND=local`）寫入 volume，重建容器後仍存在。
- [ ] OAuth／LINE／Webhook 後台 URL 與執行環境一致。
- [ ] 正式環境已規劃 Postgres 與 `uploads` 備份策略。

---

## 10. 相關檔案索引

| 路徑 | 說明 |
|------|------|
| [`../docker-compose.yml`](../docker-compose.yml) | 服務定義 |
| [`../deploy/nginx.conf`](../deploy/nginx.conf) | 閘道路由 |
| [`../.env.example`](../.env.example) | Compose／建置變數範例 |
| [`cales-breathe-v2-api/.env.example`](../cales-breathe-v2-api/.env.example) | 後端完整變數範例 |

---

*文件版本：依目前 repo 結構撰寫；若目錄或服務名稱變更，請同步更新本頁與 README。*
