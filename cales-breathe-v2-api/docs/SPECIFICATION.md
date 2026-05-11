# Cale's Breathe API v2 — 開發規格書

> **用途**：依階段實作與驗收時對照；產品背景與故事見 [NOTES.md](../NOTES.md)。  
> **版本**：0.1（對應 API `0.1.0`）  
> **維護**：階段完成或契約變更時更新本檔「實作進度」與「已決策」小節。

---

## 1. 文件關係

| 文件 | 角色 |
| --- | --- |
| [NOTES.md](../NOTES.md) | 商業目標、角色、功能需求長文、舊專案連結 |
| 本規格書 | **工程階段、驗收條件、API/資料現況、環境變數** |
| [SPEC_INTERVIEW_V1.md](./SPEC_INTERVIEW_V1.md) | **面試目標規格**：MVP 邊界、商業規則決策、Demo 與技術路徑摘要 |
| [README.md](../README.md)（總覽）／[README-legacy-root.md](../../docs/README-legacy-root.md)（本機 Compose、OAuth、Webhook、限流等指令） | 專案入口與啟動說明 |
| [PROJECT_DOCS_AND_GIT.md](./PROJECT_DOCS_AND_GIT.md) | 文件清單與 Git 版本控制慣例 |

---

## 2. 範圍與目標

### 2.1 範圍內

- FastAPI 後端：預約、服務、使用者、**LINE Webhook**、OAuth 登入／Cookie、Google Calendar 同步（細見 §9）；管理端、提醒排程等延續階段表。
- 資料：依 `DATABASE_URL` 為 **SQLite**（預設本機）或 **PostgreSQL**（Docker Compose／Supabase 等）；Schema 以 SQLAlchemy models 為準，遷移以 **Alembic** 為準。

### 2.2 範圍外（本規格不強制實作時程）

- 舊站 React 改版（僅在 NOTES 中描述導流策略）。
- LIFF 完整後台 UI（可列為後續階段擴充）。

---

## 3. 現況：MVP（已實作）— 驗收基線

### 3.1 技術

- Python：FastAPI、Uvicorn、SQLAlchemy 2.x。
- DB：[app/database.py](../app/database.py) 依 **`DATABASE_URL`**：`sqlite:///./app.db`（未設定時預設）或 **PostgreSQL**（連線字串）。根目錄 **Docker Compose** 會注入 Postgres，與正式環境 **Supabase** 同為 PostgreSQL 路線。
- 啟動時：`lifespan` 內 `init_db()` + 服務種子（[app/main.py](../app/main.py)）；正式／Compose 環境建議 **`alembic upgrade head`** 與 models 對齊。

### 3.2 HTTP API 一覽

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| GET | `/health` | 健康檢查；回傳含 `db` 識別（`sqlite` 或 `postgresql` 等，依連線而定） |
| GET | `/services` | 列出服務；依 `CATEGORY_ORDER` 與 `sort_order` 排序 |
| GET | `/services/by-category` | 依分類分組（供 LINE 選單）；分類順序同 `CATEGORY_ORDER` |
| POST | `/bookings` | 建立預約（`BookingCreate`） |
| GET | `/bookings` | 查詢預約；需登入 Cookie；Query `date=YYYY-MM-DD` 可選 |
| GET | `/bookings/{booking_id}` | 單筆預約（不限狀態，找不到 404） |
| POST | `/bookings/{booking_id}/cancel` | 取消預約（需登入 Cookie）；軟刪除為 `cancelled` |

### 3.3 商業規則（必須維持向後相容，除非另有版本計畫）

1. **服務選擇**：`service_ids` 至少一筆；同一 **category** 至多選一項，否則 HTTP **400**。
2. **服務存在性**：任一所選 id 不存在 → **404**（訊息：部分服務不存在）。
3. **時段衝突**：採「應用層 + DB 層」雙保險；與 `status in (pending, confirmed)` 的預約比對，區間重疊則 **409**（該時段已被預約）。  
   - 重疊定義：`new_start < existing_end && existing_start < new_end`（與程式一致）。
   - PostgreSQL 以 `EXCLUDE USING gist` 約束作為最終防線，避免同時提交造成雙重預約。
   - **時間粒度**：預約開始時間需落在 30 分鐘格線（`HH:00` 或 `HH:30`），否則 **400**。
4. **取消**：操作者由登入 Cookie 判定；需為預約之 `user_id` 或 `role=owner`，否則 **403**；已取消 idempotent 回傳；非 `confirmed` 不可取消 → **400**。  
   - **時間窗限制**：預約開始前 24 小時內不可取消 → **400**（訊息：開約前 24 小時內不可取消）。

