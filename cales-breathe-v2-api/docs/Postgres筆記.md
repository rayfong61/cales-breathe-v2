# PostgreSQL × SQLAlchemy × Alembic 筆記

> 本筆記對應專案：`cales-breathe-v2-api`
> 撰寫日期：2026-03-29

---

## 一、三者的角色分工

```
┌─────────────────────────────────────────────────────────────┐
│                        你的 FastAPI 程式                      │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  models.py   │    │ database.py  │    │   main.py     │  │
│  │  (定義結構)   │    │  (建立連線)   │    │  (業務邏輯)   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬────────┘  │
│         │                  │                   │            │
└─────────┼──────────────────┼───────────────────┼────────────┘
          │                  │                   │
          ▼                  ▼                   ▼
   ┌─────────────┐   ┌───────────────┐   ┌────────────────┐
   │  Alembic    │   │  SQLAlchemy   │   │   PostgreSQL   │
   │ (管 Schema  │   │  (ORM 翻譯層) │   │  (真正存資料)   │
   │  版本歷史)  │   │               │   │               │
   └─────────────┘   └───────────────┘   └────────────────┘
```

| 工具 | 職責一句話 | 類比 |
|---|---|---|
| **PostgreSQL** | 真正儲存資料的資料庫伺服器 | 倉庫本體 |
| **SQLAlchemy** | 讓你用 Python 操作資料庫，不用寫 SQL | 倉庫管理員 |
| **Alembic** | 版本控制資料庫結構（Schema）的工具 | 倉庫的裝修施工紀錄 |

---

## 二、SQLAlchemy

### 核心概念

```
Engine  →  連線到哪個資料庫（連線字串）
Session →  一次交易的範圍（像購物車，結帳才真正寫入）
Model   →  Python class ↔ 資料庫 Table 的對映
Query   →  db.query(User).filter(...) 就是 SELECT ... WHERE ...
```

### models.py — 定義資料表結構

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)
    contact_mail  = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    provider      = Column(String(20), default="local")   # local | google | line
    phone         = Column(String(20), unique=True, index=True, nullable=True)
    google_user_id= Column(String(100), unique=True, index=True, nullable=True)
    line_user_id  = Column(String(100), unique=True, index=True, nullable=True)
    role          = Column(String(20), default="customer") # customer | owner
    created_at    = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")
```

### database.py — 建立連線與 Session

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:yourpassword@localhost:5432/cales_breathe"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """依賴注入用：取得 DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 常見 CRUD 操作

```python
# 新增
db.add(User(name="Cale", contact_mail="cale@test.com"))
db.commit()

# 查詢
user = db.query(User).filter(User.contact_mail == "cale@test.com").first()

# 更新
user.name = "Cale Updated"
db.commit()

# 刪除
db.delete(user)
db.commit()
```

---

## 三、Alembic

### 為何需要 Alembic？

原本用 SQLite 時，需要手動寫 `_ensure_sqlite_columns()` 來補欄位：

```python
# ❌ 舊做法（不建議）：手動補欄位，沒有版本記錄
def _ensure_sqlite_columns():
    rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
    cols = {str(r[1]) for r in rows}
    if "google_user_id" not in cols:
        conn.execute(text("ALTER TABLE users ADD COLUMN google_user_id VARCHAR(100)"))
```

Alembic 的做法是：每次改 Schema 都產生一個有版本號的腳本，像 git commit 一樣。

### 版本腳本結構

```
alembic/
  versions/
    ├── 001_init_tables.py         ← 建立所有初始 table
    ├── 002_add_google_user_id.py  ← 加了 google_user_id 欄位
    └── 003_add_line_user_id.py    ← 加了 line_user_id 欄位
```

### Migration 腳本長這樣

```python
# alembic/versions/002_add_google_user_id.py（Alembic 自動產生）

def upgrade():
    op.add_column('users', sa.Column('google_user_id', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_users_google_user_id', 'users', ['google_user_id'])

def downgrade():  # 可以「回滾」
    op.drop_constraint('uq_users_google_user_id', 'users')
    op.drop_column('users', 'google_user_id')
```

---

## 四、完整開發流程

```
1. 修改 models.py（例如加了新欄位）
       ↓
2. alembic revision --autogenerate -m "add phone column"
   Alembic 自動比較 models.py 和現有 DB，產生差異腳本
       ↓
3. alembic upgrade head
   Alembic 執行腳本，透過 SQLAlchemy Engine 連到 PostgreSQL
   在真實的 DB 裡執行 ALTER TABLE
       ↓
4. FastAPI 啟動，SQLAlchemy Session 開始服務 API 請求
   所有查詢、新增、修改都透過 SQLAlchemy 送到 PostgreSQL
```

### 資料流向圖

```
FastAPI 路由 (main.py)
    │
    │ Depends(get_db)
    ▼
SQLAlchemy Session          ← 你操作的物件層
    │
    │ 自動翻譯成 SQL
    ▼
SQLAlchemy Engine           ← 管理連線池
    │
    │ psycopg2 driver
    ▼
PostgreSQL Server           ← 真實資料存在這裡
    │
    │ 資料表結構由誰管？
    ▼
Alembic                     ← 負責建表、改欄位、版本管理
```

---

## 五、SQLite vs PostgreSQL 對比

| 比較項目 | SQLite（舊） | PostgreSQL（新） |
|---|---|---|
| **並發寫入** | 同一時間只能一個寫入 | 支援真正的多連線並發寫入（MVCC） |
| **多執行緒** | 需要大量 workaround | 原生支援，無需額外設定 |
| **部署架構** | 只能單機，`.db` 是檔案 | 獨立服務，可遠端連線、可雲端部署 |
| **資料類型** | 有限 | 豐富（JSONB、Array、UUID、ENUM…） |
| **ALTER TABLE** | 幾乎不支援 | 完整支援 |
| **Schema 遷移** | 手動寫 SQL patch | Alembic 完整支援 |
| **生產環境** | 不建議 | 業界標準 |

---

## 六、指令速查

```bash
# 初始化 Alembic（只做一次）
alembic init alembic

# 根據 models.py 自動產生 migration 腳本
alembic revision --autogenerate -m "init all tables"

# 執行所有未執行的 migration（升級到最新）
alembic upgrade head

# 查看目前版本
alembic current

# 查看所有版本歷史
alembic history

# 回滾一個版本
alembic downgrade -1

# 回滾到最初始狀態
alembic downgrade base
```

---

## 七、部署方式選擇

| 方式 | 適合情境 | 說明 |
|---|---|---|
| **本機 Docker** | 開發環境 | `docker run -e POSTGRES_PASSWORD=xxx -p 5432:5432 postgres:16` |
| **本機安裝** | 開發環境 | 直接安裝 PostgreSQL 16 |
| **Supabase** | 小型生產 / 免費起步 | 雲端 PostgreSQL，有 Free tier |
| **Railway / Render** | 生產環境 | 部署 FastAPI + Postgres 一站搞定 |
| **AWS RDS / GCP Cloud SQL** | 大型生產 | 最穩定，但有費用 |

---

## 八、安裝依賴

`requirements.txt` 需要新增：

```
psycopg2-binary>=2.9.9   # PostgreSQL Python driver
alembic>=1.13.0          # Schema 遷移工具
```

---

## 一句話總結

> **PostgreSQL** 是倉庫，**SQLAlchemy** 是讓你用 Python 操作倉庫的管理員，**Alembic** 是負責記錄和執行倉庫裝修改建歷史的施工隊。
