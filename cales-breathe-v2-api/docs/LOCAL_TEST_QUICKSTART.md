# 本機快速測試（舊前端 + v2 API）

## 1) 後端啟動

在 `cales-breathe-v2-api` 執行：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

重點 `.env`（開發環境）：

- `JWT_SECRET=...`
- `COOKIE_SECURE=false`
- `COOKIE_SAMESITE=lax`
- `FRONTEND_PUBLIC_ORIGIN`（與你開前端的網址一致，例如 `http://192.168.0.101:3000`）
- `STORAGE_BACKEND=local`（若要改 R2，見下方章節）

> 正式環境請改回 `COOKIE_SECURE=true` 並搭配 HTTPS。

### 頭像儲存改用 Cloudflare R2（可選）

若要把 `PUT /account/update` 的照片改存 R2，請在 `.env` 設：

```env
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=...
R2_PUBLIC_BASE_URL=https://<你的公開網域或r2.dev>
R2_KEY_PREFIX=uploads
```

說明：

- `R2_PUBLIC_BASE_URL` 會直接組成 `user.photo` 回傳給前端顯示。
- 若未設定完整，後端會回 `500` 提示 `R2 設定不完整`。
- 本機開發可先維持 `STORAGE_BACKEND=local`，不影響既有 `/uploads` 流程。

### OAuth（Google / LINE）

1. 在 `.env` 設定 `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`、`LINE_LOGIN_CHANNEL_ID` / `LINE_LOGIN_CHANNEL_SECRET`。
2. 設定 **`API_PUBLIC_BASE_URL`**，並在 Google Cloud / **LINE Developers（LINE Login 那個 channel）** 登記**完全相同**的 callback：
   - `{API_PUBLIC_BASE_URL}/auth/google/callback`
   - `{API_PUBLIC_BASE_URL}/auth/line/callback`
3. 未設定憑證時，`GET /auth/google`、`GET /auth/line` 會回 `503`（避免誤以為已接上）。

#### Google：不要用區網 IP（192.168.x.x）當 redirect

若後台登記的是 `http://192.168.0.101:8000/auth/google/callback`，Google 可能顯示：

`device_id and device_name are required for private IP` / `Error 400: invalid_request`

**本機電腦測 OAuth** 請改為：

- `.env`：`API_PUBLIC_BASE_URL=http://127.0.0.1:8000`（或 `http://localhost:8000`，兩者擇一且與 Google Console **一字不差**）
- Google Cloud「已授權的重新導向 URI」新增：`http://127.0.0.1:8000/auth/google/callback`
- 前端 `.env`：`VITE_API_BASE=http://127.0.0.1:8000`
- 瀏覽器用 **`http://127.0.0.1:3000`** 開前端（與 cookie / 同源策略較一致）

**手機或區網別台**要測 Google 登入時，區網 IP 通常不可行，請改用 **HTTPS tunnel**（ngrok / cloudflared）取得公開 `https://xxx/...`，再把該網址設成 `API_PUBLIC_BASE_URL` 並登記到 Google。

#### LINE：`Invalid redirect_uri`

代表程式送出的 `redirect_uri` 與 LINE Developers 後台**沒登記或字元不一致**（含 `http`/`https`、port、尾隨斜線）。

請到 **LINE Login** 的 Channel → **Callback URL**（或允許的 redirect 清單）新增與 `.env` 中 `API_PUBLIC_BASE_URL` 組出來的網址**完全一致**的一筆，例如：

`http://127.0.0.1:8000/auth/line/callback`

（若你改用 ngrok，就要登記 ngrok 的那個 URL。）

---

## 2) 前端啟動

在 `CALES-BREATHE-1/frontend/.env` 設定：

```env
VITE_API_BASE=http://192.168.0.101:8000
```

在 `CALES-BREATHE-1/frontend` 執行：

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

手機開：

`http://192.168.0.101:3000`

---

## 3) 測試流程（最短版）

1. 註冊或登入（`/login`）
2. 確認 `GET /me` 回 `200`
3. 選服務與時段（`/unavailable-dates`, `/unavailable-times`）
4. 送出預約（`PUT /account/update2` → `POST /orders`）
5. 到 `我的帳號 > 預約紀錄` 檢查資料與取消功能

---

## 4) 常見問題

- **`/me` 401**：通常是 cookie 沒帶上；確認前後端都使用同一組 host（建議都用 `192.168.0.101`）。
- **手機登入後仍未登入**：確認後端 `.env` 為 `COOKIE_SECURE=false`、`COOKIE_SAMESITE=lax`（僅開發）。
- **取消顯示更新失敗**：通常是後端取消規則限制（例如開約前 24 小時內不可取消）。
- **頭像更新 404**：確認後端已有 `PUT /account/update`，並且 `/uploads` 靜態路徑已掛載。
- **OAuth 503**：後端尚未填 Google/LINE 憑證；或 callback URL 與 `API_PUBLIC_BASE_URL` 不一致。
- **`OAuth state 無效或已過期`**：多為 `JWT_SECRET` 在 `.env` 有尾端空白／換行導致簽名不一致（已於程式內 `strip`）；或授權流程超過 state 有效時間。請重開一輪登入並重啟 uvicorn。
