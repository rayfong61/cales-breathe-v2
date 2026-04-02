# `CALES-BREATHE-1` 重構計畫（V2 主導）

## 0. 文件目的
把你的原本預約網站（`CALES-BREATHE-1`）重構成：
- **後端使用 `cales-breathe-v2-api`（FastAPI + v2 schema）**
- **前端 UI/流程盡量保留原樣**
- **Linebot 用按鈕更好導流到原本 React 預約流程**
- **修掉舊版登入手機端不穩 bug**

本文件定義：
1. BFF adaptor（相容層）需要提供的端點契約
2. 舊前端 ↔ v2 的資料映射規則（含中文字串 addons/services）
3. 里程碑與驗收條件
4. 風險清單與待確認事項

---

## 1. 已確認的決策（鎖定以免返工）
1. **V2 主導**：預約核心邏輯與衝突檢查以 `cales-breathe-v2-api` 的 `users/services/bookings` 為準。
2. **JWT（Access Token）+ HttpOnly Cookie**：有效期 **30 天**。
3. **S3（雲端照片）**：`Account` 頁可更新與顯示照片。
4. **中文名稱字串**：`orders` 回傳必須用「中文名稱字串陣列」讓前端 `join()` 顯示成功。
5. **手機唯一 + 最後才確認**：
   - 登入完成後先選服務/日期/時段
   - 最後一步在 `PUT /account/update2` 確認手機（必填 + 唯一）
6. **必要少量改動允許**：
   - 允許前端在登入流程做必要 fallback（popup 被擋/訊號回收不到）
   - 允許修正必要 state bug（例如 `setInputError` 未宣告）
7. **Linebot 按鈕**：不走文字對話做完整表單，改用「按鈕/URI 導流」：
   - `服務項目` → `/services`
   - `立即預約` → `/booking`
   - 使用者走 React 原本流程：`/booking` → `/booking-step2` → `/booking-step3`

---

## 2. 目標與範圍
### 2.1 目標（Done Definition）
- 使用者能在瀏覽器/手機完成完整預約（含最後確認手機唯一、建立 booking、顯示於 Account/Orders、可取消）。
- Linebot 按鈕能正確導流到服務頁與預約頁，並可完成下訂流程。
- Google/LINE 登入在手機端不再因 popup/postMessage 限制而失敗或卡住。
- `Account` 頁可更新照片並正確顯示。

### 2.2 範圍內端點（BFF adaptor 必須支援舊前端）
BFF adaptor 需要提供（URL 與語意對齊舊版前端）：
- `GET /me`
- `POST /login`
- `GET /logout`
- `GET /auth/google`、`GET /auth/google/callback`
- `GET /auth/line`、`GET /auth/line/callback`
- `GET /unavailable-dates`
- `GET /unavailable-times?date=YYYY-MM-DD`
- `PUT /account/update2`
- `PUT /account/update`（multipart 上傳 `photo`）
- `POST /orders`
- `GET /orders?client_id=...`
- `PUT /orders/cancel/:id`

---

## 3. 高層架構（建議）
### 3.1 分層責任
1. **v2 核心服務（`cales-breathe-v2-api`）**
   - `POST /bookings`：衝突檢查、建立 booking、寫入 DB
   - `GET /services`：列出服務
   - `GET /bookings` 與取消：查詢/狀態更新
2. **BFF adaptor（新增/擴充於 FastAPI）**
   - 提供舊前端所需路由與 response JSON shape
   - 將舊前端的 `booking_detail.services/addons`（中文名稱）映射到 v2 的 `service_ids`
   - JWT cookie 驗證與 `/me` 回傳舊前端 user shape
3. **前端**
   - `CALES-BREATHE-1` UI/流程盡量不變
   - 允許必要少量改動（fallback + 必要 state bug 修復）

---

