import json
import math
import time
from dataclasses import dataclass
from typing import Optional

import redis


@dataclass
class RateLimitResult:
    allowed: bool
    remaining_tokens: int
    retry_after_seconds: Optional[int] = None


class RateLimiter:
    """
    Token Bucket rate limiter，將狀態存放在 Redis。

    - 每個 key 維護 tokens 與 last_refill_ts（Unix time，秒）。
    - bucket_capacity：最多可累積的 token 數。
    - fill_rate_per_sec：每秒補充的 token 數（例如 1/30 代表 30 秒補 1 個）。
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        bucket_capacity: int,
        fill_rate_per_sec: float,
        key_prefix: str = "rate",
    ) -> None:
        self._redis = redis_client
        self._bucket_capacity = bucket_capacity
        self._fill_rate_per_sec = fill_rate_per_sec
        self._key_prefix = key_prefix.rstrip(":")

    def _now(self) -> float:
        return time.time()

    def _load_bucket(self, key: str) -> tuple[float, float]:
        """
        從 Redis 載入目前的 token 狀態。

        回傳 (tokens, last_refill_ts)。若 key 不存在，視為滿桶。
        """
        raw = self._redis.get(key)
        if not raw:
            return float(self._bucket_capacity), self._now()

        try:
            data = json.loads(raw.decode("utf-8"))
            tokens = float(data.get("tokens", self._bucket_capacity))
            last_refill_ts = float(data.get("last_refill_ts", self._now()))
            return tokens, last_refill_ts
        except Exception:
            # 若資料壞掉，保守起見視為滿桶重置。
            return float(self._bucket_capacity), self._now()

    def _store_bucket(self, key: str, tokens: float, last_refill_ts: float) -> None:
        payload = json.dumps(
            {
                "tokens": tokens,
                "last_refill_ts": last_refill_ts,
            }
        ).encode("utf-8")
        # 加上一個寬鬆的 TTL，避免長期閒置的 key 佔用空間。
        ttl_seconds = max(int(self._bucket_capacity / self._fill_rate_per_sec * 10), 60)
        self._redis.set(key, payload, ex=ttl_seconds)

    def _refill(self, tokens: float, last_refill_ts: float, now_ts: float) -> tuple[float, float]:
        if tokens >= self._bucket_capacity:
            return float(self._bucket_capacity), now_ts

        elapsed = max(0.0, now_ts - last_refill_ts)
        if elapsed <= 0 or self._fill_rate_per_sec <= 0:
            return tokens, last_refill_ts

        new_tokens = elapsed * self._fill_rate_per_sec
        tokens = min(self._bucket_capacity, tokens + new_tokens)
        return tokens, now_ts

    def check_login(self, ip: str, username: str) -> RateLimitResult:
        """
        針對登入路由，以 (ip, username) 作為限流 key。
        """
        # 正規化，避免大小寫或空白差異。
        ip_norm = (ip or "").strip() or "unknown"
        user_norm = (username or "").strip().lower() or "unknown"
        key = f"{self._key_prefix}:login:{ip_norm}:{user_norm}"

        now_ts = self._now()
        tokens, last_refill_ts = self._load_bucket(key)
        tokens, last_refill_ts = self._refill(tokens, last_refill_ts, now_ts)

        cost = 1.0
        if tokens >= cost:
            tokens -= cost
            self._store_bucket(key, tokens, now_ts)
            return RateLimitResult(
                allowed=True,
                remaining_tokens=int(tokens),
                retry_after_seconds=None,
            )

        # 不足以支付這次登入：計算大約多久後會有第一個 token。
        needed = cost - tokens
        if self._fill_rate_per_sec <= 0:
            retry_after = None
        else:
            retry_after = int(math.ceil(needed / self._fill_rate_per_sec))

        # 寫回目前狀態（未扣除，單純反映最新 refill 結果）。
        self._store_bucket(key, tokens, now_ts)

        return RateLimitResult(
            allowed=False,
            remaining_tokens=int(tokens),
            retry_after_seconds=retry_after,
        )

