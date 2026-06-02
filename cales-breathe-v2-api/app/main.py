"""FastAPI 最小 MVP"""
from dotenv import load_dotenv

load_dotenv()  # 必須在所有 app.* import 之前，確保 DATABASE_URL 等環境變數已載入

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta, timezone
from collections import Counter #用來統計「各元素出現次數」。
from pathlib import Path
import base64
import hashlib
import hmac
import json
import mimetypes
import os
from uuid import uuid4

import redis

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from passlib.context import CryptContext

from app.database import get_db, init_db, SessionLocal
from app.models import User, Service, Booking, LineWebhookEvent, booking_services
from app import google_calendar as gcal
from app.auth_session import (
    access_cookie_name,
    clear_session_cookies,
    create_access_token,
    decode_access_token,
    issue_auth_session,
    refresh_cookie_name,
    refresh_session,
    resolve_user_for_logout,
    revoke_all_refresh_for_user,
)
from app.schemas import (
    ServiceRead,
    UserRead,
    BookingCreate,
    BookingRead,
    LegacyLoginRequest,
    LegacyLoginResponse,
    LegacyRegisterRequest,
    LegacyAccountUpdate2Request,
    LegacyUnavailableTimeRange,
    LegacyOrderRead,
    LegacyOrderDetail,
)

from app.oauth import create_oauth_router
from app.docs_access import add_docs_basic_auth_middleware, docs_fastapi_kwargs
from app.rate_limiter import RateLimiter
from app.rate_limit_decorators import rate_limit_login

# 分類顯示順序（對應選單）
CATEGORY_ORDER = [
    "臉部", "私密處", "手臂", "胸部", "腿部",
    "背部", "腹部", "臀部", "手指", "腳趾",
    # 加購（排最後即可）
    "addon-armpit", "addon-lip", "addon-fingers", "addon-toes",
]

# 種子資料：依實際選單
SEED_SERVICES = [
    # 臉部 (4選1)
    {"name": "眉毛", "category": "臉部", "price": 600, "duration_minutes": 30, "sort_order": 1},
    {"name": "上唇", "category": "臉部", "price": 400, "duration_minutes": 15, "sort_order": 2},
    {"name": "眉毛 + 上唇", "category": "臉部", "price": 1000, "duration_minutes": 45, "sort_order": 3},
    {"name": "全臉", "category": "臉部", "price": 1600, "duration_minutes": 60, "sort_order": 4},
    # 私密處 (5選1)
    {"name": "巴西式全除VIO", "category": "私密處", "price": 2200, "duration_minutes": 40, "sort_order": 1},
    {"name": "巴西式全除VIO + 敷膜", "category": "私密處", "price": 2599, "duration_minutes": 55, "sort_order": 2},
    {"name": "比基尼線", "category": "私密處", "price": 2000, "duration_minutes": 20, "sort_order": 3},
    {"name": "比基尼線 + 敷膜", "category": "私密處", "price": 2399, "duration_minutes": 35, "sort_order": 4},
    {"name": "質感在身邊", "category": "私密處", "price": 2800, "duration_minutes": 90, "sort_order": 5},
    # 手臂 (4選1)
    {"name": "腋下", "category": "手臂", "price": 700, "duration_minutes": 15, "sort_order": 1},
    {"name": "前手臂", "category": "手臂", "price": 1000, "duration_minutes": 40, "sort_order": 2},
    {"name": "腋下 + 前手臂", "category": "手臂", "price": 1700, "duration_minutes": 45, "sort_order": 3},
    {"name": "全手", "category": "手臂", "price": 1800, "duration_minutes": 60, "sort_order": 4},
    # 胸部 (2選1)
    {"name": "胸部", "category": "胸部", "price": 900, "duration_minutes": 30, "sort_order": 1},
    {"name": "乳暈", "category": "胸部", "price": 600, "duration_minutes": 15, "sort_order": 2},
    # 腿部 (2選1)
    {"name": "小腿", "category": "腿部", "price": 1500, "duration_minutes": 30, "sort_order": 1},
    {"name": "全腿", "category": "腿部", "price": 2500, "duration_minutes": 60, "sort_order": 2},
    # 背部、腹部、臀部、手指、腳趾
    {"name": "背部除毛", "category": "背部", "price": 1500, "duration_minutes": 40, "sort_order": 1},
    {"name": "腹部除毛", "category": "腹部", "price": 1000, "duration_minutes": 30, "sort_order": 1},
    {"name": "臀部除毛", "category": "臀部", "price": 900, "duration_minutes": 30, "sort_order": 1},
    {"name": "手指除毛", "category": "手指", "price": 400, "duration_minutes": 10, "sort_order": 1},
    {"name": "腳趾除毛", "category": "腳趾", "price": 400, "duration_minutes": 10, "sort_order": 1},

    # 加購（避免與主項目 category 衝突：各自獨立 category）
    {"name": "腋下加購", "category": "addon-armpit", "price": 499, "duration_minutes": 15, "sort_order": 1},
    {"name": "上唇加購", "category": "addon-lip", "price": 200, "duration_minutes": 15, "sort_order": 1},
    {"name": "手指加購", "category": "addon-fingers", "price": 200, "duration_minutes": 10, "sort_order": 1},
    {"name": "腳趾加購", "category": "addon-toes", "price": 200, "duration_minutes": 10, "sort_order": 1},
]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 測試／舊程式碼相容：access cookie 名稱（實際讀取見 app.auth_session.access_cookie_name）
JWT_COOKIE_NAME = access_cookie_name()


def _create_access_token(user_id: int) -> str:
    """與舊測試相容的別名。"""
    return create_access_token(user_id)


def _decode_access_token(token: str) -> int:
    return decode_access_token(token)


def _perform_logout(request: Request, response: Response, db: Session) -> None:
    uid = resolve_user_for_logout(
        db,
        request.cookies.get(access_cookie_name()),
        request.cookies.get(refresh_cookie_name()),
    )
    if uid is not None:
        revoke_all_refresh_for_user(db, uid)
    clear_session_cookies(response)


def _legacy_user_shape(user: User) -> dict:
    return {
        "id": user.id,
        "client_name": user.name,
        "contact_mobile": user.phone,
        "contact_mail": user.contact_mail,
        "provider": user.provider,
        "photo": user.photo,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "address": user.address,
        "role": user.role,
    }


def _is_keep_alive_enabled() -> bool:
    return os.getenv("ENABLE_KEEP_ALIVE", "").strip().lower() in ("1", "true", "yes")


