from typing import Any

import app.main as main_module
from app.rate_limiter import RateLimiter, RateLimitResult


class _DummyLimiter:
    def __init__(self, allowed: bool, retry_after: int | None = None) -> None:
        self.allowed = allowed
        self.retry_after = retry_after
        self.calls: list[tuple[str, str]] = []

    def check_login(self, ip: str, username: str) -> RateLimitResult:
        self.calls.append((ip, username))
        return RateLimitResult(
            allowed=self.allowed,
            remaining_tokens=0,
            retry_after_seconds=self.retry_after,
        )


def test_login_without_redis_fallback_allows(client, monkeypatch):
    """
    若未設定 Redis / RateLimiter，登入路由應保持既有行為（不限流）。
    這裡透過將 app.state.login_rate_limiter 設為 None 來模擬。
    """
    main_module.app.state.login_rate_limiter = None

    from app.models import User
    from app.main import SessionLocal, pwd_context

    db = SessionLocal()
    try:
        u = User(
            name="login_user",
            contact_mail="login@example.com",
            password_hash=pwd_context.hash("password123"),
            provider="local",
            role="customer",
        )
        db.add(u)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/login",
        json={"contact_mail": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "登入成功"


def test_login_rate_limit_blocks_when_limiter_disallows(client, monkeypatch):
    """
    當 RateLimiter 回報不允許時，/login 應回傳 429，並尊重 Retry-After。
    """
    dummy = _DummyLimiter(allowed=False, retry_after=30)
    main_module.app.state.login_rate_limiter = dummy

    from app.models import User
    from app.main import SessionLocal, pwd_context

    db = SessionLocal()
    try:
        u = User(
            name="blocked_user",
            contact_mail="blocked@example.com",
            password_hash=pwd_context.hash("password123"),
            provider="local",
            role="customer",
        )
        db.add(u)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/login",
        json={"contact_mail": "blocked@example.com", "password": "password123"},
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"
    body = resp.json()
    assert body["detail"]
    # 確認 limiter 有收到正確的 key 維度
    assert any("blocked@example.com" in user for _ip, user in dummy.calls)


def test_rate_limiter_token_bucket_behaviour_with_memory_store(monkeypatch):
    """
    直接測試 RateLimiter.Token Bucket 行為（不連線實際 Redis）。
    以 dict 模擬 redis_client，覆寫 _load_bucket/_store_bucket。
    """

    class _MemoryRedis:
        def __init__(self) -> None:
            self.store: dict[str, bytes] = {}

        def get(self, key: str) -> bytes | None:
            return self.store.get(key)

        def set(self, key: str, value: bytes, ex: int | None = None) -> None:  # noqa: ARG002
            self.store[key] = value

    fake_redis = _MemoryRedis()

    limiter = RateLimiter(
        redis_client=fake_redis,  # type: ignore[arg-type]
        bucket_capacity=5,
        fill_rate_per_sec=1 / 30.0,
    )

    # 固定時間軸，避免依賴實際 time.time()
    times: list[float] = [1_000_000.0]

    def _fake_now() -> float:
        return times[0]

    monkeypatch.setattr(limiter, "_now", _fake_now)

    ip = "127.0.0.1"
    user = "test@example.com"

    # 第一次呼叫：滿桶 5，扣掉 1 → 剩餘 4。
    r1 = limiter.check_login(ip, user)
    assert r1.allowed
    assert r1.remaining_tokens == 4

    # 連續再呼叫 4 次，總共 5 次都應該允許。
    for expected in (3, 2, 1, 0):
        r = limiter.check_login(ip, user)
        assert r.allowed
        assert r.remaining_tokens == expected

    # 此時 bucket 已經為 0，再呼叫一次應被拒絕。
    r_block = limiter.check_login(ip, user)
    assert not r_block.allowed
    assert r_block.retry_after_seconds is not None

    # 時間往後推 60 秒（約可補 2 個 token）。
    times[0] += 60.0
    r_after = limiter.check_login(ip, user)
    assert r_after.allowed
    # 補約 2 個 token 扣掉 1，剩餘應約為 1（整數化後為 1 或 2 均可接受，視誤差而定）
    assert r_after.remaining_tokens >= 1

