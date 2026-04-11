from __future__ import annotations
from datetime import datetime
from app.models.memory import MemoryItem, MemoryLayer, MemoryStatus
from app.schemas.memory import CreateMemoryRequest, UpdateMemoryRequest
from app.repositories.redis_repo import RedisRepository

NS = "memory"


class MemoryService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def create(self, session_id: str, req: CreateMemoryRequest) -> MemoryItem:
        item = MemoryItem(
            session_id=session_id,
            layer=req.layer,
            key=req.key,
            value=req.value,
            source=req.source,
            confidence=req.confidence,
            importance_score=req.importance_score,
            tags=req.tags,
        )
        await self.repo.save_model(self._ns(session_id), item.id, item)
        # also index by key for quick lookups
        await self.repo.save_model(f"{NS}:bykey:{session_id}:{req.layer.value}", req.key, item)
        return item

    async def create_item(self, item: MemoryItem) -> MemoryItem:
        await self.repo.save_model(self._ns(item.session_id), item.id, item)
        await self.repo.save_model(
            f"{NS}:bykey:{item.session_id}:{item.layer.value}",
            item.key,
            item,
        )
        return item

    async def get(self, session_id: str, memory_id: str) -> MemoryItem | None:
        return await self.repo.get_model(self._ns(session_id), memory_id, MemoryItem)

    async def get_by_key(self, session_id: str, layer: MemoryLayer, key: str) -> MemoryItem | None:
        return await self.repo.get_model(
            f"{NS}:bykey:{session_id}:{layer.value}",
            key,
            MemoryItem,
        )

    async def update(self, session_id: str, memory_id: str, req: UpdateMemoryRequest) -> MemoryItem | None:
        item = await self.get(session_id, memory_id)
        if not item:
            return None
        if req.value is not None:
            item.value = req.value
        if req.confidence is not None:
            item.confidence = req.confidence
        if req.contradiction_score is not None:
            item.contradiction_score = req.contradiction_score
        if req.importance_score is not None:
            item.importance_score = req.importance_score
        if req.status is not None:
            item.status = req.status
        if req.tags is not None:
            item.tags = req.tags
        item.updated_at = datetime.utcnow()
        await self.repo.save_model(self._ns(session_id), item.id, item)
        return item

    async def quarantine(self, session_id: str, memory_id: str) -> MemoryItem | None:
        return await self.update(
            session_id,
            memory_id,
            UpdateMemoryRequest(status=MemoryStatus.QUARANTINED, contradiction_score=1.0),
        )

    async def promote(self, session_id: str, memory_id: str) -> MemoryItem | None:
        return await self.update(
            session_id,
            memory_id,
            UpdateMemoryRequest(status=MemoryStatus.ACTIVE, contradiction_score=0.0),
        )

    async def list_by_session(
        self,
        session_id: str,
        layer: MemoryLayer | None = None,
        status: MemoryStatus | None = None,
    ) -> list[MemoryItem]:
        items = await self.repo.list_models(self._ns(session_id), MemoryItem)
        if layer:
            items = [i for i in items if i.layer == layer]
        if status:
            items = [i for i in items if i.status == status]
        items.sort(key=lambda m: m.updated_at, reverse=True)
        return items

    async def snapshot_ids(self, session_id: str) -> list[str]:
        items = await self.list_by_session(session_id)
        return [i.id for i in items if i.status == MemoryStatus.ACTIVE]

    async def count_quarantined(self) -> int:
        """Count quarantined memories across all sessions (dashboard metric)."""
        all_ids = await self.repo.list_ids(NS)
        # This scans the top-level memory namespace
        count = 0
        for session_ns_id in all_ids:
            # each id here is actually a session sub-key
            item = await self.repo.get_model(NS, session_ns_id, MemoryItem)
            if item and item.status == MemoryStatus.QUARANTINED:
                count += 1
        return count
