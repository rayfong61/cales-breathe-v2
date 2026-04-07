# Cloud Run 部署筆記（Cale's Breathe）

本筆記整理本專案目前採用的部署方式：

- 前端：Vercel（`cales-breathe-v2-vite`）
- 後端：Cloud Run（`cales-breathe-api`）
- 資料庫：Supabase（PostgreSQL）
- API 入口：Vercel `/api/*` rewrite 到 Cloud Run

---

## 1. 專案與服務資訊

- GCP Project ID：`cale-458405`
- Region：`asia-east1`
- Cloud Run Service：`cales-breathe-api`
- Artifact Registry Repo：`cales-api`
- Image：`asia-east1-docker.pkg.dev/cale-458405/cales-api/cales-breathe-api:latest`
- Cloud Run URL：`https://cales-breathe-api-564346395090.asia-east1.run.app`

---

## 2. 一次性初始化（新環境）

```bash
gcloud config set project cale-458405
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create cales-api --repository-format=docker --location=asia-east1 --description="Cales API"
```

若 repo 已存在會報 `already exists`，可忽略。

---

## 3. 日常更新流程（最常用）

> 前提：Cloud Shell 的 `~/cales-breathe-v2` 已是最新程式碼（必要時先 `git pull`）。

```bash
gcloud config set project cale-458405
cd ~/cales-breathe-v2
gcloud builds submit ./cales-breathe-v2-api --tag asia-east1-docker.pkg.dev/cale-458405/cales-api/cales-breathe-api:latest
gcloud run deploy cales-breathe-api --image asia-east1-docker.pkg.dev/cale-458405/cales-api/cales-breathe-api:latest --region asia-east1
```

成功後會看到：

- `STATUS: SUCCESS`（Cloud Build）
- `Service ... revision ... has been deployed and is serving 100 percent of traffic.`（Cloud Run）

---

## 4. Cloud Run 重要環境變數

至少需設定：

- `DATABASE_URL`：Supabase 連線字串（建議 pooler）
- `JWT_SECRET`
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=none`
- `FRONTEND_PUBLIC_ORIGIN=https://<你的前端網域>`
- `API_PUBLIC_BASE_URL=https://<你的前端網域>/api`（目前採 Vercel 反代）
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `OWNER_LINE_USER_ID`
- 其他 OAuth/Google Calendar 相關變數（如有使用）

---

## 5. Vercel 設定重點（同網域登入）

`cales-breathe-v2-vite/vercel.json`：

- `source: /api/:path*`
- `destination: https://<cloud-run-url>/:path*`

前端 `VITE_API_BASE` 建議設：

- `https://<你的前端網域>/api`

這樣瀏覽器端維持同網域路徑，Cookie/登入流程較穩定。

---

## 6. LINE Webhook 設定建議

目前可用兩種：

1. 走前端反代：`https://<前端網域>/api/line/webhook`
2. 直連 Cloud Run：`https://<cloud-run-url>/line/webhook`

若追求 webhook 延遲最小，通常直連較快（少一跳）。

---

## 7. 常用排查指令

Cloud Console 查看：

1. 開啟 Cloud Run：`https://console.cloud.google.com/run?project=cale-458405`
2. 點 `cales-breathe-api`
3. 進入 `Logs` 分頁
4. 可用關鍵字篩選：`line_webhook`、`Google Calendar`、`ERROR`

---

讀取最近 log：

```bash
gcloud run services logs read cales-breathe-api --region asia-east1 --project cale-458405 --limit 100
```

模擬即時刷新（Cloud Shell）：

```bash
watch -n 3 'gcloud run services logs read cales-breathe-api --region asia-east1 --project cale-458405 --limit 40'
```

只看 webhook 相關：

```bash
gcloud run services logs read cales-breathe-api --region asia-east1 --project cale-458405 --limit 200 | grep line_webhook
```

健康檢查：

```bash
curl -sS https://cales-breathe-api-564346395090.asia-east1.run.app/health
```

查看最近 revision：

```bash
gcloud run revisions list --service cales-breathe-api --region asia-east1 --project cale-458405 --limit 5
```

---

## 8. 常見錯誤與解法

### (A) `The required property [project] is not currently set`

```bash
gcloud config set project cale-458405
```

### (B) `could not find source [./cales-breathe-v2-api]`

代表目前目錄不對，先：

```bash
cd ~/cales-breathe-v2
```

或改用絕對路徑。

### (C) `Invalid username or token`（GitHub pull/clone）

- Cloud Shell 用 HTTPS 拉私有 repo 時，Password 欄位要填 **PAT token**，不是 GitHub 帳號密碼。

### (D) `gcloud run services logs tail` 無法使用

- 某些 Cloud Shell 版本沒有對應 component，可改用：

```bash
gcloud run services logs read cales-breathe-api --region asia-east1 --project cale-458405 --limit 100
```

---

## 9. 目前已做的關鍵優化（程式層）

1. Webhook 改為「先回 200，再背景處理」，降低 LINE 重送機率。  
2. 禁止建立「過去時間」預約（後端硬限制）。  
3. `unavailable-dates` 改為以時段可用性判斷「客滿日期」。  
4. 前端今日時段會過濾掉已過去時間（例如 16:16 不可選 16:00）。

---

## 10. 上線前快速檢查清單

- [ ] Cloud Shell `git pull` 到最新
- [ ] Cloud Build `STATUS: SUCCESS`
- [ ] Cloud Run revision 已更新且 100% 流量
- [ ] `/health` 正常
- [ ] 前端可登入且 `/api` 請求正常
- [ ] LINE Webhook 測試可收可回
- [ ] 新預約不允許過去時間

