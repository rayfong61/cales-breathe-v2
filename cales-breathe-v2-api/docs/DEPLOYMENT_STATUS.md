# 部署進度紀錄

> 最後更新：2026-03-31

**說明**：下表曾以 Render 為後端託管撰寫；目前程式庫之 Vercel API 轉發目標為 **Google Cloud Run**（見根目錄 `docs/本地與雲端部署.md`、`cales-breathe-v2-vite/vercel.json`）。若已全面改為 Cloud Run，以下「後端網址」列僅供對照歷史紀錄。

---

## 系統架構

| 元件 | 平台 | 網址 |
|------|------|------|
| 前端 | Vercel | https://cales-breathe-v2-vite.vercel.app |
| 後端 API | Render（Free） | https://cales-breathe-v2-api.onrender.com |
| 資料庫 | Supabase PostgreSQL（Free） | aws-1-ap-southeast-1.pooler.supabase.com |
| 圖片/影片 | Cloudflare R2 | https://pub-cdd09c31cc514fd89032dc45ed4a34ee.r2.dev |

---

## 已完成項目 ✅

### 基礎架構
- [x] FastAPI 後端部署到 Render
- [x] React + Vite 前端部署到 Vercel
- [x] Supabase PostgreSQL 連線（`database.py` 支援環境變數切換 SQLite / PostgreSQL）
- [x] `load_dotenv()` 移至所有 import 前，確保 PostgreSQL 連線正確載入
- [x] Cloudflare R2 圖片儲存
- [x] 兩個 repo 推上 GitHub，push 觸發自動部署

### 功能驗證
- [x] 帳號密碼 註冊 / 登入
- [x] Google OAuth 登入
- [x] LINE OAuth 登入
- [x] 完整預約流程（選服務 → 選時段 → 送出）
- [x] 業主 LINE Bot 指令（確認 / 取消 / 完成預約）
- [x] 頭像更新上傳至 R2
- [x] 預約完成後 LINE 加好友按鈕（條件：有設定 `VITE_LINE_ADD_FRIEND_URL` 且非 LINE 帳號登入）

### 跨域問題解決
- [x] Vercel `vercel.json` 新增 `/api/*` rewrite proxy，解決手機 Safari 跨域 cookie 問題
- [x] `API_PUBLIC_BASE_URL` 改為 `https://cales-breathe-v2-vite.vercel.app/api`
- [x] Google / LINE OAuth callback 改為透過 Vercel proxy：
  - `https://cales-breathe-v2-vite.vercel.app/api/auth/google/callback`
  - `https://cales-breathe-v2-vite.vercel.app/api/auth/line/callback`
- [x] CORS 新增 Vercel 正式網址，並支援 `FRONTEND_PUBLIC_ORIGIN` 環境變數動態設定

---

## 待完成項目

### 緊急 / 功能性

| 項目 | 說明 | 狀態 |
|------|------|------|
| `VITE_LINE_ADD_FRIEND_URL` | 設定 Vercel 環境變數，讓預約完成後出現 LINE 加好友按鈕 | ⏳ 待設定 |
| Supabase 直連 URL | 將 `DATABASE_URL` 從 Pooler 改為直連（`db.xxxx.supabase.co`），避免 Render 連線 timeout | ⏳ 待設定 |
| LINE Webhook URL | Render 部署後已更新為 `https://cales-breathe-v2-api.onrender.com/line/webhook` | ✅ 已設定 |

### 效能優化

| 項目 | 說明 |
|------|------|
| 字型檔瘦身 | `ChenYuluoyan-Thin-Monospaced.ttf` 約 4.5MB，建議上傳至 R2 或改用 Google Fonts |
| JS Bundle 拆分 | 目前約 542KB，可用 dynamic import() 拆分，加速首頁載入 |
| favicon.ico | 後端持續出現 404，可加入檔案或在 FastAPI 忽略此路徑 |

### 安全性

| 項目 | 說明 |
|------|------|
| Render 環境變數 | 確認所有敏感金鑰（R2、LINE、Google、JWT）已設為 Secret，勿明文存於 `render.yaml` |
| `.env` 不 commit | 後端 `.gitignore` 已排除 `.env`，請勿手動加回 |

---

## 正式營運前準備

| 項目 | 說明 |
|------|------|
| Supabase 防暫停 | 免費方案閒置 7 天會暫停，需定期喚醒或升級 Pro（$25/月）|
| Render 防休眠 | 免費方案閒置 15 分鐘休眠，首次請求需等 30～60 秒喚醒，建議升級 Starter（$7/月）|
| 自訂網域 | 購買網域，分別綁定到 Vercel（前端）與 Render（後端）|
| OAuth callback 更新 | 自訂網域後需同步更新 Google Cloud Console 與 LINE Developers 的 callback URL |

---

## 未來功能規劃

| 功能 | 說明 | 優先度 |
|------|------|--------|
| LINE Bot 完整預約流程 | 讓客人直接透過 LINE 聊天機器人完成預約（目前僅業主指令）| 高 |
| Google Calendar 整合 | 預約建立 / 修改 / 取消時同步到 Google 行事曆 | 中 |
| 預約前自動提醒 | 排程任務，提前 1 天透過 LINE 推播通知客人 | 中 |
| pytest 測試補齊 | 為預約邏輯、時段衝突、API 端點補充單元測試 | 低 |
| CI/CD GitHub Actions | Push 後自動跑測試，測試通過才部署 | 低 |

---

## 環境變數一覽

### 後端（Render 設定）

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | Supabase PostgreSQL 連線字串（建議改直連）|
| `JWT_SECRET` | JWT 簽章金鑰（正式環境需與本機不同）|
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `none` |
| `API_PUBLIC_BASE_URL` | `https://cales-breathe-v2-vite.vercel.app/api` |
| `FRONTEND_PUBLIC_ORIGIN` | `https://cales-breathe-v2-vite.vercel.app` |
| `STORAGE_BACKEND` | `r2` |
| `R2_*` 系列 | Cloudflare R2 存取金鑰與 Bucket 設定 |
| `GOOGLE_OAUTH_*` | Google OAuth 憑證 |
| `LINE_CHANNEL_SECRET` | LINE Messaging API 驗簽金鑰 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API 推播用 Token |
| `LINE_LOGIN_CHANNEL_ID` | LINE Login Channel ID |
| `LINE_LOGIN_CHANNEL_SECRET` | LINE Login Channel Secret |
| `OWNER_LINE_USER_ID` | 業主的 LINE User ID |

### 前端（Vercel 設定）

| 變數 | 說明 |
|------|------|
| `VITE_API_BASE` | `/api`（透過 Vercel proxy）|
| `VITE_LINE_ADD_FRIEND_URL` | LINE 官方帳號加好友連結（⏳ 待設定）|
