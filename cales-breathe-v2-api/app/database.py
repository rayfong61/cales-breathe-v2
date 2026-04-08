"""資料庫設定：讀取 DATABASE_URL 環境變數，支援 SQLite（開發）與 PostgreSQL（正式）"""
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

DATABASE_URL = (os.environ.get("DATABASE_URL") or "sqlite:///./app.db").strip()

# 統一轉換為 postgresql+psycopg2://（SQLAlchemy 與 psycopg2 明確搭配）
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30.0},
        poolclass=NullPool,
    )
else:
    # Supabase pooler：
    # - Session mode（:5432）— QueuePool；適合長駐後端（Render）。
    # - Transaction mode（:6543）— NullPool，避免與 PgBouncer 雙層池互撞。
    _url = make_url(DATABASE_URL)
    _is_supabase_pooler = (_url.host or "").endswith(".pooler.supabase.com")
    _is_tx_pooler = _is_supabase_pooler and (_url.port == 6543)

    _pg_connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", "30"))
    _connect_args = {
        "connect_timeout": _pg_connect_timeout,
        "sslmode": "prefer",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

    if _is_tx_pooler:
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            connect_args=_connect_args,
        )
    else:
        _pool_size = int(os.environ.get("DB_POOL_SIZE", "10"))
        _max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "5"))
        _pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
        _pool_recycle = int(os.environ.get("DB_POOL_RECYCLE", "280"))
        engine = create_engine(
            DATABASE_URL,
            pool_size=_pool_size,
            max_overflow=_max_overflow,
            pool_timeout=_pool_timeout,
            pool_recycle=_pool_recycle,
            pool_pre_ping=True,
            pool_use_lifo=True,
            connect_args=_connect_args,
        )


@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, _connection_record):
    if not _is_sqlite:
        return
    cur = dbapi_conn.cursor()
    try:
        try:
            cur.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        cur.execute("PRAGMA busy_timeout=30000")
    finally:
        cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """依賴注入用：取得 DB session。pool_pre_ping=True 已自動處理死連線。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建立所有資料表"""
    from app.models import User, Service, Booking, LineWebhookEvent  # noqa: F401
    Base.metadata.create_all(bind=engine)
    if _is_sqlite:
        _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """對既有 SQLite 檔做最小欄位補齊（避免本機測試每次刪 DB）。"""
    with engine.begin() as conn:
        # users 表欄位補強
        user_rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        user_cols = {str(r[1]) for r in user_rows}
        if "google_user_id" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_user_id VARCHAR(100)"))
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_user_id ON users (google_user_id)")
        )

        # bookings 表欄位補強（guest_name, created_by_owner_id）
        booking_rows = conn.execute(text("PRAGMA table_info(bookings)")).fetchall()
        booking_cols = {str(r[1]) for r in booking_rows}
        if "guest_name" not in booking_cols:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN guest_name VARCHAR(100)"))
        if "guest_phone" not in booking_cols:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN guest_phone VARCHAR(20)"))
        if "created_by_owner_id" not in booking_cols:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN created_by_owner_id INTEGER"))
