# Cale's Breathe API v2 — 面試目標規格書（v1）

> **定位**：本檔彙整「面試展示用」的產品目標、商業規則、技術與驗收標準。  
> **與主規格書關係**：[SPECIFICATION.md](./SPECIFICATION.md) 為儲存庫**工程現況與階段 A–J** 的對照本；本檔為**目標願景與決策摘要**，實作落地時應同步更新主規格書 §3 與 §9。  
> **背景故事**：[NOTES.md](../NOTES.md)。

---

## 1. 專案定位與面試敘事

### 1.1 目標職缺與展示能力

| 面向 | 說明 |
| --- | --- |
| 職缺 | 後端工程師（Python / FastAPI） |
| 希望面試官看到的能力 | API 設計與資料建模、系統設計與擴展性、第三方整合（LINE / Google） |
| 作品定位 | **可上線的小型商用系統**（非僅教學 demo） |

### 1.2 Demo 展示目標（第一版建議）

- **LINE 實際對話**：Webhook 驗簽、對話引導或指令完成預約。
- **Google Calendar 同步**：建立 / 取消預約對應行事曆事件（儲存 `event_id`）。
- **CI/CD pipeline**：GitHub 上自動跑品質檢查與測試（並可銜接部署）。

---

## 2. MVP 範圍

### 2.1 必做（第一版）

- LINE Webhook 接收與處理（含簽章驗證、事件冪等防重送）。
- 客人預約、業主代客預約（權限與現有 API 契約對齊或於本檔 §4 明定）。
- 查詢 / 取消預約；**取消須符合 §3.4「開約前 24 小時內不可取消」**。
- Google Calendar 同步（建立、取消；失敗時行為見 §6.3）。
- CI：至少 `pytest`；建議加上 `ruff`、`black --check`（見 §8）。

### 2.2 第一版不做（避免範圍膨脹）

- 完整 LIFF 後台 UI（可保留 API／指令式查詢作為替代）。
- 多店員 / 多時區排班（現階段 **全域互斥** 即可）。
- 複雜會員系統（重設密碼、Email 驗證等）。

### 2.3 技術路徑（已決策）

| 項目 | 決策 |
| --- | --- |
| 資料庫 | **先 SQLite 完成功能**，再升級 **PostgreSQL**（與 [SPECIFICATION.md](./SPECIFICATION.md) 階段 C 一致）。 |
| Schema 遷移 | **第二階段**導入 **Alembic**（階段 D）。 |
| 部署 | **Render**；希望具 **Docker / docker-compose** 以利環境一致（見 §9）。 |
| 整合 demo | **真實** LINE / Google 憑證可演示（機密僅環境變數，不入庫）。 |

---

## 3. 角色與商業規則

### 3.1 角色

- **customer**：建立 / 查詢 / 取消自己的預約（在規則允許下）。
- **owner**：代客建立預約、查詢排程、在權限內取消預約。

### 3.2 預約容量與時間

- **同時僅能服務一位客人**（單人工作室）：預約衝突為 **全域互斥**——任一 `confirmed` 預約與新預約時間區間重疊即拒絕（HTTP **409**）。重疊定義與主規格書一致：`new_start < existing_end && existing_start < new_end`。
- **可預約時間粒度**：**30 分鐘**（選時間、驗證與文件敘述以此為準；若服務總時長非 30 的倍數，則以「起始時間落在 30 分鐘格線」為規則，實作時需白話寫入 SPECIFICATION）。

### 3.3 服務選擇（與現行 API 一致）

- `service_ids` 至少一筆；同一 **category** 至多一項，否則 **400**。
- 服務 id 不存在 → **404**（部分服務不存在）。

### 3.4 取消政策（本檔新增之目標規則）

- **開約前 24 小時內不可取消**（以預約開始時間 `booking_date` 為準）。違反時回 **400**，訊息需固定且可測試。
- 操作者須為預約之 `user_id` 或 `role=owner`，否則 **403**（與現行一致）。
- 已取消：**idempotent** 回傳（與現行一致）。
- 狀態流：**僅** `confirmed` → `cancelled`（不導入 `pending` / `completed` 除非另開版本）。

### 3.5 使用者識別（目標）

- **手機號碼**為主要識別與唯一性約束之一（`phone` **unique**）；`line_user_id` 用於 LINE 綁定與 webhook 對應（可為 unique、可空，與主規格書模型對齊後實作）。

---

## 4. API 契約（MVP 目標）

與 [SPECIFICATION.md §3.2](./SPECIFICATION.md) 對齊，並預留：

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| POST | `/line/webhook` | LINE Messaging API Webhook；驗證 `X-Line-Signature`；冪等處理 |
| GET | `/health` | 健康檢查 |
| GET | `/services` | 服務清單 |
| GET | `/services/by-category` | 依分類分組 |
| POST | `/users` | 建立使用者（導入認證後公開範圍見 §7） |
| POST | `/bookings` | 建立預約 |
| GET | `/bookings` | 查詢；`date=YYYY-MM-DD` 可選 |
| GET | `/bookings/{id}` | 單筆 |
| POST | `/bookings/{id}/cancel` | 取消（含 24 小時規則） |