### 3.4 資料模型摘要（實作以程式為準）

- `users`：`name`, `line_user_id`（unique 可空）, `phone`（unique）, `role`（`customer` \| `owner`）, `created_at`。
- `services`：`name`, `category`, `duration_minutes`, `price`, `sort_order`, `created_at`。
- `bookings`：`user_id`, `booking_date`, `total_duration_minutes`, `total_price`, `status`, `notes`, `google_calendar_event_id`（可空）, `created_at` 等（實作以 [app/models.py](../app/models.py) 為準）。
- `booking_services`：多對多關聯。

### 3.5 已知技術債（後續階段處理）

- 衝突檢查：應用層已做 overlap check，PostgreSQL 另以 `EXCLUDE` 約束保證併發一致性；SQLite 僅有應用層保護。
- **Alembic**、**pytest**（[`tests/`](../tests/)）已具備；**GitHub Actions CI** 已上線（`.github/workflows/api-ci.yml`，後端路徑變更觸發 `pytest`）。
- **P0** 已完成：`POST /users` 已移除；`/bookings*` 需登入 Cookie 與授權規則（見 [P0-API收斂與安全補強備忘.md](../../docs/P0-API收斂與安全補強備忘.md)）。正式環境 **`/docs` 保護、CORS 白名單、登入 rate limit** 已完成第一階段收斂（仍可持續補強敏感路由覆蓋）。

---

## 4. 階段開發規格（A–J）

每階段需滿足：**交付物** + **驗收條件（Done 定義）**。建議順序見 §5。

### 階段 A — 版本控制與專案衛生

| 項目 | 規格 |
| --- | --- |
| 交付物 | Git 儲存庫、`.gitignore`（至少：`app.db`、`__pycache__`、`.env`）、README 補環境與指令 |
| 驗收 | 新 clone 可依 README 安裝並啟動；機密不進庫 |

### 階段 B — 自動化測試

| 項目 | 規格 |
| --- | --- |
| 交付物 | `pytest`、`tests/`、`conftest.py`；測試用 DB 與本機 `app.db` **隔離**（獨立 engine 或 tmp 檔） |
| 驗收 | 至少涵蓋：`POST /bookings` 成功/404/400/409；`GET /bookings?date=` 當日篩選；（可選）`/services/by-category` 分類順序 |
| 主要檔案 | `tests/conftest.py`、`tests/test_bookings.py`（命名可調）；[app/main.py](../app/main.py) 可能需可注入 `get_db` |

### 階段 C — PostgreSQL + Docker

| 項目 | 規格 |
| --- | --- |
| 交付物 | `docker-compose.yml`（postgres、volume、port）；`DATABASE_URL` 由環境讀取 |
| 驗收 | `docker compose up -d` 後，設好 `DATABASE_URL` 可跑通現有 API；SQLite 預設路徑仍可在無 Docker 時開發（若維持雙模式） |

### 階段 D — Alembic

| 項目 | 規格 |
| --- | --- |
| 交付物 | Alembic 初始化、baseline 對齊現有 models；後續 schema 變更僅經 migration |
| 驗收 | 新環境可用 `upgrade head` 建表；不再依賴「刪 `app.db`」作為常態流程 |

### 階段 E — 預約衝突查詢與併發（論述 + 實作）

| 項目 | 規格 |
| --- | --- |
| 交付物 | 衝突檢查改為資料庫可執行之查詢（單一 query 或等效） |
| 驗收 | 行為與 §3.3 一致；文件或註解中說明 race 情境與採用策略（鎖／重試／約束擇一或組合） |

### 階段 F — 身分驗證與授權

| 項目 | 規格 |
| --- | --- |
| 交付物 | **短效 access JWT** + **HttpOnly refresh**（DB 存 token hash、輪替、`POST /auth/refresh`）；OAuth／本地登入皆簽發雙 cookie；`/admin/...` 僅 `owner`；公開端點策略**明文化** |
| 驗收 | 未授權無法操作管理端；refresh 可撤銷（登出）；與測試策略一致（測試 token 或 dependency override） |

### 階段 G — LINE Webhook

| 項目 | 規格 |
| --- | --- |
| 交付物 | `POST /line/webhook`；驗證 `X-Line-Signature`；`line_user_id` 對應 `User`；對話狀態可追溯 |
| 驗收 | 非法簽章拒絕；LINE 重送不重複建立預約（冪等鍵或事件 id 表）；可於測試中 mock 簽章 |

### 階段 H — Google Calendar

