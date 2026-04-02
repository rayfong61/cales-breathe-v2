"""Google / LINE OAuth：簽發與本地登入相同的 JWT cookie。"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import quote, unquote, urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

CreateToken = Callable[[int], str]
SetCookie = Callable[[Response, str], None]


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(500, "缺少 JWT_SECRET 設定")
    return secret


def _api_public_base(request: Request) -> str:
    base = os.getenv("API_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return base
    return str(request.base_url).rstrip("/")


def _default_frontend_origin() -> str:
    return os.getenv("FRONTEND_PUBLIC_ORIGIN", "http://localhost:3000").strip().rstrip("/")


def _oauth_db_unreachable_redirect(frontend_origin: str, redirect_path: str) -> RedirectResponse:
    """PostgreSQL 連線失敗（timeout 等）時導回前端，避免 OAuth callback 回 500 整頁錯誤。"""
    return _oauth_error_redirect(frontend_origin, redirect_path, "資料庫暫時無法連線，請稍後再試")


def _oauth_error_redirect(frontend_origin: str, redirect_path: str, error_value: str) -> RedirectResponse:
    """OAuth 失敗時導回前端並帶 oauth_error=（避免瀏覽器只看到 JSON）。"""
    base = frontend_origin.rstrip("/")
    path = redirect_path if redirect_path.startswith("/") else f"/{redirect_path}"
    full = f"{base}{path}"
    sep = "&" if "?" in full else "?"
    resp = RedirectResponse(
        url=f"{full}{sep}oauth_error={quote(error_value)}",
        status_code=302,
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _frontend_redirect_with_query(
    frontend_origin: str,
    redirect_path: str,
    params: dict[str, str],
) -> RedirectResponse:
    base = frontend_origin.rstrip("/")
    path = redirect_path if redirect_path.startswith("/") else f"/{redirect_path}"
    full = f"{base}{path}"
    sep = "&" if "?" in full else "?"
    query = "&".join(f"{k}={quote(v)}" for k, v in params.items())
    resp = RedirectResponse(url=f"{full}{sep}{query}", status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _safe_redirect_path(path: str | None, default: str = "/account") -> str:
    if not path or not isinstance(path, str):
        return default
    p = path.strip()
    if not p.startswith("/") or p.startswith("//") or ".." in p or "\n" in p or "\r" in p:
        return default
    return p


def _encode_oauth_state(
    *,
    provider: str,
    redirect: str,
    frontend_origin: str,
) -> str:
    now = datetime.now(timezone.utc)
    # OAuth 流程可能較久（選帳號、同意權限），state 放寬至 30 分鐘
    exp = now + timedelta(minutes=30)
    payload = {
        # 避免使用鍵名 typ（易與 JWT header 混淆）；舊 state 仍相容 typ
        "purpose": "oauth_state",
        "provider": provider,
        "redirect": redirect,
        "frontend_origin": frontend_origin,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _decode_oauth_state(raw: str) -> dict:
    """解回 OAuth state；處理 URL 傳遞時空白/+ 與 JWT_SECRET 尾端空白問題。"""
    raw = (raw or "").strip()
    if not raw:
        raise HTTPException(400, "缺少 OAuth state")
    candidates: list[str] = [raw]
    u = unquote(raw)
    if u != raw:
        candidates.append(u)
    # 少數情境下 + 會被轉成空白，破壞 JWT
    if raw.count(".") == 2 and " " in raw:
        candidates.append(raw.replace(" ", "+"))

    last_err: Exception | None = None
    for cand in candidates:
        try:
            payload = jwt.decode(
                cand,
                _jwt_secret(),
                algorithms=["HS256"],
                leeway=120,
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(400, "OAuth state 已過期，請重新點登入") from exc
        except jwt.PyJWTError as exc:
            last_err = exc
            continue
        if payload.get("purpose") == "oauth_state" or payload.get("typ") == "oauth_state":
            return payload
        last_err = ValueError("OAuth state payload 不符")
    raise HTTPException(400, "OAuth state 無效或已過期") from last_err


def _encode_bind_token(
    provider: str,
    email: str,
    frontend_origin: str,
    redirect: str,
    provider_user_id: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "oauth_bind_confirm",
        "provider": provider,
        "email": email,
        "provider_user_id": (provider_user_id or "").strip(),
        "frontend_origin": frontend_origin,
        "redirect": redirect,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _decode_bind_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"], leeway=60)
    except jwt.PyJWTError as exc:
        raise HTTPException(400, "綁定 token 無效或已過期") from exc
    if payload.get("purpose") != "oauth_bind_confirm":
        raise HTTPException(400, "綁定 token 無效")
    return payload


def _finish_oauth_html(frontend_origin: str, redirect_path: str) -> HTMLResponse:
    """popup：postMessage 給 opener；整頁：導回前端。"""
    fo = json.dumps(frontend_origin)
    rp = json.dumps(redirect_path)
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>登入完成</title></head>
<body><script>
(function() {{
  var origin = {fo};
  var path = {rp};
  if (window.opener) {{
    try {{
      window.opener.postMessage("login-success", origin);
    }} catch (e) {{}}
    window.close();
  }} else {{
    window.location.href = origin + path;
  }}
}})();
</script><p>登入完成，請關閉此視窗。</p></body></html>"""
    return HTMLResponse(content=body)