async def _keep_alive_loop():
    """每 10 分鐘 ping 自己的 /health（僅 ENABLE_KEEP_ALIVE=true 時啟動；Cloud Run 預設關閉）。"""
    api_base = os.getenv("API_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not api_base:
        print("[keep_alive] API_PUBLIC_BASE_URL 未設定，略過自動 ping")
        return
    url = f"{api_base}/health"
    await asyncio.sleep(60)  # 啟動後等 60 秒再開始
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url)
                print(f"[keep_alive] ping {url} → {r.status_code}")
        except Exception as e:
            print(f"[keep_alive] ping 失敗：{e}")
        await asyncio.sleep(600)  # 每 10 分鐘


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動時建立資料表與種子資料（DB 失敗不中斷啟動，避免 Render 找不到 port）"""
    try:
        init_db()
        db = SessionLocal()
        try:
            if db.query(Service).count() == 0:
                for s in SEED_SERVICES:
                    db.add(Service(**s))
                db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[lifespan] DB 初始化失敗，服務仍繼續啟動：{e}")

    # 初始化 Redis / RateLimiter（若 REDIS_URL 未設定則略過，採 fail-open）
    redis_url = os.getenv("REDIS_URL", "").strip()
    app.state.login_rate_limiter = None
    if redis_url:
        try:
            redis_client = redis.Redis.from_url(redis_url)
            bucket_capacity = int(os.getenv("LOGIN_RATE_LIMIT_BUCKET_CAPACITY", "5"))
            fill_rate_per_sec = float(os.getenv("LOGIN_RATE_LIMIT_FILL_RATE_PER_SEC", "0.0333"))
            app.state.login_rate_limiter = RateLimiter(
                redis_client=redis_client,
                bucket_capacity=bucket_capacity,
                fill_rate_per_sec=fill_rate_per_sec,
                key_prefix="rate",
            )
            print(
                f"[lifespan] Login RateLimiter 啟用：bucket_capacity={bucket_capacity}, "
                f"fill_rate_per_sec={fill_rate_per_sec}, redis_url={redis_url}"
            )
        except Exception as e:
            # Redis 錯誤不應阻止服務啟動；限流會自動 fail-open。
            print(f"[lifespan] 初始化 Redis/RateLimiter 失敗，登入限流停用：{e}")

    keep_alive_task = None
    if _is_keep_alive_enabled():
        keep_alive_task = asyncio.create_task(_keep_alive_loop())
        print("[lifespan] ENABLE_KEEP_ALIVE=true，已啟動每 10 分鐘 /health ping")
    else:
        print("[lifespan] 未啟用 ENABLE_KEEP_ALIVE，略過容器內定期 ping")
    yield
    if keep_alive_task is not None:
        keep_alive_task.cancel()
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass


# Docker gateway 會把外部路徑 `/api/*` 反代到後端 FastAPI 的根路徑。
# 設定 root_path 讓 OpenAPI/Swagger 產生的 servers/base URL 正確帶上 `/api`，
# 例如 Swagger UI 的 Execute 會呼叫 `/api/services` 而不是 `/services`。
app = FastAPI(
    title="Cale's Breathe API",
    version="0.1.0",
    lifespan=lifespan,
    root_path="/api",
    **docs_fastapi_kwargs(),
)

def _allowed_origins() -> list[str]:
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # 正式環境由 FRONTEND_PUBLIC_ORIGIN 控制；支援單一或逗號分隔多個 origin。
    extra = os.getenv("FRONTEND_PUBLIC_ORIGIN", "").strip()
    if extra:
        for origin in (x.strip().rstrip("/") for x in extra.split(",")):
            if origin and origin not in origins:
                origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_docs_basic_auth_middleware(app)

app.include_router(
    create_oauth_router(issue_auth_session),
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def _storage_backend() -> str:
    return os.getenv("STORAGE_BACKEND", "local").strip().lower()


def _upload_photo_and_get_url(content: bytes, suffix: str) -> str:
    backend = _storage_backend()
    filename = f"{uuid4().hex}{suffix}"

    if backend == "r2":
        # 延遲 import，避免 local 模式也需要安裝 boto3 才能啟動。
        try:
            import boto3
        except Exception as exc:
            raise HTTPException(500, "R2 模式需要先安裝 boto3") from exc

        account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
        access_key = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        bucket = os.getenv("R2_BUCKET", "").strip()
        key_prefix = os.getenv("R2_KEY_PREFIX", "uploads").strip().strip("/")
        public_base = os.getenv("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")

        if not all([account_id, access_key, secret_key, bucket, public_base]):
            raise HTTPException(
                500,
                "R2 設定不完整（需 R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET/R2_PUBLIC_BASE_URL）",
            )

        key = f"{key_prefix}/{filename}" if key_prefix else filename
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

        try:
            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except Exception as exc:
            raise HTTPException(502, "R2 上傳失敗，請稍後再試") from exc

        return f"{public_base}/{key}"

    target = UPLOAD_DIR / filename
    target.write_bytes(content)
    return f"/uploads/{filename}"


def _category_sort_key(category: str) -> int:
    # 用 CATEGORY_ORDER 的位置來當作排序權重（搭配 list_services 的 services.sort）。
    # 找不到的 category 代表是「未知分類」，回傳 99 讓它通常排在最後。
    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return 99


def _verify_line_signature(raw_body: bytes, signature: str | None) -> None:
    secret = os.getenv("LINE_CHANNEL_SECRET", "")
    if not secret:
        raise HTTPException(500, "缺少 LINE_CHANNEL_SECRET 設定")
    if not signature:
        raise HTTPException(401, "缺少 LINE 簽章")

    expected_signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")
    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(401, "LINE 簽章驗證失敗")


async def _reply_text_to_line(
    access_token: str,
    reply_token: str,
    text: str,
) -> None:
    """呼叫 LINE Reply API 回覆文字訊息。"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


async def _push_text_to_line(access_token: str, user_id: str, text: str) -> None:
    """呼叫 LINE Push API 主動推播文字訊息（非同步）。"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


def _reply_text_to_line_sync(
    access_token: str,
    reply_token: str,
    text: str,
) -> None:
    """呼叫 LINE Reply API 回覆文字訊息（同步，供背景任務使用）。"""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


def _push_text_to_line_sync(access_token: str, user_id: str, text: str) -> None:
    """呼叫 LINE Push API 主動推播文字訊息（同步，用於 sync route handler）。"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        if not resp.is_success:
            print(f"[LINE Push] 失敗 status={resp.status_code} body={resp.text}")
        resp.raise_for_status()


def _bg_line_push_safe(access_token: str, user_id: str, text: str) -> None:
    """背景 LINE Push：失敗只 log，不拋出。"""
    try:
        _push_text_to_line_sync(access_token, user_id, text)
    except Exception as exc:
        print(f"[bg] LINE Push 失敗：{exc}")


def _bg_after_booking_created_calendar_and_line(booking_id: int, customer_user_id: int) -> None:
    """建立預約後背景：Google Calendar（待確認）+ 寫回 event_id + LINE 通知業主。"""
    with SessionLocal() as db:
        booking = (
            db.query(Booking)
            .options(joinedload(Booking.services))
            .filter(Booking.id == booking_id)
            .first()
        )
        customer = db.query(User).filter(User.id == customer_user_id).first()
        if not booking or not customer:
            return
        owner_line_id = os.getenv("OWNER_LINE_USER_ID", "").strip()
        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        if owner_line_id and access_token:
            try:
                _push_text_to_line_sync(
                    access_token,
                    owner_line_id,
                    _new_booking_owner_text(booking, customer),
                )
            except Exception as exc:
                print(f"[bg create_booking] LINE 業主通知失敗：{exc}")
        try:
            event_id = gcal.create_event(booking, customer, status="pending")
            if event_id:
                booking.google_calendar_event_id = event_id
                db.commit()
        except Exception as exc:
            print(f"[bg create_booking] Google Calendar 建立失敗：{exc}")


def _bg_sync_confirm_booking_google_calendar(booking_id: int) -> None:
    """確認預約後背景：更新或建立 Google Calendar 事件（已確認）。"""
    with SessionLocal() as db:
        b = (
            db.query(Booking)
            .options(joinedload(Booking.services))
            .filter(Booking.id == booking_id)
            .first()
        )
        if not b or b.status != "confirmed":
            return
        customer = (
            db.query(User).filter(User.id == b.user_id).first() if b.user_id else None
        )
        if customer is None and not (b.guest_name or "").strip():
            return
        try:
            if b.google_calendar_event_id:
                gcal.update_event_status(b.google_calendar_event_id, b, customer, "confirmed")
            else:
                event_id = gcal.create_event(b, customer, status="confirmed")
                if event_id:
                    b.google_calendar_event_id = event_id
                    db.commit()
        except Exception as exc:
            print(f"[bg confirm_booking] Google Calendar 更新失敗：{exc}")


