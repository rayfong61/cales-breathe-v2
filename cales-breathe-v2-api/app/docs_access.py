"""正式環境下關閉或以 HTTP Basic 保護 /docs、/redoc、/openapi.json。"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from secrets import compare_digest

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


def _parse_bool(env_val: str | None, default: bool = False) -> bool:
    if env_val is None or not str(env_val).strip():
        return default
    return str(env_val).strip().lower() in ("1", "true", "yes", "on")


def is_production_environment() -> bool:
    v = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return v in ("production", "prod")


def docs_disabled_by_flag() -> bool:
    return _parse_bool(os.getenv("DISABLE_API_DOCS"), False)


def docs_basic_credentials() -> tuple[str | None, str | None]:
    u = (os.getenv("DOCS_BASIC_USER") or "").strip()
    p = (os.getenv("DOCS_BASIC_PASSWORD") or "").strip()
    if u and p:
        return (u, p)
    return (None, None)


def docs_urls_disabled() -> bool:
    if docs_disabled_by_flag():
        return True
    if is_production_environment() and docs_basic_credentials() == (None, None):
        return True
    return False


def docs_fastapi_kwargs() -> dict[str, None]:
    if docs_urls_disabled():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def should_use_docs_basic_middleware() -> bool:
    return (
        is_production_environment()
        and not docs_disabled_by_flag()
        and docs_basic_credentials() != (None, None)
    )


def _safe_str_equal(a: str, b: str) -> bool:
    return compare_digest(
        hashlib.sha256(a.encode("utf-8")).digest(),
        hashlib.sha256(b.encode("utf-8")).digest(),
    )


class DocsBasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, username: str, password: str) -> None:
        super().__init__(app)
        self._username = username
        self._password = password

    def _is_protected_path(self, path: str) -> bool:
        if path == "/openapi.json" or path == "/redoc":
            return True
        if path.startswith("/redoc/"):
            return True
        if path == "/docs" or path.startswith("/docs/"):
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        if not self._is_protected_path(request.url.path):
            return await call_next(request)
        auth = request.headers.get("Authorization")
        parts = (auth or "").split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "basic":
            return self._unauthorized()
        try:
            raw = base64.b64decode(parts[1].strip(), validate=True)
            decoded = raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return self._unauthorized()
        if ":" not in decoded:
            return self._unauthorized()
        user, _, password = decoded.partition(":")
        if not (_safe_str_equal(user, self._username) and _safe_str_equal(password, self._password)):
            return self._unauthorized()
        return await call_next(request)

    def _unauthorized(self) -> Response:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="API documentation"'},
        )


def add_docs_basic_auth_middleware(app) -> None:
    if not should_use_docs_basic_middleware():
        return
    u, p = docs_basic_credentials()
    if u is None or p is None:
        return
    app.add_middleware(DocsBasicAuthMiddleware, username=u, password=p)