def _google_oauth_credentials() -> tuple[str, str]:
    """舊專案常用 GOOGLE_CLIENT_ID，本專案預設用 GOOGLE_OAUTH_*。"""
    cid = (
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        or os.getenv("GOOGLE_CLIENT_ID", "").strip()
    )
    sec = (
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        or os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    )
    return cid, sec


def _google_exchange_code(code: str, redirect_uri: str) -> dict:
    cid, sec = _google_oauth_credentials()
    if not cid or not sec:
        raise HTTPException(503, "Google OAuth 未設定（GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET）")
    with httpx.Client(timeout=20.0) as client:
        r = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": cid,
                "client_secret": sec,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if r.status_code != 200:
            detail = r.text[:800]
            try:
                j = r.json()
                detail = j.get("error_description") or j.get("error") or detail
            except Exception:
                pass
            raise HTTPException(400, f"Google token 交換失敗：{detail}")
        data = r.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(400, "Google 未回傳 access_token")
        u = client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if u.status_code != 200:
            raise HTTPException(400, "取得 Google 使用者資料失敗")
        return u.json()


def _line_exchange_code(code: str, redirect_uri: str) -> tuple[str, str | None, str | None]:
    cid = os.getenv("LINE_LOGIN_CHANNEL_ID", "").strip()
    sec = os.getenv("LINE_LOGIN_CHANNEL_SECRET", "").strip()
    if not cid or not sec:
        raise HTTPException(503, "LINE Login 未設定（LINE_LOGIN_CHANNEL_ID / LINE_LOGIN_CHANNEL_SECRET）")
    with httpx.Client(timeout=20.0) as client:
        r = client.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": cid,
                "client_secret": sec,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            detail = r.text[:800]
            try:
                j = r.json()
                detail = j.get("error_description") or j.get("error") or detail
            except Exception:
                pass
            # invalid_grant 常見：同一組 code 被請求兩次（重複導向／雙擊）
            hint = ""
            if "invalid_grant" in str(detail).lower():
                hint = "（授權碼僅能使用一次，請重新點「LINE 登入」）"
            raise HTTPException(400, f"LINE token 交換失敗：{detail}{hint}")
        data = r.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(400, "LINE 未回傳 access_token")
        p = client.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if p.status_code != 200:
            raise HTTPException(400, "取得 LINE 使用者資料失敗")
        prof = p.json()
        user_id = prof.get("userId")
        name = prof.get("displayName")
        picture = prof.get("pictureUrl")
        if not user_id:
            raise HTTPException(400, "LINE 未回傳 userId")
        return user_id, name, picture