def _bg_sync_complete_booking_google_calendar(booking_id: int) -> None:
    """標記完成後背景：Google Calendar 事件改為已完成。"""
    with SessionLocal() as db:
        b = (
            db.query(Booking)
            .options(joinedload(Booking.services))
            .filter(Booking.id == booking_id)
            .first()
        )
        if not b or b.status != "completed":
            return
        customer = (
            db.query(User).filter(User.id == b.user_id).first() if b.user_id else None
        )
        if customer is None and not (b.guest_name or "").strip():
            return
        try:
            gcal.update_event_status(b.google_calendar_event_id, b, customer, "completed")
        except Exception as exc:
            print(f"[bg complete_booking] Google Calendar 更新失敗：{exc}")


def _bg_delete_google_calendar_event(cal_event_id: str | None) -> None:
    """背景刪除行事曆事件（取消預約）。"""
    try:
        gcal.delete_event(cal_event_id or "")
    except Exception as exc:
        print(f"[bg cancel_booking] Google Calendar 刪除失敗：{exc}")


def _new_booking_owner_text(b: "Booking", customer: "User") -> str:
    """新預約待審核通知（傳給業主）。"""
    date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
    service_names = "、".join(s.name for s in b.services)
    notes_line = f"備註：{b.notes}\n" if b.notes else ""
    phone_line = f"電話：{customer.phone}\n" if customer.phone else ""
    return (
        f"【新預約待審核】\n"
        f"預約編號：#{b.id}\n"
        f"客人：{customer.name}\n"
        f"{phone_line}"
        f"日期時間：{date_str}\n"
        f"服務項目：{service_names}\n"
        f"總費用：${b.total_price}\n"
        f"{notes_line}\n"
        f"回覆「確認 {b.id}」確認\n"
        f"回覆「取消 {b.id}」取消"
    )


def _booking_confirmed_text(b: "Booking") -> str:
    """預約確認通知（傳給客人）。"""
    date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
    service_names = "、".join(s.name for s in b.services)
    notes_line = f"備註：{b.notes}\n" if b.notes else ""
    return (
        f"您的預約已確認！\n"
        f"預約編號：#{b.id}\n"
        f"日期時間：{date_str}\n"
        f"服務項目：{service_names}\n"
        f"總費用：${b.total_price}\n"
        f"{notes_line}\n"
        f"期待為您服務！"
    )


def _booking_rejected_text(b: "Booking") -> str:
    """預約拒絕/取消通知（傳給客人）。"""
    date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
    return (
        f"很抱歉，您的預約已取消。\n"
        f"預約編號：#{b.id}\n"
        f"日期時間：{date_str}\n\n"
        f"如有疑問，請聯繫店家。"
    )


def _customer_cancelled_owner_text(b: "Booking", customer: "User") -> str:
    """客人取消預約通知（傳給業主）。"""
    date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
    service_names = "、".join(s.name for s in b.services)
    phone_line = f"電話：{customer.phone}\n" if customer.phone else ""
    return (
        f"【預約已取消】\n"
        f"預約編號：#{b.id}\n"
        f"客人：{customer.name}\n"
        f"{phone_line}"
        f"日期時間：{date_str}\n"
        f"服務項目：{service_names}\n"
        f"總費用：${b.total_price}"
    )


def _booking_completed_text(b: "Booking") -> str:
    """預約完成通知（傳給客人）。"""
    date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
    service_names = "、".join(s.name for s in b.services)
    return (
        f"感謝您的光臨！\n"
        f"預約編號：#{b.id}\n"
        f"日期時間：{date_str}\n"
        f"服務項目：{service_names}\n\n"
        f"期待下次再為您服務 ✨"
    )


def _help_text() -> str:
    return (
        "可用指令：\n"
        "- help：顯示指令說明\n"
        "- 服務：列出可預約服務（含 id）\n"
        "\n"
        "【業主專用】\n"
        "- 確認{編號}：確認預約並通知客人\n"
        "- 取消{編號}：取消預約並通知客人\n"
        "- 完成{編號}：標記預約已完成並通知客人\n"
        "\n"
        "範例：確認17、取消17、完成17"
    )


def _format_services_text(services: list[Service]) -> str:
    # 依分類排序（CATEGORY_ORDER 未出現的分類排最後）
    services_sorted = sorted(
        services,
        key=lambda s: (_category_sort_key(s.category), s.sort_order, s.id),
    )

    lines: list[str] = ["服務清單（輸入時可用服務 id）："]
    current_category: str | None = None
    for s in services_sorted:
        if s.category != current_category:
            current_category = s.category
            lines.append(f"\n【{current_category}】")
        lines.append(f"- {s.id}. {s.name}（{s.duration_minutes} 分，${s.price}）")

    text = "\n".join(lines).strip()
    # LINE text message 長度限制（官方為 5000）；保守裁切避免送出失敗。
    return text[:4900]


def _handle_owner_confirm_sync(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
) -> tuple[str, int | None, str | None, str | None]:
    """Webhook 業主「確認 {id}」指令處理（同步背景版本）。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作", None, None, None
    raw_id = cmd.removeprefix("確認").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：確認 {預約編號}", None, None, None
    booking_id = int(raw_id)
    customer_line: str | None = None
    push_copy: str | None = None
    summary = ""
    try:
        with SessionLocal() as db:
            b = _do_confirm_booking(booking_id, db)
            cust = db.query(User).filter(User.id == b.user_id).first()
            if cust and cust.line_user_id:
                customer_line = cust.line_user_id
            push_copy = _booking_confirmed_text(b)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已確認，同步進行中。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}", None, None, None

    return summary, booking_id, customer_line, push_copy


def _handle_owner_cancel_sync(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
) -> tuple[str, str | None, str | None, str | None]:
    """Webhook 業主「取消{id}」或「拒絕{id}」指令處理（同步背景版本）。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作", None, None, None
    raw_id = cmd.removeprefix("取消").removeprefix("拒絕").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：取消 {預約編號}", None, None, None
    booking_id = int(raw_id)
    customer_line: str | None = None
    push_copy: str | None = None
    summary = ""
    cal_ev: str | None = None
    try:
        with SessionLocal() as db:
            b, cal_ev = _do_cancel_booking(booking_id, db)
            cust = db.query(User).filter(User.id == b.user_id).first()
            if cust and cust.line_user_id:
                customer_line = cust.line_user_id
            push_copy = _booking_rejected_text(b)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已取消，同步進行中。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}", None, None, None

    return summary, customer_line, push_copy, cal_ev


