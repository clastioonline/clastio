"""Token-bucket rate limiting. Uses Redis when configured, otherwise an in-process bucket.

Per-IP limits use `request.client.host`, which uvicorn derives from X-Forwarded-For only for requests that come
from a trusted proxy (FORWARDED_ALLOW_IPS; the Docker image trusts private networks). Many teachers can share one
school IP, so per-IP limits are generous and sensitive actions are also limited per account.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.core.config import get_settings


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self):
        self._local: dict[str, _Bucket] = {}
        self._redis = None
        url = get_settings().redis_url
        if url:
            import redis.asyncio as redis

            self._redis = redis.from_url(url)

    async def hit(self, key: str, capacity: int, refill_per_s: float, cost: float = 1.0) -> bool:
        if self._redis is not None:
            return await self._hit_redis(key, capacity, refill_per_s, cost)
        now = time.monotonic()
        b = self._local.get(key)
        if b is None:
            b = self._local[key] = _Bucket(tokens=capacity, updated=now)
        b.tokens = min(capacity, b.tokens + (now - b.updated) * refill_per_s)
        b.updated = now
        if b.tokens >= cost:
            b.tokens -= cost
            return True
        return False

    _LUA = """
    local key = KEYS[1]
    local cap = tonumber(ARGV[1]); local rate = tonumber(ARGV[2]); local now = tonumber(ARGV[3]); local cost = tonumber(ARGV[4])
    local b = redis.call('HMGET', key, 't', 'u')
    local t = tonumber(b[1]) or cap; local u = tonumber(b[2]) or now
    t = math.min(cap, t + (now - u) * rate)
    local ok = 0
    if t >= cost then t = t - cost; ok = 1 end
    redis.call('HMSET', key, 't', t, 'u', now)
    redis.call('EXPIRE', key, math.ceil(cap / rate) + 10)
    return ok
    """

    async def _hit_redis(self, key: str, capacity: int, refill_per_s: float, cost: float) -> bool:
        ok = await self._redis.eval(self._LUA, 1, f"rl:{key}", capacity, refill_per_s, time.time(), cost)
        return bool(ok)

    def reset(self) -> None:
        self._local.clear()


limiter = RateLimiter()


async def enforce(key: str, capacity: int, per_seconds: float) -> None:
    """Raise 429 when `key` has used up `capacity` requests in `per_seconds`."""
    if not await limiter.hit(key, capacity, capacity / per_seconds):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.",
                            headers={"Retry-After": str(int(per_seconds / capacity) + 1)})


def rate_limit(name: str, capacity: int, per_seconds: float, *, by_user: bool = True):
    """FastAPI dependency factory: `Depends(rate_limit("login", 10, 60))`."""

    async def dep(request: Request):
        ident = request.client.host if request.client else "anon"
        uid = getattr(request.state, "user_id", None)
        if by_user and uid:
            ident = str(uid)
        await enforce(f"{name}:{ident}", capacity, per_seconds)

    return dep
