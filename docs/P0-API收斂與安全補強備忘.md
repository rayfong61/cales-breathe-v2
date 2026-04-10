# P0 API 收斂與安全補強備忘

本文件記錄本次 P0 的目標、已完成項目、驗收方式與常見排錯，方便後續交接與回歸測試。

---

## 1) 本次目標

- 預約相關 API 儘量收斂到 v2（`/bookings*`）。
- 補上高風險安全缺口（匿名可建帳、以 body 偽造使用者身分）。
- 保留現行可運作流程，避免一次大爆改。

---

## 2) 已完成項目

### 後端（API）

- 移除公開建帳端點：`POST /users`。
- `/bookings*` 改為需登入 Cookie（`cb_access_token`）：
  - `POST /bookings`
  - `GET /bookings`
  - `GET /bookings/{booking_id}`
  - `POST /bookings/{booking_id}/cancel`
- 建立預約授權規則：
  - 客人只能替自己預約。
  - owner 可代客（`add_by_owner` 必須為本人且角色為 owner）。
- 取消預約改為以 Cookie 身分判定，不再信任 body 的 `user_id`。
- `BookingRead` 補齊客戶顯示欄位：
  - `customer_name`
  - `customer_phone`
  - `customer_photo`

### 前端（Vite）

- `Booking-step3` 由舊 `POST /orders` 改成 `POST /bookings`。
- `Orders` 列表改打 `GET /bookings`，取消改打 `POST /bookings/{id}/cancel`。
- owner 頁面改用 v2 回傳欄位顯示客人姓名、手機、頭像。

### 文件

- 更新 `docs/SPECIFICATION.md`：
  - 移除 `/users` 條目。
  - 更新 `/bookings*` 認證描述與取消規則。

---

## 3) 驗收清單（手動）

### A. 基本流程

- [ ] 客人登入後可建立預約（`POST /bookings` 200）。
- [ ] owner 登入後「代訂紀錄」可正常顯示。
- [ ] owner 可看到客人姓名/手機/頭像（若有照片）。

### B. 權限與安全

- [ ] 未登入 `GET /bookings` 回 401。
- [ ] 未登入 `POST /bookings` 回 401。
- [ ] 客人以他人 `user_id` 建單回 403。
- [ ] 非本人/非 owner 取消回 403。
- [ ] `POST /users` 不可用（404/405 皆可接受）。

### C. 路由收斂

- [ ] 操作「預約紀錄」時，`api` logs 出現 `GET /bookings`。
- [ ] 不再出現 `GET /orders?...` 或 `GET /owner/orders`（若仍出現，見第 5 節）。

---

## 4) 常用指令

### 查看 API logs

```bash
docker compose logs -f api
```

### 重建前端 gateway（確保載入新 bundle）

```bash
docker compose build --no-cache gateway
docker compose up -d gateway
```

### 全測試（後端）

```bash
cd cales-breathe-v2-api
python -m pytest tests/ -q
```

---

## 5) 若 logs 還看到 `/orders*` 的排錯

這通常不是後端沒更新，而是瀏覽器仍在跑舊頁面（快取/BFCache/舊分頁）。

建議步驟：

1. 關掉所有 `localhost` 分頁。
2. 開無痕視窗重新進站。
3. DevTools -> Network 勾選：
   - `Preserve log`
   - `Disable cache`
4. 操作「預約紀錄」並觀察 request：
   - 若仍有 `/orders*`，查看 `Initiator` 與 `Referer` 定位來源。

---

## 6) 下一步（P1 建議）

- 正式環境關閉或保護 `/docs`、`/openapi.json`。
- 收斂 CORS 白名單（避免過寬 regex）。
- 對登入/預約操作加 rate limit。
- 完成 legacy `/orders*` 下架計畫（先 deprecate，再移除）。