def _handle_owner_complete_sync(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
) -> tuple[str, int | None]:
    """Webhook 業主「完成{id}」指令處理（同步背景版本）。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作", None
    raw_id = cmd.removeprefix("完成").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：完成 {預約編號}", None
    booking_id = int(raw_id)
    try:
        with SessionLocal() as db:
            b = _do_complete_booking(booking_id, db)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已標記完成，同步進行中。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}", None

    return summary, booking_id


def _process_line_webhook_event(event: dict, access_token: str) -> None:
    """背景處理單一 LINE webhook event，避免在 request path 做外部 I/O。"""
    event_id = event.get("webhookEventId")
    if not event_id:
        return

    event_type = event.get("type")
    reply_token = event.get("replyToken")
    message_type = (event.get("message") or {}).get("type")
    message_text = (event.get("message") or {}).get("text")
    preview_text = (message_text or "")[:200]
    source_uid = (event.get("source") or {}).get("userId", "")
    print(
        f"[line_webhook] event.type={event_type} webhookEventId={event_id} "
        f"replyToken_present={bool(reply_token)} message.type={message_type} "
        f"message.text_preview={preview_text} source.userId={source_uid}"
    )

    if not (event_type == "message" and message_type == "text" and reply_token):
        return

    cmd = (message_text or "").strip()
    owner_line_id = os.getenv("OWNER_LINE_USER_ID", "").strip()
    post_confirm_booking_id: int | None = None
    post_confirm_customer_line: str | None = None
    post_confirm_push_copy: str | None = None
    post_cancel_cal_ev: str | None = None
    post_cancel_customer_line: str | None = None
    post_cancel_push_copy: str | None = None
    post_complete_booking_id: int | None = None

    if cmd.lower() == "help":
        reply_text = _help_text()
    elif cmd == "服務":
        with SessionLocal() as db_svc:
            services = db_svc.query(Service).all()
            reply_text = _format_services_text(services)
    elif cmd.startswith("確認"):
        (
            reply_text,
            post_confirm_booking_id,
            post_confirm_customer_line,
            post_confirm_push_copy,
        ) = _handle_owner_confirm_sync(cmd, source_uid, owner_line_id, access_token)
    elif cmd.startswith("取消") or cmd.startswith("拒絕"):
        (
            reply_text,
            post_cancel_customer_line,
            post_cancel_push_copy,
            post_cancel_cal_ev,
        ) = _handle_owner_cancel_sync(cmd, source_uid, owner_line_id, access_token)
    elif cmd.startswith("完成"):
        reply_text, post_complete_booking_id = _handle_owner_complete_sync(cmd, source_uid, owner_line_id)
    else:
        reply_text = f"收到：{cmd}\n\n（輸入 help 查看可用指令）"

    try:
        _reply_text_to_line_sync(
            access_token=access_token,
            reply_token=reply_token,
            text=reply_text,
        )
    except Exception as exc:
        print(f"[line_webhook] reply 失敗 event_id={event_id}: {exc}")

    # 回覆業主後再做較慢的同步，提升聊天體感。
    if post_confirm_customer_line and access_token and post_confirm_push_copy:
        _bg_line_push_safe(access_token, post_confirm_customer_line, post_confirm_push_copy)
    if post_confirm_booking_id is not None:
        _bg_sync_confirm_booking_google_calendar(post_confirm_booking_id)

    if post_cancel_customer_line and access_token and post_cancel_push_copy:
        _bg_line_push_safe(access_token, post_cancel_customer_line, post_cancel_push_copy)
    if post_cancel_cal_ev:
        _bg_delete_google_calendar_event(post_cancel_cal_ev)

    if post_complete_booking_id is not None:
        _bg_sync_complete_booking_google_calendar(post_complete_booking_id)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """健康檢查（含 DB ping）。定期保活請用外部排程，勿依賴容器內 keep-alive。"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "db": db_status}


@app.post("/line/webhook")
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str | None = Header(default=None),
):
    """LINE Webhook：不可在單一 ORM Session 上跨 await 佔用連線（會塞滿小連線池）。"""
    raw_body = await request.body()
    _verify_line_signature(raw_body, x_line_signature)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "LINE payload 格式錯誤") from exc

    events = payload.get("events", [])
    print(f"[line_webhook] events_count={len(events)}")

    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not access_token:
        # 目前 webhook 會對文字訊息做 reply，因此沒 token 就直接回錯誤，避免「驗簽成功但不回覆」。
        raise HTTPException(500, "缺少 LINE_CHANNEL_ACCESS_TOKEN 設定")

    processed = 0
    duplicated = 0
    for event in events:
        event_id = event.get("webhookEventId")
        if not event_id:
            continue
        try:
            # 先入庫去重，再將實際處理排到背景，讓 webhook 儘速回 200。
            with SessionLocal() as db_ins:
                db_ins.add(LineWebhookEvent(event_id=event_id))
                db_ins.commit()
        except IntegrityError:
            duplicated += 1
            continue
        background_tasks.add_task(_process_line_webhook_event, event, access_token)
        processed += 1

    return {"status": "ok", "processed": processed, "duplicated": duplicated}


@app.get("/services", response_model=list[ServiceRead])
def list_services(db: Session = Depends(get_db)):
    """列出所有服務項目（依選單分類順序）"""
    services = db.query(Service).all()
    services.sort(key=lambda s: (_category_sort_key(s.category), s.sort_order))
    return services


@app.get("/services/by-category")
def list_services_by_category(db: Session = Depends(get_db)):
    """依分類分組列出服務（給 LINE Bot / 前端選單用）"""
    services = db.query(Service).order_by(Service.category, Service.sort_order).all()
    grouped = {}
    for s in services:
        if s.category not in grouped:
            grouped[s.category] = []
        grouped[s.category].append(ServiceRead.model_validate(s))
    # 依 CATEGORY_ORDER 排序
    return {k: grouped[k] for k in CATEGORY_ORDER if k in grouped}


# ----------------------------
# Legacy/BFF adaptor endpoints
# ----------------------------


def _get_current_user_from_cookie(request: Request, db: Session) -> User:
    token = request.cookies.get(access_cookie_name())
    if not token:
        raise HTTPException(401, "請先登入")
    user_id = _decode_access_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "請先登入")
    return user


@app.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user_from_cookie(request, db)
    return {"user": _legacy_user_shape(user)}


@app.post("/login", response_model=LegacyLoginResponse)
@rate_limit_login
def legacy_login(
    payload: LegacyLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.contact_mail == payload.contact_mail)
        .first()
    )
    if not user or not user.password_hash:
        raise HTTPException(401, "找不到帳號")
    if not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(401, "密碼錯誤")

    issue_auth_session(db, response, user.id)
    return LegacyLoginResponse(message="登入成功", user=_legacy_user_shape(user))


@app.post("/register", response_model=LegacyLoginResponse)
def legacy_register(payload: LegacyRegisterRequest, response: Response, db: Session = Depends(get_db)):
    # 舊前端會希望註冊後直接登入
    email = payload.contact_mail.strip().lower()
    if not email:
        raise HTTPException(400, "Email 為必填")
    if db.query(User).filter(User.contact_mail == email).first():
        raise HTTPException(400, "此 Email 已被註冊")

    user = User(
        name=payload.client_name.strip() or "New User",
        contact_mail=email,
        password_hash=pwd_context.hash(payload.password),
        provider="local",
        role="customer",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "註冊失敗，請稍後再試")
    db.refresh(user)

    issue_auth_session(db, response, user.id)
    return LegacyLoginResponse(message="註冊並登入成功", user=_legacy_user_shape(user))


@app.post("/auth/refresh")
def auth_refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(refresh_cookie_name())
    if not raw:
        clear_session_cookies(response)
        raise HTTPException(401, "請重新登入")
    refresh_session(db, response, raw)
    return {"message": "ok"}


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _perform_logout(request, response, db)
    return {"message": "登出成功"}


@app.get("/logout")
def legacy_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _perform_logout(request, response, db)
    return {"message": "登出成功"}


