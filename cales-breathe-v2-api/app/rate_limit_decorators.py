from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request

from app.rate_limiter import RateLimiter


def _extract_client_ip(request: Request) -> str:
    # 先看常見的 Proxy header，再 fallback 到 client.host。
    xff = request.headers.get("X-Forwarded-For") or request.headers.get("x-forwarded-for")
    if xff:
        # 取第一個 IP 即可（最靠近 client 的）。
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[0]
    client = request.client
    return client.host if client and client.host else "unknown"


def rate_limit_login(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    登入專用的 rate limit decorator。

    要求被裝飾的 handler 具有下列參數：
    - request: Request
    - payload: 具有 contact_mail 屬性的物件（例如 LegacyLoginRequest）
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 從 args/kwargs 中找出 request 與 payload。
        request: Request | None = kwargs.get("request")
        payload = kwargs.get("payload")

        # FastAPI 會依名稱注入參數，這裡假設 login handler 使用關鍵字參數名稱。
        # 若將來簽名變動，可視需要擴充成更通用的掃描。
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

        if request is None or payload is None:
            # 缺少必要資訊時，為避免誤傷，選擇放行。
            return func(*args, **kwargs)

        app = request.app
        limiter: RateLimiter | None = getattr(app.state, "login_rate_limiter", None)
        if limiter is None:
            # 未配置 Redis 或 RateLimiter 時，採 fail-open 策略。
            return func(*args, **kwargs)

        client_ip = _extract_client_ip(request)
        username = getattr(payload, "contact_mail", None) or ""

        try:
            result = limiter.check_login(client_ip, username)
        except Exception:
            # Redis 發生錯誤時，為了可用性採 fail-open，並讓上層 log。
            return func(*args, **kwargs)

        if not result.allowed:
            headers = {}
            if result.retry_after_seconds is not None:
                headers["Retry-After"] = str(result.retry_after_seconds)
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts, please try again later.",
                headers=headers,
            )

        return func(*args, **kwargs)

    return wrapper

