from __future__ import annotations

import json
from hashlib import sha256

from redis.asyncio import Redis

from app.core.config import get_settings


class RedisOpsService:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.settings = get_settings()

    def _key(self, *parts: str) -> str:
        return self.settings.redis_prefix + ":".join(parts)

    def _hash(self, raw: str) -> str:
        return sha256(raw.encode("utf-8")).hexdigest()

    async def acquire_session_lock(self, session_id: str) -> bool:
        return bool(await self.redis.set(
            self._key("lock", "session", session_id),
            "1",
            ex=self.settings.lock_ttl_seconds,
            nx=True,
        ))

    async def release_session_lock(self, session_id: str) -> None:
        await self.redis.delete(self._key("lock", "session", session_id))

    async def register_idempotency(self, raw_key: str, session_id: str) -> tuple[bool, str | None]:
        idem_key = self._key("idem", self._hash(raw_key))
        created = await self.redis.set(
            idem_key,
            session_id,
            ex=self.settings.idempotency_ttl_seconds,
            nx=True,
        )
        if created:
            return True, None
        existing = await self.redis.get(idem_key)
        return False, existing

    async def check_rate_limit(self, scope: str = "operator") -> tuple[bool, int]:
        key = self._key("rate", scope)
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.settings.rate_limit_window_seconds)
        remaining = max(self.settings.rate_limit_max_requests - count, 0)
        return count <= self.settings.rate_limit_max_requests, remaining

    async def set_run_state(self, session_id: str, state: dict) -> None:
        await self.redis.set(
            self._key("run", session_id, "state"),
            json.dumps(state),
            ex=self.settings.run_state_ttl_seconds,
        )

    async def get_run_state(self, session_id: str) -> dict | None:
        raw = await self.redis.get(self._key("run", session_id, "state"))
        if not raw:
            return None
        return json.loads(raw)

    async def cache_plan(self, raw_key: str, payload: dict) -> None:
        await self.redis.set(
            self._key("cache", "plan", self._hash(raw_key)),
            json.dumps(payload),
            ex=self.settings.idempotency_ttl_seconds,
        )

    async def get_cached_plan(self, raw_key: str) -> dict | None:
        raw = await self.redis.get(self._key("cache", "plan", self._hash(raw_key)))
        if not raw:
            return None
        return json.loads(raw)