@app.delete("/account")
def legacy_delete_account(request: Request, response: Response, db: Session = Depends(get_db)):
    """刪除目前登入會員帳號（含其預約）並清除登入 cookie。"""
    user = _get_current_user_from_cookie(request, db)
    # 預約–服務多對多列必須先刪，否則外鍵會阻擋刪除 bookings（PostgreSQL 等）。
    booking_ids = [bid for (bid,) in db.query(Booking.id).filter(Booking.user_id == user.id).all()]
    if booking_ids:
        db.execute(delete(booking_services).where(booking_services.c.booking_id.in_(booking_ids)))
    db.query(Booking).filter(Booking.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    clear_session_cookies(response)
    return {"message": "帳號已刪除"}


@app.put("/account/update2")
def legacy_account_update2(
    payload: LegacyAccountUpdate2Request,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user_from_cookie(request, db)
    mobile = payload.contact_mobile.strip()
    if not mobile:
        raise HTTPException(400, "手機為必填")

    user.name = payload.client_name.strip() or user.name
    user.phone = mobile
    db.commit()
    db.refresh(user)
    return {"updatedUser": _legacy_user_shape(user)}


@app.put("/account/update")
async def legacy_account_update(
    request: Request,
    client_name: str | None = Form(None),
    contact_mobile: str | None = Form(None),
    contact_mail: str | None = Form(None),
    birthday: str | None = Form(None),
    address: str | None = Form(None),
    photo: UploadFile | None = File(None),
):
    """舊前端 Account 編輯入口（multipart）。await／上傳完成後再以 SessionLocal 寫入，避免長握 DB 連線。"""
    photo_payload: tuple[bytes, str] | None = None
    if photo is not None:
        suffix = Path(photo.filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            raise HTTPException(400, "僅支援 jpg/jpeg/png/gif/webp")
        content = await photo.read()
        photo_payload = (content, suffix)

    new_photo_url: str | None = None
    if photo_payload is not None:
        content, suffix = photo_payload
        new_photo_url = _upload_photo_and_get_url(content, suffix)

    with SessionLocal() as db:
        user = _get_current_user_from_cookie(request, db)

        if client_name is not None:
            user.name = client_name.strip() or user.name

        if contact_mobile is not None:
            mobile = contact_mobile.strip()
            if mobile:
                user.phone = mobile
            else:
                user.phone = None

        # 安全策略：僅 LINE 帳號允許在此入口設定/變更 email。
        # 其他 provider 即使直接呼叫 API 夾帶 contact_mail 也會被忽略。
        if contact_mail is not None and user.provider == "line":
            email = contact_mail.strip().lower()
            if email:
                existing = (
                    db.query(User)
                    .filter(User.contact_mail == email, User.id != user.id)
                    .first()
                )
                if existing:
                    raise HTTPException(409, "Email 已存在")
                user.contact_mail = email

        if birthday is not None:
            b = birthday.strip()
            if b:
                try:
                    user.birthday = date.fromisoformat(b)
                except ValueError as exc:
                    raise HTTPException(400, "生日格式錯誤，請使用 YYYY-MM-DD") from exc
            else:
                user.birthday = None

        if address is not None:
            user.address = address.strip() or None

        if new_photo_url is not None:
            user.photo = new_photo_url

        db.commit()
        db.refresh(user)
        return {"updatedUser": _legacy_user_shape(user)}


def _parse_legacy_date_time(booking_date: str, booking_time: str) -> datetime:
    # booking_date: YYYY-MM-DD
    # booking_time: HH:MM (前端) 或 HH:MM:SS
    t = booking_time.strip()
    if len(t) == 5:
        t = f"{t}:00"
    try:
        return datetime.fromisoformat(f"{booking_date}T{t}")
    except ValueError as exc:
        raise HTTPException(400, "日期或時間格式錯誤") from exc


def _service_ids_from_legacy_detail(db: Session, services: list[str], addons: list[str]) -> list[int]:
    names = [s.strip() for s in services if s and s.strip()] + [a.strip() for a in addons if a and a.strip()]
    if not names:
        raise HTTPException(400, "至少需選擇一項服務")

    rows = db.query(Service).filter(Service.name.in_(names)).all()
    found = {r.name: r.id for r in rows}
    missing = [n for n in names if n not in found]
    if missing:
        raise HTTPException(404, f"部分服務不存在: {', '.join(missing)}")
    # booking_services 為 (booking_id, service_id) 複合唯一鍵；需去重避免重複插入。
    unique_ids: list[int] = []
    seen: set[int] = set()
    for n in names:
        sid = found[n]
        if sid in seen:
            continue
        seen.add(sid)
        unique_ids.append(sid)
    return unique_ids


@app.get("/unavailable-times", response_model=list[LegacyUnavailableTimeRange])
def legacy_unavailable_times(date: str = Query(...), db: Session = Depends(get_db)):
    # 回舊前端需要的 HH:MM:SS 字串
    try:
        d = date  # YYYY-MM-DD（直接當字串使用）
        start = datetime.fromisoformat(f"{d}T00:00:00")
    except ValueError as exc:
        raise HTTPException(400, "date 格式錯誤") from exc
    end = start + timedelta(days=1)

    bookings = (
        db.query(Booking)
        .filter(
            Booking.status.in_(["pending", "confirmed"]),
            Booking.booking_date >= start,
            Booking.booking_date < end,
        )
        .all()
    )
    ranges = []
    for b in bookings:
        b_end = b.booking_date + timedelta(minutes=b.total_duration_minutes)
        ranges.append(
            {
                "start_time": b.booking_date.time().strftime("%H:%M:%S"),
                "end_time": b_end.time().strftime("%H:%M:%S"),
            }
        )
    return ranges


@app.get("/unavailable-dates")
def legacy_unavailable_dates(db: Session = Depends(get_db)):
    # 以「可預約時段是否全滿」判斷客滿日期，並忽略過去日期。
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    active = (
        db.query(Booking)
        .filter(
            Booking.status.in_(["pending", "confirmed"]),
            Booking.booking_date >= today_start,
        )
        .all()
    )

    by_day: dict[str, list[Booking]] = {}
    for b in active:
        by_day.setdefault(b.booking_date.date().isoformat(), []).append(b)

    full_days: list[str] = []
    for day_str, bookings in by_day.items():
        day = datetime.fromisoformat(f"{day_str}T00:00:00")
        slot_starts = [day.replace(hour=h, minute=0, second=0, microsecond=0) for h in range(9, 18)]

        # 今天只允許挑選「現在之後」的時段。
        if day.date() == now.date():
            slot_starts = [slot for slot in slot_starts if slot > now]
            if not slot_starts:
                full_days.append(day_str)
                continue

        has_available = False
        for slot_start in slot_starts:
            slot_end = slot_start + timedelta(hours=1)
            overlapped = any(
                slot_start < (b.booking_date + timedelta(minutes=b.total_duration_minutes))
                and b.booking_date < slot_end
                for b in bookings
            )
            if not overlapped:
                has_available = True
                break
        if not has_available:
            full_days.append(day_str)

    return full_days


def _legacy_order_from_booking(booking: Booking, services: list[Service], customer: User | None = None) -> dict:
    # 以 v2 status 作為來源
    booking_date_str = booking.booking_date.date().isoformat()
    booking_time_str = booking.booking_date.time().strftime("%H:%M:%S")

    # services/addons 以「中文名稱字串」回傳
    service_names = [s.name for s in services if not s.category.startswith("addon-")]
    addon_names = [s.name for s in services if s.category.startswith("addon-")]

    data = {
        "id": booking.id,
        "booking_date": booking_date_str,
        "booking_time": booking_time_str,
        "total_price": booking.total_price,
        "total_duration": booking.total_duration_minutes,
        "booking_note": booking.notes,
        "is_cancelled": booking.status == "cancelled",
        "status": booking.status,
        "booking_detail": {
            "services": service_names,
            "addons": addon_names,
        },
    }
    # 代客/訪客資訊（若有）
    data["guest_name"] = booking.guest_name
    data["created_by_owner_id"] = booking.created_by_owner_id
    data["customer_id"] = customer.id if customer else None
    data["customer_name"] = customer.name if customer else booking.guest_name
    data["customer_photo"] = customer.photo if customer else None
    data["customer_phone"] = customer.phone if customer else booking.guest_phone
    return data


@app.post("/orders")
def legacy_create_order(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    舊前端建立預約入口。
    - 驗證登入：JWT cookie
    - 取 booking_date + booking_time 組 datetime
    - 取 booking_detail（JSON 字串）拆 services/addons 中文名稱
    - 映射成 v2 service_ids 後呼叫 v2 create_booking 邏輯
    """
    actor = _get_current_user_from_cookie(request, db)
    if not actor.phone:
        raise HTTPException(400, "請先填寫手機")

    booking_date = payload.get("booking_date")
    booking_time = payload.get("booking_time")
    if not booking_date or not booking_time:
        raise HTTPException(400, "缺少預約日期或時間")
    when = _parse_legacy_date_time(str(booking_date), str(booking_time))

    detail_raw = payload.get("booking_detail")
    if not detail_raw:
        raise HTTPException(400, "缺少 booking_detail")
    try:
        detail_obj = json.loads(detail_raw) if isinstance(detail_raw, str) else detail_raw
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "booking_detail 格式錯誤") from exc

    service_names = detail_obj.get("services") or []
    addon_names = detail_obj.get("addons") or []
    service_ids = _service_ids_from_legacy_detail(db, service_names, addon_names)

    notes = payload.get("booking_note")
    customer_name = (payload.get("customer_name") or "").strip()
    customer_mobile = (payload.get("customer_mobile") or "").strip()

    # 代客/訪客資訊
    client_id = payload.get("client_id")
    guest_name = (payload.get("guest_name") or "").strip() or None

    # 一般客人走舊邏輯：未提供 client_id/guest_name 時，預設為自己
    target_user_id: int | None = None
    add_by_owner: int | None = None

    if client_id is None and not guest_name:
        target_user_id = actor.id
    elif actor.role != "owner":
        # 一般客人可明確帶自己的 client_id（舊前端習慣），但不可代他人也不可帶 guest_name。
        requested_user_id = int(client_id) if client_id is not None else None
        if guest_name or requested_user_id != actor.id:
            raise HTTPException(403, "僅限 owner 可代客建立預約")
        target_user_id = actor.id
    else:
        # owner 代客（會員或訪客）
        add_by_owner = actor.id
        if client_id is not None:
            target_user_id = int(client_id)

    # 業主代訂「已註冊客人」時，同步更新客人基本資料。
    if actor.role == "owner" and target_user_id is not None and target_user_id != actor.id:
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user:
            raise HTTPException(404, "客人不存在")

        if customer_mobile:
            target_user.phone = customer_mobile
        if customer_name:
            target_user.name = customer_name
        db.commit()

    # 直接呼叫 v2 booking 建立邏輯
    guest_phone = customer_mobile if guest_name else None
    booking_create = BookingCreate(
        user_id=target_user_id,
        add_by_owner=add_by_owner,
        guest_name=guest_name,
        guest_phone=guest_phone,
        service_ids=service_ids,
        booking_date=when,
        notes=notes,
    )
    try:
        created = _create_booking_core(
            booking_create,
            background_tasks=background_tasks,
            db=db,
        )
    except IntegrityError as exc:
        db.rollback()
        if "booking_services.booking_id, booking_services.service_id" in str(exc.orig):
            raise HTTPException(400, "預約項目重複，請重新選擇服務") from exc
        raise
    return {"message": "預約成功!期待為您服務!", "orderId": created.id}


@app.get("/orders", response_model=list[LegacyOrderRead])
def legacy_list_orders(client_id: int = Query(...), request: Request = None, db: Session = Depends(get_db)):
    """
    舊前端的預約列表。
    目前前端會帶 client_id（user.id），但後端仍以 JWT cookie 的 user 為準。
    """
    user = _get_current_user_from_cookie(request, db)
    if user.id != client_id and user.role != "owner":
        raise HTTPException(403, "無權限")

    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.services), joinedload(Booking.user))
        .filter(Booking.user_id == client_id)
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return [
        LegacyOrderRead.model_validate(_legacy_order_from_booking(b, b.services, b.user))
        for b in bookings
    ]


@app.get("/owner/orders", response_model=list[LegacyOrderRead])
def legacy_owner_list_orders(request: Request, db: Session = Depends(get_db)):
    """業主查看代客預約紀錄（含客人資訊）。"""
    actor = _get_current_user_from_cookie(request, db)
    if actor.role != "owner":
        raise HTTPException(403, "僅限 owner")

    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.services), joinedload(Booking.user))
        .filter(Booking.created_by_owner_id == actor.id)
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return [
        LegacyOrderRead.model_validate(_legacy_order_from_booking(b, b.services, b.user))
        for b in bookings
    ]


@app.get("/customers/search", response_model=list[UserRead])
def search_customers(q: str = Query(..., min_length=1), request: Request = None, db: Session = Depends(get_db)):
    """
    業主用客人搜尋（依姓名模糊查詢）。
    僅限 owner 呼叫。
    """
    actor = _get_current_user_from_cookie(request, db)
    if actor.role != "owner":
        raise HTTPException(403, "僅限 owner 可搜尋客人")

    keyword = q.strip()
    if not keyword:
        return []

    rows = (
        db.query(User)
        .filter(User.name.ilike(f"%{keyword}%"))
        .order_by(User.created_at.desc())
        .limit(20)
        .all()
    )
    return [UserRead.model_validate(u) for u in rows]


@app.put("/orders/cancel/{booking_id}")
def legacy_cancel_order(
    booking_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user_from_cookie(request, db)
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    _assert_can_cancel_booking(user, b)
    if b.status == "cancelled":
        return {"message": "預約已取消"}
    if b.status not in ("pending", "confirmed"):
        raise HTTPException(400, f"無法取消狀態為「{b.status}」的預約")
    if b.status == "confirmed" and user.role != "owner":
        _assert_cancel_time_window(b)

    cal_event_id = b.google_calendar_event_id
    b.status = "cancelled"
    db.commit()
    db.refresh(b)

    background_tasks.add_task(_bg_delete_google_calendar_event, cal_event_id)
    if user.role != "owner":
        background_tasks.add_task(_bg_notify_owner_customer_cancelled, booking_id, user.id)
    else:
        background_tasks.add_task(_bg_notify_customer_owner_cancelled, booking_id)

    return {"message": "預約已取消"}



def _validate_category_max_one(services: list[Service]) -> None:
    """驗證同一分類最多選 1 項（X選1 規則）"""
    categories = [s.category for s in services]
    counts = Counter(categories)
    dup = [c for c, n in counts.items() if n > 1]
    if dup:
        raise HTTPException(400, f"同一分類只能選一項：{', '.join(dup)}")


def _assert_booking_on_30_min_grid(booking_date: datetime) -> None:
    """預約開始時間必須落在 30 分鐘格線。"""
    if booking_date.minute not in (0, 30) or booking_date.second != 0 or booking_date.microsecond != 0:
        raise HTTPException(400, "預約時間需為 30 分鐘格線（HH:00 或 HH:30）")


def _assert_booking_not_in_past(booking_date: datetime) -> None:
    """不可建立過去時間的預約。"""
    if booking_date <= datetime.now():
        raise HTTPException(400, "不可預約過去時間")


def _booking_create_authorized(actor: User, data: BookingCreate) -> BookingCreate:
    """依登入者解析預約主體；禁止客戶端偽造他人身分。"""
    if data.add_by_owner is not None:
        if actor.id != data.add_by_owner or actor.role != "owner":
            raise HTTPException(403, "僅限 owner 可替他人建立預約")
        return data
    if data.guest_name:
        raise HTTPException(403, "訪客預約僅限店家操作")
    if data.user_id is not None and data.user_id != actor.id:
        raise HTTPException(403, "僅能為本人建立預約")
    return BookingCreate(
        user_id=actor.id,
        add_by_owner=None,
        guest_name=None,
        guest_phone=None,
        service_ids=data.service_ids,
        booking_date=data.booking_date,
        notes=data.notes,
    )


def _is_booking_overlap_integrity_error(exc: IntegrityError) -> bool:
    """判斷是否為 bookings 時段互斥約束衝突。"""
    msg = str(getattr(exc, "orig", exc)).lower()
    return "bookings_no_time_overlap_excl" in msg


def _create_booking_core(
    data: BookingCreate,
    background_tasks: BackgroundTasks,
    db: Session,
) -> BookingRead:
    """建立預約（核心邏輯）。呼叫前須已完成身分授權。"""
    target_user = None
    if data.user_id is not None:
        target_user = db.query(User).filter(User.id == data.user_id).first()
        if not target_user:
            raise HTTPException(404, "使用者不存在")

    owner = None
    if data.add_by_owner is not None:
        owner = db.query(User).filter(User.id == data.add_by_owner).first()
        if not owner:
            raise HTTPException(404, "店家不存在")
        if owner.role != "owner":
            raise HTTPException(403, "僅限 owner 可替他人建立預約")

    services = db.query(Service).filter(Service.id.in_(data.service_ids)).all()
    if len(services) != len(data.service_ids):
        raise HTTPException(404, "部分服務不存在")
    _validate_category_max_one(services)
    _assert_booking_on_30_min_grid(data.booking_date)
    _assert_booking_not_in_past(data.booking_date)
    total_duration = sum(s.duration_minutes for s in services)
    total_price = sum(s.price for s in services)

    start = data.booking_date
    end = start + timedelta(minutes=total_duration)

    # 檢查時段是否與其他預約重疊（pending 與 confirmed 皆佔用時段）
    existing = (
        db.query(Booking)
        .filter(Booking.status.in_(["pending", "confirmed"]))
        .all()
    )
    for b in existing:
        b_end = b.booking_date + timedelta(minutes=b.total_duration_minutes)
        if start < b_end and b.booking_date < end:
            raise HTTPException(409, "該時段已被預約")

    status = "confirmed" if data.add_by_owner is not None else "pending"
    booking = Booking(
        user_id=data.user_id,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        created_by_owner_id=data.add_by_owner,
        booking_date=data.booking_date,
        total_duration_minutes=total_duration,
        total_price=total_price,
        status=status,
        notes=data.notes,
    )
    booking.services = services
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_booking_overlap_integrity_error(exc):
            raise HTTPException(409, "該時段已被預約") from exc
        raise
    db.refresh(booking)

    if data.add_by_owner is not None:
        # 代客預約：直接已確認，通知客人並同步 Google Calendar confirmed 狀態。
        if booking.user_id:
            customer = db.query(User).filter(User.id == booking.user_id).first()
            if customer and customer.line_user_id:
                access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
                if access_token:
                    background_tasks.add_task(
                        _bg_line_push_safe,
                        access_token,
                        customer.line_user_id,
                        _booking_confirmed_text(booking),
                    )
        background_tasks.add_task(_bg_sync_confirm_booking_google_calendar, booking.id)
    else:
        background_tasks.add_task(
            _bg_after_booking_created_calendar_and_line,
            booking.id,
            booking.user_id or 0,
        )

    return _booking_to_read(booking)


@app.post("/bookings", response_model=BookingRead)
def create_booking(
    data: BookingCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """建立預約（需登入 Cookie）。客人僅能替自己預約；業主可代客（`add_by_owner` 須為本人且 role=owner）。"""
    actor = _get_current_user_from_cookie(request, db)
    resolved = _booking_create_authorized(actor, data)
    return _create_booking_core(resolved, background_tasks, db)


def _do_confirm_booking(booking_id: int, db: Session) -> Booking:
    """共用確認邏輯：pending → confirmed，回傳更新後的 Booking。"""
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    if b.status == "confirmed":
        raise HTTPException(400, "預約已是確認狀態")
    if b.status != "pending":
        raise HTTPException(400, f"無法確認狀態為「{b.status}」的預約")
    b.status = "confirmed"
    db.commit()
    db.refresh(b)

    return b


def _do_reject_booking(booking_id: int, db: Session) -> tuple[Booking, str | None]:
    """向下相容舊邏輯，實際委派給 _do_cancel_booking。"""
    return _do_cancel_booking(booking_id, db)


def _do_cancel_booking(booking_id: int, db: Session) -> tuple[Booking, str | None]:
    """共用取消邏輯：pending 或 confirmed → cancelled；回傳 (Booking, 刪除用 google_calendar_event_id)。"""
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    if b.status == "cancelled":
        raise HTTPException(400, "預約已是取消狀態")
    if b.status not in ("pending", "confirmed"):
        raise HTTPException(400, f"無法取消狀態為「{b.status}」的預約")

    # 同步 Google Calendar：刪除事件（取消前先記 event_id）
    cal_event_id = b.google_calendar_event_id

    b.status = "cancelled"
    db.commit()
    db.refresh(b)

    return b, cal_event_id


def _do_complete_booking(booking_id: int, db: Session) -> Booking:
    """共用完成邏輯：confirmed → completed，回傳更新後的 Booking。"""
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    if b.status == "completed":
        raise HTTPException(400, "預約已是完成狀態")
    if b.status != "confirmed":
        raise HTTPException(400, f"只有已確認的預約可標記完成（目前狀態：{b.status}）")
    b.status = "completed"
    db.commit()
    db.refresh(b)

    return b


@app.post("/bookings/{booking_id}/confirm", response_model=BookingRead)
def confirm_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """確認預約（僅限 owner）：pending → confirmed，並推播 LINE 通知客人。"""
    actor = _get_current_user_from_cookie(request, db)
    if actor.role != "owner":
        raise HTTPException(403, "僅限 owner 可確認預約")

    b = _do_confirm_booking(booking_id, db)

    customer = db.query(User).filter(User.id == b.user_id).first()
    if customer and customer.line_user_id:
        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        if access_token:
            background_tasks.add_task(
                _bg_line_push_safe,
                access_token,
                customer.line_user_id,
                _booking_confirmed_text(b),
            )
    background_tasks.add_task(_bg_sync_confirm_booking_google_calendar, b.id)

    return _booking_to_read(b)


async def _handle_owner_confirm(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
    background_tasks: BackgroundTasks,
) -> str:
    """Webhook 業主「確認 {id}」指令處理，回傳要 reply 的文字。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作"
    # 支援：確認 17 / 確認17 / 確認#17
    raw_id = cmd.removeprefix("確認").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：確認 {預約編號}"
    booking_id = int(raw_id)
    customer_line: str | None = None
    push_copy: str | None = None
    summary = ""
    try:
        with SessionLocal() as db:
            b = _do_confirm_booking(booking_id, db)
            cust = db.query(User).filter(User.id == b.user_id).first()
            if cust and cust.line_user_id:
                customer_line = cust.line_user_id
            push_copy = _booking_confirmed_text(b)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已確認，通知已送出。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}"

    if customer_line and access_token and push_copy:
        background_tasks.add_task(_bg_line_push_safe, access_token, customer_line, push_copy)
    background_tasks.add_task(_bg_sync_confirm_booking_google_calendar, booking_id)

    return summary


async def _handle_owner_reject(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
    background_tasks: BackgroundTasks,
) -> str:
    """向下相容舊「拒絕」指令，邏輯同取消。"""
    return await _handle_owner_cancel(
        cmd, source_user_id, owner_line_id, access_token, background_tasks
    )


async def _handle_owner_cancel(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
    background_tasks: BackgroundTasks,
) -> str:
    """Webhook 業主「取消{id}」或「拒絕{id}」指令處理，回傳要 reply 的文字。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作"
    # 支援：取消 17 / 取消17 / 取消#17 / 拒絕17
    raw_id = cmd.removeprefix("取消").removeprefix("拒絕").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：取消 {預約編號}"
    booking_id = int(raw_id)
    customer_line: str | None = None
    push_copy: str | None = None
    summary = ""
    cal_ev: str | None = None
    try:
        with SessionLocal() as db:
            b, cal_ev = _do_cancel_booking(booking_id, db)
            cust = db.query(User).filter(User.id == b.user_id).first()
            if cust and cust.line_user_id:
                customer_line = cust.line_user_id
            push_copy = _booking_rejected_text(b)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已取消，通知已送出。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}"

    if customer_line and access_token and push_copy:
        background_tasks.add_task(_bg_line_push_safe, access_token, customer_line, push_copy)
    background_tasks.add_task(_bg_delete_google_calendar_event, cal_ev)

    return summary


async def _handle_owner_complete(
    cmd: str,
    source_user_id: str,
    owner_line_id: str,
    access_token: str,
    background_tasks: BackgroundTasks,
) -> str:
    """Webhook 業主「完成{id}」指令處理，回傳要 reply 的文字。"""
    if not owner_line_id or source_user_id != owner_line_id:
        return "您無權執行此操作"
    # 支援：完成 17 / 完成17 / 完成#17
    raw_id = cmd.removeprefix("完成").strip().lstrip("#").strip()
    if not raw_id.isdigit():
        return "格式錯誤，請使用：完成 {預約編號}"
    booking_id = int(raw_id)
    try:
        with SessionLocal() as db:
            b = _do_complete_booking(booking_id, db)
            date_str = b.booking_date.strftime("%Y/%m/%d %H:%M")
            summary = f"預約 #{b.id}（{date_str}）已標記完成。"
    except HTTPException as exc:
        return f"操作失敗：{exc.detail}"

    background_tasks.add_task(_bg_sync_complete_booking_google_calendar, booking_id)
    return summary


def _notify_owner_customer_cancelled(b: Booking, customer: User) -> None:
    """客人取消預約後推播通知業主（sync，失敗只 log 不中斷）。"""
    owner_line_id = os.getenv("OWNER_LINE_USER_ID", "").strip()
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not owner_line_id or not access_token:
        return
    try:
        _push_text_to_line_sync(access_token, owner_line_id, _customer_cancelled_owner_text(b, customer))
    except Exception as exc:
        print(f"[cancel_booking] LINE 業主通知失敗（不影響取消）：{exc}")


def _bg_notify_owner_customer_cancelled(booking_id: int, cancelled_by_user_id: int) -> None:
    """背景：客人取消後以新 Session 載入資料並通知業主 LINE。"""
    with SessionLocal() as db:
        b = (
            db.query(Booking)
            .options(joinedload(Booking.services))
            .filter(Booking.id == booking_id)
            .first()
        )
        actor = db.query(User).filter(User.id == cancelled_by_user_id).first()
        if not b or not actor:
            return
        _notify_owner_customer_cancelled(b, actor)


def _bg_notify_customer_owner_cancelled(booking_id: int) -> None:
    """背景：業主取消後以新 Session 載入資料並通知客人 LINE。"""
    with SessionLocal() as db:
        b = (
            db.query(Booking)
            .options(joinedload(Booking.services))
            .filter(Booking.id == booking_id)
            .first()
        )
        if not b:
            return
        customer = db.query(User).filter(User.id == b.user_id).first()
        if not customer or not customer.line_user_id:
            return
        access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        if not access_token:
            return
        _bg_line_push_safe(access_token, customer.line_user_id, _booking_rejected_text(b))


def _assert_can_cancel_booking(actor: User, booking: Booking) -> None:
    if actor.role == "owner" or actor.id == booking.user_id:
        return
    raise HTTPException(403, "僅限預約本人或店家可取消")


def _assert_can_read_booking(actor: User, booking: Booking) -> None:
    """預約詳情：業主可看全部；客人僅能看 user_id 為本人的預約（訪客單僅業主可讀）。"""
    if actor.role == "owner":
        return
    if booking.user_id is not None and booking.user_id == actor.id:
        return
    raise HTTPException(403, "無權限")


def _assert_cancel_time_window(booking: Booking) -> None:
    """預約開始前 24 小時內不可取消。"""
    if datetime.now() >= booking.booking_date - timedelta(hours=24):
        raise HTTPException(400, "開約前 24 小時內不可取消")


def _booking_to_read(booking: Booking) -> BookingRead:
    """將 Booking model 轉成 BookingRead（含 services）"""
    customer_name = booking.guest_name
    customer_phone = booking.guest_phone
    customer_photo = None
    if booking.user is not None:
        customer_name = booking.user.name
        customer_phone = booking.user.phone
        customer_photo = booking.user.photo

    return BookingRead(
        id=booking.id,
        user_id=booking.user_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_photo=customer_photo,
        booking_date=booking.booking_date,
        total_duration_minutes=booking.total_duration_minutes,
        total_price=booking.total_price,
        status=booking.status,
        notes=booking.notes,
        google_calendar_event_id=booking.google_calendar_event_id,
        created_at=booking.created_at,
        guest_name=booking.guest_name,
        guest_phone=booking.guest_phone,
        created_by_owner_id=booking.created_by_owner_id,
        services=[ServiceRead.model_validate(s) for s in booking.services],
    )


@app.get("/bookings", response_model=list[BookingRead])
def list_bookings(
    request: Request,
    date_filter: date | None = Query(None, alias="date"),
    status: str | None = Query(None, description="篩選狀態（pending/confirmed/cancelled/completed），不填則顯示 pending+confirmed"),
    db: Session = Depends(get_db),
):
    """查詢預約（需登入）：可依日期與狀態篩選；業主可看全部，客人僅看自己。"""
    actor = _get_current_user_from_cookie(request, db)
    q = db.query(Booking).options(joinedload(Booking.services), joinedload(Booking.user))
    if status:
        q = q.filter(Booking.status == status)
    else:
        q = q.filter(Booking.status.in_(["pending", "confirmed"]))
    if date_filter:
        start = datetime.combine(date_filter, datetime.min.time())
        end = start + timedelta(days=1)
        q = q.filter(Booking.booking_date >= start, Booking.booking_date < end)
    if actor.role != "owner":
        q = q.filter(Booking.user_id == actor.id)
    bookings = q.order_by(Booking.booking_date).all()
    return [_booking_to_read(b) for b in bookings]


@app.get("/bookings/{booking_id}", response_model=BookingRead)
def get_booking(booking_id: int, request: Request, db: Session = Depends(get_db)):
    """取得單一預約（需登入）"""
    actor = _get_current_user_from_cookie(request, db)
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services), joinedload(Booking.user))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    _assert_can_read_booking(actor, b)
    return _booking_to_read(b)


@app.post("/bookings/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """取消預約（需登入 Cookie；軟刪除為 cancelled）；僅預約本人或 owner 可操作"""
    actor = _get_current_user_from_cookie(request, db)
    b = (
        db.query(Booking)
        .options(joinedload(Booking.services), joinedload(Booking.user))
        .filter(Booking.id == booking_id)
        .first()
    )
    if not b:
        raise HTTPException(404, "預約不存在")
    _assert_can_cancel_booking(actor, b)
    if b.status == "cancelled":
        return _booking_to_read(b)
    if b.status not in ("pending", "confirmed"):
        raise HTTPException(400, f"無法取消狀態為「{b.status}」的預約")
    if b.status == "confirmed":
        _assert_cancel_time_window(b)

    cal_event_id = b.google_calendar_event_id
    b.status = "cancelled"
    db.commit()
    db.refresh(b)

    background_tasks.add_task(_bg_delete_google_calendar_event, cal_event_id)

    if actor.role != "owner":
        background_tasks.add_task(_bg_notify_owner_customer_cancelled, booking_id, actor.id)
    else:
        background_tasks.add_task(_bg_notify_customer_owner_cancelled, booking_id)

    return _booking_to_read(b)
