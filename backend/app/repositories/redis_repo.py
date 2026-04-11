"""Generic Redis repository for JSON-serialized Pydantic models."""
from __future__ import annotations

import json
from typing import TypeVar, Type
from pydantic import BaseModel
from redis.asyncio import Redis
from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class RedisRepository:
    def __init__(self, redis: Redis):
        self.r = redis
        self.prefix = get_settings().redis_prefix

    def _key(self, *parts: str) -> str:
        return self.prefix + ":".join(parts)

    async def save_model(self, namespace: str, id: str, model: BaseModel) -> None:
        key = self._key(namespace, id)
        await self.r.set(key, model.model_dump_json())

    async def get_model(self, namespace: str, id: str, cls: Type[T]) -> T | None:
        key = self._key(namespace, id)
        data = await self.r.get(key)
        if data is None:
            return None
        return cls.model_validate_json(data)

    async def delete_model(self, namespace: str, id: str) -> None:
        await self.r.delete(self._key(namespace, id))

    async def list_ids(self, namespace: str) -> list[str]:
        pattern = self._key(namespace, "*")
        prefix_len = len(self._key(namespace, ""))
        keys = []
        async for key in self.r.scan_iter(match=pattern, count=200):
            keys.append(key[prefix_len:])
        return keys

    async def list_models(self, namespace: str, cls: Type[T]) -> list[T]:
        ids = await self.list_ids(namespace)
        items = []
        for id in ids:
            m = await self.get_model(namespace, id, cls)
            if m:
                items.append(m)
        return items

    async def append_to_list(self, list_key: str, data: str) -> None:
        await self.r.rpush(self._key(list_key), data)

    async def get_list(self, list_key: str, start: int = 0, end: int = -1) -> list[str]:
        return await self.r.lrange(self._key(list_key), start, end)

    async def get_list_length(self, list_key: str) -> int:
        return await self.r.llen(self._key(list_key))

    async def publish(self, channel: str, message: str) -> None:
        await self.r.publish(self._key(channel), message)

    async def save_hash(self, namespace: str, id: str, data: dict) -> None:
        key = self._key(namespace, id)
        await self.r.hset(key, mapping={k: json.dumps(v) if not isinstance(v, str) else v for k, v in data.items()})

    async def get_hash(self, namespace: str, id: str) -> dict:
        key = self._key(namespace, id)
        raw = await self.r.hgetall(key)
        result = {}
        for k, v in raw.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result