管理端查詢（`/admin/...`）為選用，若實作需與 **owner** 權限一併在 SPECIFICATION 明列。

---

## 5. 資料模型（目標擴充）

在現有 `users`、`services`、`bookings`、`booking_services` 基礎上：

- **bookings**：新增 **`google_calendar_event_id`**（名稱以 migration 為準），供 Calendar 同步與補償。
- **reminder**（階段 I）：可選欄位如 `reminder_sent_at`（見主規格書階段 I）。

---

## 6. 外部整合

### 6.1 LINE

- Webhook：**驗證簽章**；非法簽章拒絕。
- **冪等**：以 LINE `event` id 或自訂鍵避免重送導致重複建單。

### 6.2 Google Calendar

- 預約 **confirmed** 後建立事件，寫入 `event_id`。
- 取消時刪除或更新事件（策略擇一並文件化）。
- 憑證：Service Account 或 OAuth，以環境變數或掛載路徑配置（見 `.env.example`）。

### 6.3 外部失敗策略

- Calendar API 失敗時：**不可**靜默與 DB 長期不一致；至少記錄 log、定義重試或人工補償流程（面試可說明 trade-off）。

---

## 7. 身分驗證（建議分階段）

| 階段 | 做法 |
| --- | --- |
| 短期 | LINE Bot 以 **Webhook 簽章 + `line_user_id`** 識別使用者；與 DB `User` 綁定。 |
| 目標 | **LINE Login（OAuth 2.0）** 完成授權後，後端簽發 **JWT**，保護需登入之 REST API（與 [SPECIFICATION.md 階段 F](./SPECIFICATION.md) 一致）。 |

說明：OAuth 是授權流程；LINE Login 是 LINE 提供的 OAuth 實作；登入成功後後端發 JWT 給前端／LIFF 用於後續 API 為常見模式。

---

## 8. 品質與 CI

| 項目 | 目標 |
| --- | --- |
| 測試 | **API 整合測試** + **service 層單元測試**（預約衝突、24 小時取消等）。 |
| CI | GitHub Actions：`pytest`；建議加 `ruff`、`black --check`。 |
| Coverage | 第一版可先產報告；門檻（如 75%）為選用。 |

---

## 9. 部署與環境

- **Render**：部署目標；設定環境變數與啟動指令文件化（README 或 `docs/DEPLOYMENT.md`）。
- **Docker**：`Dockerfile` 與／或 `docker-compose.yml`（app + 日後 postgres）提升本機與雲端一致性。
- **`.env.example`**：列出 `DATABASE_URL`、`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`、Google 憑證相關鍵名等（不含真值）。

---

## 10. 非功能需求

- **可觀測性**：結構化 log（route、status、latency、request id 擇一）。
- **安全性**：密鑰僅環境變數；生產是否關閉 `/docs` 見主規格書 §8 待決議。
- **健康檢查**：`/health` 可用於 Render／負載檢查。

---

## 11. 與現行程式可能之差異（實作時請逐項勾除）

下列項目落地後，應更新 [SPECIFICATION.md](./SPECIFICATION.md) §3.3 與測試：

- [x] 取消：**24 小時內不可取消**（已落地並補測試）。
- [x] 時間粒度：**30 分鐘** 規則與驗證。
- [x] **手機號碼 unique** 與主要識別敘述。
- [ ] `POST /line/webhook`、Google `event_id` 欄位與同步流程。

---

## 12. 建議里程碑（1～2 週、每週約 25h 之參考節奏）

| 順序 | 主題 | 完成定義（摘要） |
| --- | --- | --- |
| 1 | 規則與測試先行 | 24h 取消、日期篩選、邊界衝突、422；service 單測 |
| 2 | LINE Webhook MVP | 驗簽、回覆、建單、冪等 |
| 3 | Google Calendar + CI | 事件建立/取消、`event_id`；GitHub Actions 綠燈 |
| 4 | Render + 文件 | 可遠端 demo；README 與環境變數說明齊全 |

（細部工時可再拆 issue；階段編號仍與主規格書 A–J 對照。）

---

## 13. 文件與版本控制

- Git 工作流程、分支與 commit 慣例見 [PROJECT_DOCS_AND_GIT.md](./PROJECT_DOCS_AND_GIT.md)。
- 本檔版本：**v1**。重大變更時遞增並於主規格書「變更紀錄」呼應。

---

## 14. 變更紀錄

| 日期 | 摘要 |
| --- | --- |
| 2026-03-24 | 初版：面試目標、MVP、商業規則、整合與品質、與主規格書分工 |