## 4. 資料映射規則（關鍵）
### 4.1 主項目與加購（services / addons）如何映射到 v2
舊前端 selection 來源：
- 主項目：`BookingItems.jsx`（中文名稱字串、按分類 X選1）
- 加購：`AddingItems.jsx`（4 種中文名稱字串，可多選）
  - `腋下加購`
  - `上唇加購`
  - `手指加購`
  - `腳趾加購`

v2 目前有規則：同一 `category` 最多選 1（X選1 驗證）。
因此重構時要避免「加購與主項目撞 category」導致被擋。

建議規則：
1. 在 v2 `services` seed 中新增 4 個加購 service
2. 給加購 service 用獨立 `category` 命名空間：
   - `addon-armpit`
   - `addon-lip`
   - `addon-fingers`
   - `addon-toes`
3. BFF adaptor 在 `POST /orders`：
   - `booking_detail.services`（主項目中文）→ 對到 v2 主項目 service_id
   - `booking_detail.addons`（加購中文）→ 對到 v2 加購 service_id
   - 合併成 v2 `service_ids` 呼叫 `POST /bookings`

### 4.2 `unavailable-*` 時段回傳格式
舊前端 `Booking-step2` 會使用：
`new Date('1970-01-01T' + start_time)`
因此 BFF 必須回傳：
- `GET /unavailable-dates`：`["YYYY-MM-DD", ...]`
- `GET /unavailable-times?date=YYYY-MM-DD`：
  - `[{ start_time: "HH:MM:SS", end_time: "HH:MM:SS" }, ...]`

### 4.3 `GET /orders` 回傳格式（中文字串）
舊前端 `Orders.jsx` 會做：
- `order.booking_detail.services.join("、")`
- `order.booking_detail.addons.join("、") || "無"`
- `order.booking_time.slice(0,5)`
- `order.is_cancelled`

BFF 必須回傳每筆訂單（陣列元素）具備至少：
- `id`
- `booking_date`（建議 `YYYY-MM-DD` 或可被 Date 解析的字串）
- `booking_time`（必須 `HH:MM:SS`）
- `total_price`
- `total_duration`
- `booking_note`
- `is_cancelled`（依 v2：`booking.status === "cancelled"`）
- `booking_detail`：
  - `services`: 中文名稱字串陣列
  - `addons`: 中文名稱字串陣列

並且 `GET /orders?client_id=...` 回傳是「陣列」，不是包一層。

---

## 5. Endpoint 契約（BFF ↔ 舊前端）
> 以下以舊前端需求為準；BFF 內部再呼叫 v2 核心邏輯。

### 5.1 `GET /me`
- 成功：`{ "user": <舊前端 user shape> }`
- 未登入/過期：`401`（或 `{ "user": null }`，但需確保前端能正確置 `user=null`）

舊前端 user shape 至少需包含（Account/Booking-step3 用）：
- `id`
- `client_name`
- `contact_mobile`
- `contact_mail`
- `provider`
- `photo`
- `birthday`
- `address`

### 5.2 `POST /login`
- request：`{ contact_mail, password }`
- success 回：
  - `{ "message": "...", "user": <與 GET /me 相容的 user shape> }`
- fail 回：
  - `401/400` + `{ "message": "登入失敗原因" }`

### 5.3 `PUT /account/update2`
- request body：`{ client_name, contact_mobile }`
- 驗證規則：
  - `contact_mobile` 必填
  - 手機唯一（重複手機 → 回 `409`）
- success 回：
  - `{ ...updatedUser 舊欄位... }`（讓前端可用）

### 5.4 `PUT /account/update`（multipart）
- request：
  - multipart `photo` file + 其他欄位（由前端決定）
- success 回：
  - `{ updatedUser: <舊前端欄位> }`
- user.photo 回傳必須是「完整公開 URL」以便前端顯示。

