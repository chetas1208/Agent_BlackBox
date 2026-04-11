from __future__ import annotations
import redis.asyncio as redis
from app.core.config import get_settings

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pool


async def close_redis():
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