def create_oauth_router(
    create_access_token: CreateToken,
    set_auth_cookie: SetCookie,
) -> APIRouter:
    router = APIRouter(tags=["oauth"])

    @router.post("/auth/oauth-bind/confirm")
    def oauth_bind_confirm(payload: dict, response: Response, db: Session = Depends(get_db)):
        token = str(payload.get("token") or "").strip()
        if not token:
            raise HTTPException(400, "缺少綁定 token")
        data = _decode_bind_token(token)
        provider = str(data.get("provider") or "")
        email = str(data.get("email") or "").strip().lower()
        provider_user_id = str(data.get("provider_user_id") or "").strip()
        if provider != "google":
            raise HTTPException(400, "目前僅支援 Google 綁定確認")
        if not email:
            raise HTTPException(400, "綁定資料缺少 email")
        if not provider_user_id:
            raise HTTPException(400, "綁定資料缺少 provider user id")

        user = db.query(User).filter(User.contact_mail == email).first()
        if not user:
            raise HTTPException(404, "找不到要綁定的帳號")

        if user.provider == "local":
            # SQLite 在本機開發時偶發「database is locked」，短暫重試可吸收瞬時鎖競爭。
            committed = False
            for attempt in range(5):
                try:
                    user.provider = "google"
                    user.google_user_id = provider_user_id
                    db.commit()
                    committed = True
                    break
                except OperationalError as ex:
                    db.rollback()
                    if "database is locked" not in str(ex).lower():
                        raise
                    if attempt == 4:
                        raise HTTPException(503, "資料庫忙碌中，請 1-2 秒後重試")
                    time.sleep(0.2 * (attempt + 1))
            if not committed:
                raise HTTPException(503, "資料庫忙碌中，請稍後重試")
            db.refresh(user)

        auth = create_access_token(user.id)
        set_auth_cookie(response, auth)
        return {"message": "綁定成功並登入", "user": {"user": {"id": user.id}}}

    @router.get("/auth/google")
    def google_start(
        request: Request,
        redirect: str | None = Query(None, description="登入後導向前端路徑，例如 /account"),
        frontend_origin: str | None = Query(None, description="前端 origin，popup postMessage 用"),
    ):
        cid, _ = _google_oauth_credentials()
        if not cid:
            raise HTTPException(
                503,
                "Google OAuth 未設定（GOOGLE_OAUTH_CLIENT_ID 或 GOOGLE_CLIENT_ID）",
            )
        api_base = _api_public_base(request)
        cb = f"{api_base}/auth/google/callback"
        red = _safe_redirect_path(redirect, "/account")
        fo = (frontend_origin or "").strip().rstrip("/") or _default_frontend_origin()
        state = _encode_oauth_state(provider="google", redirect=red, frontend_origin=fo)
        q = urlencode(
            {
                "client_id": cid,
                "redirect_uri": cb,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        resp = RedirectResponse(
            url=f"https://accounts.google.com/o/oauth2/v2/auth?{q}",
            status_code=302,
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @router.get("/auth/google/callback")
    def google_callback(
        request: Request,
        code: str | None = Query(None),
        state: str | None = Query(None),
        error: str | None = Query(None),
        db: Session = Depends(get_db),
    ):
        fo = _default_frontend_origin()
        red = "/account"
        if error:
            # 使用者按「取消」或拒絕權限時常見 access_denied → 導回前端
            if state:
                try:
                    st = _decode_oauth_state(state)
                    fo = st.get("frontend_origin") or fo
                    red = _safe_redirect_path(st.get("redirect"), "/account")
                except HTTPException:
                    pass
            return _oauth_error_redirect(fo, red, error)
        if not code or not state:
            raise HTTPException(400, "缺少 code 或 state")
        st = _decode_oauth_state(state)
        fo = st.get("frontend_origin") or fo
        red = _safe_redirect_path(st.get("redirect"), "/account")
        if st.get("provider") != "google":
            raise HTTPException(400, "OAuth state 不符")
        api_base = _api_public_base(request)
        cb = f"{api_base}/auth/google/callback"
        try:
            info = _google_exchange_code(code, cb)
        except HTTPException as exc:
            return _oauth_error_redirect(fo, red, str(exc.detail))
        email = (info.get("email") or "").strip().lower()
        google_sub = str(info.get("sub") or "").strip()
        if not email:
            raise HTTPException(400, "Google 未提供 email")
        if not google_sub:
            raise HTTPException(400, "Google 未提供使用者識別碼")
        name = (info.get("name") or email.split("@")[0] or "Google User").strip()
        picture = info.get("picture")

        try:
            user = db.query(User).filter(User.google_user_id == google_sub).first()
            if not user:
                user = db.query(User).filter(User.contact_mail == email).first()
            if not user:
                user = User(
                    name=name,
                    contact_mail=email,
                    password_hash=None,
                    provider="google",
                    google_user_id=google_sub,
                    role="customer",
                    photo=picture,
                )
                db.add(user)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    user = db.query(User).filter(User.contact_mail == email).first()
                    if not user:
                        raise HTTPException(400, "建立 Google 帳號失敗")
            else:
                # local 帳號撞同 email：需要使用者明確確認是否綁定
                if user.provider == "local":
                    bind_token = _encode_bind_token("google", email, fo, red, google_sub)
                    return _frontend_redirect_with_query(
                        fo,
                        "/login",
                        {
                            "oauth_bind_required": "1",
                            "oauth_provider": "google",
                            "oauth_email": email,
                            "oauth_bind_token": bind_token,
                        },
                    )
                if user.google_user_id and user.google_user_id != google_sub:
                    return _oauth_error_redirect(fo, red, "此 Google 帳號已綁定其他會員")
                if not user.google_user_id:
                    user.google_user_id = google_sub
                if user.provider != "google":
                    user.provider = "google"
                if picture and not user.photo:
                    user.photo = picture
                db.commit()
                db.refresh(user)

            token = create_access_token(user.id)
            html = _finish_oauth_html(fo, red)
            html.headers["Cache-Control"] = "no-store"
            set_auth_cookie(html, token)
            return html
        except OperationalError:
            return _oauth_db_unreachable_redirect(fo, red)

    @router.get("/auth/line")
    def line_start(
        request: Request,
        redirect: str | None = Query(None),
        frontend_origin: str | None = Query(None),
    ):
        cid = os.getenv("LINE_LOGIN_CHANNEL_ID", "").strip()
        if not cid:
            raise HTTPException(503, "LINE Login 未設定（LINE_LOGIN_CHANNEL_ID）")
        api_base = _api_public_base(request)
        cb = f"{api_base}/auth/line/callback"
        red = _safe_redirect_path(redirect, "/account")
        fo = (frontend_origin or "").strip().rstrip("/") or _default_frontend_origin()
        state = _encode_oauth_state(provider="line", redirect=red, frontend_origin=fo)
        q = urlencode(
            {
                "response_type": "code",
                "client_id": cid,
                "redirect_uri": cb,
                "state": state,
                "scope": "profile openid email",
            }
        )
        resp = RedirectResponse(
            url=f"https://access.line.me/oauth2/v2.1/authorize?{q}",
            status_code=302,
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @router.get("/auth/line/callback")
    def line_callback(
        request: Request,
        code: str | None = Query(None),
        state: str | None = Query(None),
        error: str | None = Query(None),
        error_description: str | None = Query(None),
        db: Session = Depends(get_db),
    ):
        fo = _default_frontend_origin()
        red = "/account"
        if error:
            msg = error_description or error
            if state:
                try:
                    st = _decode_oauth_state(state)
                    fo = st.get("frontend_origin") or fo
                    red = _safe_redirect_path(st.get("redirect"), "/account")
                except HTTPException:
                    pass
            return _oauth_error_redirect(fo, red, msg)
        if not code or not state:
            raise HTTPException(400, "缺少 code 或 state")
        st = _decode_oauth_state(state)
        fo = st.get("frontend_origin") or fo
        red = _safe_redirect_path(st.get("redirect"), "/account")
        if st.get("provider") != "line":
            raise HTTPException(400, "OAuth state 不符")
        api_base = _api_public_base(request)
        cb = f"{api_base}/auth/line/callback"
        try:
            line_uid, display_name, picture = _line_exchange_code(code, cb)
        except HTTPException as exc:
            return _oauth_error_redirect(fo, red, str(exc.detail))
        name = (display_name or "LINE User").strip()

        try:
            user = db.query(User).filter(User.line_user_id == line_uid).first()
            if not user:
                user = User(
                    name=name,
                    contact_mail=None,
                    password_hash=None,
                    provider="line",
                    line_user_id=line_uid,
                    photo=picture,
                    role="customer",
                )
                db.add(user)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    user = db.query(User).filter(User.line_user_id == line_uid).first()
                    if not user:
                        raise HTTPException(400, "建立 LINE 帳號失敗")
            else:
                user.name = name or user.name
                if picture and not user.photo:
                    user.photo = picture
                db.commit()
                db.refresh(user)

            token = create_access_token(user.id)
            html = _finish_oauth_html(fo, red)
            html.headers["Cache-Control"] = "no-store"
            set_auth_cookie(html, token)
            return html
        except OperationalError:
            return _oauth_db_unreachable_redirect(fo, red)

    return router
