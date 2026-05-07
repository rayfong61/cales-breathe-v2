"""Access JWT（短效）+ refresh opaque token（HttpOnly cookie、DB 可撤銷與輪替）。"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import jwt
from fastapi import HTTPException, Response
from sqlalchemy.orm import Session

from app.models import RefreshToken, User

if TYPE_CHECKING:
    pass


def jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(500, "缺少 JWT_SECRET 設定")
    return secret


def access_cookie_name() -> str:
    return os.getenv("ACCESS_TOKEN_COOKIE_NAME", "cb_access_token").strip() or "cb_access_token"


def refresh_cookie_name() -> str:
    return os.getenv("REFRESH_TOKEN_COOKIE_NAME", "cb_refresh_token").strip() or "cb_refresh_token"


def access_ttl_minutes() -> int:
    raw = os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60").strip()
    try:
        n = int(raw)
    except ValueError:
        return 60
    return max(5, min(n, 24 * 60))


def refresh_ttl_days() -> int:
    raw = os.getenv("REFRESH_TOKEN_TTL_DAYS", "30").strip()
    try:
        n = int(raw)
    except ValueError:
        return 30
    return max(1, min(n, 365))


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"


def cookie_samesite() -> str:
    raw = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    if raw not in {"lax", "strict", "none"}:
        raw = "none"
    if raw == "none" and not cookie_secure():
        return "lax"
    return raw


def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_refresh_raw() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=access_ttl_minutes())
    payload = {
        "sub": str(user_id),
        "purpose": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "登入已過期") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "未授權") from exc
    if payload.get("purpose") != "access":
        raise HTTPException(401, "未授權")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(401, "未授權")
    try:
        return int(sub)
    except ValueError as exc:
        raise HTTPException(401, "未授權") from exc


def set_access_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=access_cookie_name(),
        value=token,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        max_age=access_ttl_minutes() * 60,
        path="/",
    )


def set_refresh_cookie(resp: Response, raw: str) -> None:
    resp.set_cookie(
        key=refresh_cookie_name(),
        value=raw,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        max_age=refresh_ttl_days() * 24 * 60 * 60,
        path="/",
    )


def clear_access_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key=access_cookie_name(),
        path="/",
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
    )


def clear_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key=refresh_cookie_name(),
        path="/",
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
    )


def clear_session_cookies(resp: Response) -> None:
    clear_access_cookie(resp)
    clear_refresh_cookie(resp)


def issue_auth_session(db: Session, response: Response, user_id: int) -> None:
    """建立新的 access + refresh（寫入 DB 並 Set-Cookie）。"""
    raw = _new_refresh_raw()
    th = _hash_refresh(raw)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=refresh_ttl_days())
    row = RefreshToken(
        user_id=user_id,
        token_hash=th,
        expires_at=exp.replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    access = create_access_token(user_id)
    set_access_cookie(response, access)
    set_refresh_cookie(response, raw)


def revoke_all_refresh_for_user(db: Session, user_id: int) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()


def _active_refresh_row(db: Session, raw: str) -> RefreshToken | None:
    if not raw:
        return None
    th = _hash_refresh(raw)
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == th, RefreshToken.revoked_at.is_(None))
        .first()
    )
    if not row:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row.expires_at <= now:
        return None
    return row


def refresh_session(db: Session, response: Response, refresh_raw: str) -> User:
    """驗證 refresh、輪替後發新 cookie；失敗拋 401。"""
    row = _active_refresh_row(db, refresh_raw)
    if not row:
        clear_session_cookies(response)
        raise HTTPException(401, "請重新登入")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        clear_session_cookies(response)
        raise HTTPException(401, "請重新登入")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row.revoked_at = now
    db.add(row)

    new_raw = _new_refresh_raw()
    new_hash = _hash_refresh(new_raw)
    exp = datetime.now(timezone.utc) + timedelta(days=refresh_ttl_days())
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=exp.replace(tzinfo=None),
    )
    db.add(new_row)
    db.commit()

    access = create_access_token(user.id)
    set_access_cookie(response, access)
    set_refresh_cookie(response, new_raw)
    return user


def resolve_user_for_logout(db: Session, access_token: str | None, refresh_raw: str | None) -> int | None:
    """盡量取得要撤銷 session 的 user_id（access 或 refresh）。"""
    if refresh_raw:
        row = _active_refresh_row(db, refresh_raw)
        if row:
            return row.user_id
        th = _hash_refresh(refresh_raw)
        row2 = db.query(RefreshToken).filter(RefreshToken.token_hash == th).first()
        if row2:
            return row2.user_id
    if access_token:
        try:
            return decode_access_token(access_token)
        except HTTPException:
            pass
    return None
