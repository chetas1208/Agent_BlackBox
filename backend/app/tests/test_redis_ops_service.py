from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.redis_ops_service import RedisOpsService


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def get(self, key: str):
        return self.data.get(key)

    async def delete(self, key: str):
        self.data.pop(key, None)

    async def incr(self, key: str):
        current = int(self.data.get(key, "0"))
        current += 1
        self.data[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int):
        return True


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_session_lock_round_trip():
    service = RedisOpsService(FakeRedis())

    assert await service.acquire_session_lock("sess-1") is True
    assert await service.acquire_session_lock("sess-1") is False

    await service.release_session_lock("sess-1")

    assert await service.acquire_session_lock("sess-1") is True


@pytest.mark.asyncio
async def test_idempotency_returns_existing_session():
    service = RedisOpsService(FakeRedis())

    created, existing = await service.register_idempotency("abc", "session-a")
    assert created is True
    assert existing is None

    created, existing = await service.register_idempotency("abc", "session-b")
    assert created is False
    assert existing == "session-a"


@pytest.mark.asyncio
async def test_rate_limit_reports_remaining_quota(monkeypatch):
    monkeypatch.setenv("ABB_RATE_LIMIT_MAX_REQUESTS", "2")
    service = RedisOpsService(FakeRedis())

    allowed, remaining = await service.check_rate_limit()
    assert allowed is True
    assert remaining == 1

    allowed, remaining = await service.check_rate_limit()
    assert allowed is True
    assert remaining == 0

    allowed, remaining = await service.check_rate_limit()
    assert allowed is False
    assert remaining == 0
