# Alembic 筆記（cales-breathe-v2）

> 目的：快速理解 Alembic，並保留本專案本次導入與同步 Supabase 的實作紀錄。

---

## 1. Alembic 是什麼

Alembic 是 SQLAlchemy 的資料庫 migration 工具，用來管理「資料表結構（Schema）」版本。

- `upgrade`：真的執行 SQL（建表、加欄位、改欄位）
- `downgrade`：回退版本
- `stamp`：只更新版本紀錄，不執行 SQL

一句話：**Alembic 就是資料庫結構的 Git。**

---

## 2. 本專案目前 Alembic 結構

位於 `cales-breathe-v2-api`：

- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260409_000001_baseline.py`
- `alembic/versions/770727dac7ad_add_test_table.py`

目前版本鏈：

- baseline：`20260409_000001`
- add test table：`770727dac7ad`

---

## 3. 基本指令（最常用）

在 `cales-breathe-v2-api` 目錄執行：

```bash
alembic current
alembic history
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "your message"
```

---

## 4. 本次實作操作紀錄（含踩雷）

### 4.1 SQLite 既有資料庫直接 upgrade baseline 失敗

現象：

- `alembic upgrade head`
- 錯誤：`table line_webhook_events already exists`

原因：

- 本機 `app.db` 早就有舊表（先前由 `create_all` 或既有流程建立）
- baseline migration 又嘗試 `CREATE TABLE`

解法：

```bash
alembic stamp 20260409_000001
alembic current
```

結果：

- SQLite 版本成功對齊 baseline。

### 4.2 新增 `test_table` migration 時夾帶舊差異

現象：

- `alembic revision --autogenerate -m "add test_table"` 生成檔案中，除了 `test_table`，還包含 `bookings` 欄位變更。

原因：

- 本機 DB 結構與 models/基準版本不一致，autogenerate 把歷史差異一起抓出來。

解法：

- 手動編修 `770727dac7ad_add_test_table.py`，只保留 `test_table` 的 create/drop 與 index。

### 4.3 重建本機 DB 後仍遇到 duplicate / already exists

現象：

- `alembic upgrade head` 過程中出現 `duplicate column` 或 `test_table already exists`。

原因：

- 前一次失敗時，SQLite 非交易式 DDL 可能已部分生效（物件已建立，但版本未前進）。

解法：

```bash
alembic stamp 770727dac7ad
alembic current
```

結果：

- 本機 SQLite 對齊到 `770727dac7ad (head)`。

### 4.4 同步 Supabase 時 baseline 再次撞表已存在

現象：

- 連到 Supabase 後執行 `upgrade head`
- 錯誤：`DuplicateTable: relation "line_webhook_events" already exists`

原因：

- Supabase 是既有資料庫，不是空庫，不能直接重跑 baseline 建表。

解法（既有庫）：

```bash
# 先對齊版本（只寫版本，不建表）
DATABASE_URL='postgresql+psycopg2://<...>' alembic stamp 20260409_000001

# 再升級到最新（會套用後續 migration，例如 test_table）
DATABASE_URL='postgresql+psycopg2://<...>' alembic upgrade head

# 檢查版本
DATABASE_URL='postgresql+psycopg2://<...>' alembic current
```

結果：

- Supabase 成功出現 `alembic_version` 與 `test_table`。

---

## 5. 本專案推薦流程（本機 + Supabase）

### 日常 schema 變更

1. 修改 `app/models.py`
2. 產生 migration
3. 人工檢查 migration（必要時手修）
4. 本機 `alembic upgrade head`
5. Supabase `DATABASE_URL='...' alembic upgrade head`

指令：

```bash
alembic revision --autogenerate -m "your change"
alembic upgrade head
DATABASE_URL='postgresql+psycopg2://<...>' alembic upgrade head
```

---

## 6. 何時用 upgrade？何時用 stamp？

- 空資料庫：`upgrade head`
- 既有資料庫首次納管：`stamp <revision>`
- migration 失敗但物件已建立、僅版本未前進：`stamp <revision>`

---

## 7. 快速排錯對照

- `table ... already exists`
  - 代表正在重建既有物件，先確認是否應改用 `stamp`
- `duplicate column name ...`
  - 多半是該欄位已存在，檢查 migration 是否重複操作
- `alembic current` 只顯示 dialect，不顯示 revision
  - 可能尚未建立/寫入 `alembic_version`，先 `stamp` 對齊

---

## 8. 安全提醒

- 命令列貼出完整 DB 連線字串可能外洩帳密，建議定期輪替密碼。
- 正式環境執行 migration 前，先備份或在 staging 驗證。

---

## 9. 目前狀態（本次操作結論）

- 本機 SQLite：已對齊到 `770727dac7ad (head)`
- Supabase：已建立 `alembic_version`，且 `test_table` 已可見
- Alembic 流程已可正式使用於後續 schema 演進

---

## 10. 本機使用 Docker Compose 時，資料庫怎麼更新

本專案 `docker-compose.yml` 會啟動：

- `postgres`：本機 PostgreSQL（使用 `postgres_data` volume 持久化）
- `api`：FastAPI，`DATABASE_URL` 指向 `postgres:5432`

### 10.1 目前會自動做的事

`api` 啟動時會跑 `init_db()`，內部是 `Base.metadata.create_all(...)`。

這代表：

- 會建立「不存在的 table」
- 不會安全處理「欄位修改/刪除/型別變更」

所以在 Docker 環境也應以 Alembic migration 為主，不要依賴 `create_all` 做 schema 演進。

### 10.2 Docker 內更新 DB 的正確指令

在專案根目錄（有 `docker-compose.yml`）執行：

```bash
docker compose exec api alembic current
docker compose exec api alembic upgrade head
docker compose exec api alembic history
```

需要回退時：

```bash
docker compose exec api alembic downgrade -1
```

### 10.3 建議實務流程（Docker 本機 + Supabase）

1. 在開發環境修改 `models`
2. 產生 migration 並人工檢查
3. 用 Docker 本機 Postgres 測試 `upgrade head`
4. 驗證 API 正常後，再同步到 Supabase `upgrade head`

對應指令：

```bash
# 產生 migration（通常在本機 repo 直接跑）
alembic revision --autogenerate -m "your change"

# Docker 本機 Postgres 驗證
docker compose exec api alembic upgrade head

# Supabase 同步
DATABASE_URL='postgresql+psycopg2://<...>' alembic upgrade head
```