### 5.5 `POST /orders`
- request（舊前端）：
  - `client_id`
  - `booking_date` + `booking_time`
  - `total_price`, `total_duration`
  - `booking_detail`：JSON.stringify `{ services: string[], addons: string[] }`
  - `booking_note`: string | null
- 驗證（BFF層）：
  - 呼叫 v2 建 booking 前先確保手機已存在（符合“最後才填且唯一”）
- success：
  - `201` + `{ "message": "...", "orderId": ... }`
- fail：
  - `400/409` + `{ "message": "..." }`

### 5.6 `GET /orders?client_id=...`
- 回傳：`[ order1, order2, ... ]`
- order 形狀見 4.3（中文字串 + is_cancelled + booking_time 格式）

### 5.7 `PUT /orders/cancel/:id`
- request：空 `{}` 即可
- 驗證：權限/權限比對需符合 v2 的 cancellation 規則（時間窗與 actor）
- success：回訂單或至少回 success JSON

---

## 6. JWT Cookie 設計（MVP）
### 6.1 cookie 規格
- `HttpOnly`
- `Secure`
- `SameSite=None`
- `Path=/`
- `Max-Age=2592000`（30 天）

### 6.2 失效行為
- token 過期 → `GET /me` 回 `401`
- 前端自動把 `user` 置為 null，booking-step3 會顯示登入區塊與引導。

---

## 7. S3 照片規格（雲端 + 前端相容）
### 7.1 上傳流程
1. 前端 `PUT /account/update` 送 multipart `photo`
2. BFF 接到檔案 → 上傳 S3
3. 將 `user.photo` 設為完整公開 URL：`https://...`

### 7.2 檔名
- 使用 uuid 作為檔名，避免覆蓋與猜測檔案。

---

## 8. Linebot 按鈕導流（最低對話成本）
### 8.1 建議設定
- `服務項目` → `https://your-domain/services`
- `立即預約` → `https://your-domain/booking`

### 8.2 使用者完整路徑
- 點按鈕進入 `/booking`
- 選服務 → `/booking-step2`
- 選日期/時段 → `/booking-step3`
- 最後一步登入（若未登入）→ `PUT /account/update2` 手機唯一校驗 → `POST /orders`

---

## 9. 重點修 bug（登入手機端不穩）
你舊版登入流程使用 popup + `postMessage("login-success")`。
手機/Line WebView 常會阻擋 popup 或訊號回不來。

修復策略（必要少量改動）：
- callback 若偵測 `window.opener` 不存在，就直接做 redirect（你後端 callback 已有類似邏輯，BFF 需維持）
- 前端若 popup 被阻擋，應 fallback 到同頁 redirect，並在回來後重新呼叫 `/me`

驗收：
- 手機端 Google/LINE 登入後，必定能回到 `/booking-step3`，並能送出預約。

---

## 10. 里程碑計畫（建議順序）
### Milestone 1：BFF adaptor 打通（不含 Linebot）
交付：
- `/me`, `/login`, `/logout`
- `/auth/google`, `/auth/line`（簽發 JWT cookie）
- `/unavailable-dates`, `/unavailable-times`
- `PUT /account/update2`, `POST /orders`
- `GET /orders`, `PUT /orders/cancel/:id`
驗收：
- 使用者在瀏覽器能完整預約一次並取消。

### Milestone 2：S3 照片
交付：
- `PUT /account/update` 上傳到 S3
- `/me` 回傳 photo URL
驗收：
- Account 頁可更新頭像並顯示正確。

### Milestone 3：Linebot 按鈕導流
交付：
- Rich menu/按鈕 URI 設定完成
驗收：
- Linebot 點按鈕能完成預約流程。

### Milestone 4：手機登入穩定性修復
交付：
- popup/postMessage fallback 修正
驗收：
- 手機端登入成功率達到預期（至少可穩定回到 booking-step3）。

---