| 項目 | 規格 |
| --- | --- |
| 交付物 | 預約建立/更新/取消時同步行事曆；`bookings` 保存 `event_id`（欄位名稱於 migration 決定） |
| 驗收 | 失敗時行為已定義（重試、補償、log）；不靜默丟失與 DB 不一致狀態 |

### 階段 I — 提醒排程

| 項目 | 規格 |
| --- | --- |
| 交付物 | 週期掃描「明日」預約並 LINE push；避免重複推播（例：`reminder_sent_at`） |
| 驗收 | 時區與「明日」定義明確；重啟不重複送（或接受至少一次語意並說明） |

### 階段 J — CI/CD 與部署

| 項目 | 規格 |
| --- | --- |
| 交付物 | GitHub Actions 跑 `pytest`；部署目標與環境變數注入方式文件化 |
| 驗收 | PR/主分支可見測試結果；正式環境 health 可用 |

---

## 5. 建議執行順序

- **完整打底**：A → B → C → D → E → **G** → **F** → H → I → J。  
- **時間緊**：A + B + G（最小 webhook + 呼叫既有 booking）→ 再補 C、D、F、H、I、J。

---

## 6. 與 NOTES.md 章節對照

| NOTES 段落 | 本規格階段 |
| --- | --- |
| 學習路線 1（Git） | A |
| 學習路線 2（Postgres + CRUD） | C、D（MVP 已在 §3） |
| 學習路線 3（JWT、admin） | F |
| 學習路線 4（LINE） | G |
| 學習路線 5（Calendar、提醒） | H、I |
| 學習路線 6（pytest、CI/CD） | B、J |

NOTES 底部「選項 A / B / C」：對應 **B / G / C**（細節以本檔階段為準）。

---

## 7. 環境變數（預留）

| 變數 | 階段 | 說明 |
| --- | --- | --- |
| `DATABASE_URL` | C | 例如 Postgres 連線字串 |
| `LINE_CHANNEL_SECRET` | G | Webhook 簽章 |
| `LINE_CHANNEL_ACCESS_TOKEN` | G、I | 回覆與 push |
| `JWT_SECRET` | F | HS256 簽章用 |
| `ACCESS_TOKEN_TTL_MINUTES` | F | access JWT 分鐘數（預設 60） |
| `REFRESH_TOKEN_TTL_DAYS` | F | refresh cookie／DB 列天數（預設 30） |
| `ACCESS_TOKEN_COOKIE_NAME`／`REFRESH_TOKEN_COOKIE_NAME` | F | 選用；預設 `cb_access_token`、`cb_refresh_token` |
| Google／LINE OAuth 變數 | F | 見 `.env.example` |
| Google 憑證路徑或 JSON | H | Service Account 等 |

---

## 8. 待決議事項（TBD）

- [ ] 行事曆與 DB 不一致時的補償流程（階段 H）

---

## 9. 實作進度（請於完成階段時更新）

| 階段 | 狀態 | 完成日期 | 備註 |
| --- | --- | --- | --- |
| A | 完成 | | Git、README、`.gitignore` 等 |
| B | 完成 | | `pytest`、`tests/`、`conftest.py` |
| C | 完成 | | 根目錄 `docker-compose.yml`、Postgres + gateway |
| D | 完成 | | `alembic/`、baseline 與增量 revision |
| E | 未開始 | | 衝突查詢仍見 §3.5 |
| F | 完成 | | Google／LINE OAuth、短效 JWT + refresh（`refresh_tokens` 表）、`/bookings` 授權已落地；後續為持續補強 |
| G | 完成 | | `POST /line/webhook`、簽章與冪等鍵 |
| H | 進行中 | | `google_calendar_event_id`、同步與取消；補償流程論述見 §8 TBD |
| I | 未開始 | | 預約提醒排程 |
| J | 完成 | | `.github/workflows/api-ci.yml`（pytest）與 `.github/workflows/api-cd.yml`（OIDC/WIF -> build/push/deploy Cloud Run）已上線 |

狀態建議：`未開始` / `進行中` / `完成`。

---

## 10. 變更紀錄

| 日期 | 變更摘要 |
| --- | --- |
| 2026-03-20 | 初版：整合 MVP 現況（含 cancel）與階段 A–J 驗收條件 |
| 2026-05-07 | §3.1／§3.5／§9 對齊：DB 雙模式、Alembic／pytest、P0、階段進度；§2.1 範圍與 webhook |
| 2026-05-07 | 對齊面試敘事：CI/CD 已上線（api-ci/api-cd）、F/J 狀態更新、移除 docs 保護 TBD |