## 11. 風險清單（提前避免踩坑）
1. v2 `category X選1` 與加購映射衝突 → 加購必須獨立 category。
2. v2 `phone unique 且不可空` 與你「最後才填手機」矛盾 → 必須允許登入先空值，唯一性放在 `update2`。
3. 時段格式不一致（`HH:MM:SS` vs `HH:MM`）→ 會讓重疊計算/顯示壞掉。
4. `/orders` 回傳 shape 不一致（陣列/欄位缺漏/時間格式）→ Account/Orders 畫面錯誤。
5. JWT cookie 跨域/secure/sameSite 失誤 → `GET /me` 永遠未登入。

---

## 12. 交付前檢查清單（可作為你開工的 Done）

### 12.1 原始條目（對照實作狀態）

- [x] `GET /me` 回傳舊前端所需欄位（含 photo/birthday/address）
- [x] `PUT /account/update2` 手機必填 + unique（重複回 409 + message）
- [x] `POST /orders` services/addons 中文字串能正確映射到 v2 service_ids
- [x] `GET /orders` 回傳陣列，且 `booking_time` 為 `HH:MM:SS`
- [x] `GET /unavailable-times` 回傳 `{start_time,end_time}` 為 `HH:MM:SS`
- [x] `PUT /account/update` 上傳 photo 到雲端並回公開 URL（實作為 **Cloudflare R2**，S3 相容 API；`STORAGE_BACKEND=local` 時仍為本機 `/uploads/`）
- [ ] 手機端 Google/LINE 登入成功後能回到 `/booking-step3` 並送出預約（LINE 區網可驗；**Google 手機**建議以 **staging HTTPS** 再驗收打勾）
- [ ] Linebot 按鈕導流：`/services` 與 `/booking` 深連結可用（需在 LINE Official 後台設定 Rich menu / URI）

### 12.2 逐項打勾表（實測紀錄）

| # | 檢查項 | 狀態 | 說明 |
|---|--------|------|------|
| 1 | `GET /me` 回傳舊前端所需欄位（含 photo/birthday/address） | **✅** | `_legacy_user_shape` 已含 `id`、`client_name`、`contact_mobile`、`contact_mail`、`provider`、`photo`、`birthday`、`address`。 |
| 2 | `PUT /account/update2` 手機必填 + unique（重複回 409） | **✅** | 必填與唯一性檢查已實作；前端 Booking step3 會顯示手機衝突訊息。 |
| 3 | `POST /orders` services/addons 中文 → v2 `service_ids` | **✅** | `_service_ids_from_legacy_detail` 映射 + 重複 service 去重，避免關聯表唯一鍵錯誤。 |
| 4 | `GET /orders` 回傳陣列，且 `booking_time` 為 `HH:MM:SS` | **✅** | `legacy_list_orders` 回陣列；`_legacy_order_from_booking` 使用 `%H:%M:%S`。 |
| 5 | `GET /unavailable-times` 回 `{start_time,end_time}` 為 `HH:MM:SS` | **✅** | `legacy_unavailable_times` 以 `strftime("%H:%M:%S")` 輸出。 |
| 6 | `PUT /account/update` 上傳 photo 到雲端並回公開 URL | **⚠️ 等價完成** | 計畫原文為 AWS S3；實際為 **Cloudflare R2（S3 相容）**，`STORAGE_BACKEND=r2` 時 `user.photo` 為完整公開 URL；`local` 時仍為 `/uploads/...`。 |
| 7 | 手機端 Google/LINE 登入後能回 `/booking-step3` 並送出預約 | **⚠️ 部分** | **LINE + 區網**多數可測通；**Google 手機**在 tunnel/跨網域下 cookie 易不一致，建議 **staging HTTPS** 再驗收打勾。 |
| 8 | Linebot 按鈕導流：`/services` 與 `/booking` 深連結可用 | **❌ 待營運設定** | 程式路由已存在；需在 **LINE Official 後台** Rich menu / URI 指到正式網址（本機 IP 不適合長期）。 |

