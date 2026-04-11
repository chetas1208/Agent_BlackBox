from __future__ import annotations
from app.models.checkpoint import Checkpoint
from app.repositories.redis_repo import RedisRepository

NS = "checkpoints"


class CheckpointService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def create(
        self,
        session_id: str,
        label: str = "",
        event_index: int = 0,
        plan_snapshot: list[str] | None = None,
        memory_ids: list[str] | None = None,
        sandbox_ref: str = "",
        risk_score: float = 0.0,
        confidence: float = 1.0,
        safety_status: str = "clean",
    ) -> Checkpoint:
        cp = Checkpoint(
            session_id=session_id,
            label=label,
            event_index=event_index,
            plan_snapshot=plan_snapshot or [],
            memory_snapshot_ref=",".join(memory_ids) if memory_ids else "",
            sandbox_snapshot_ref=sandbox_ref,
            risk_score_at=risk_score,
            confidence_at=confidence,
            safety_status=safety_status,
        )
        await self.repo.save_model(self._ns(session_id), cp.id, cp)
        return cp

    async def get(self, session_id: str, checkpoint_id: str) -> Checkpoint | None:
        return await self.repo.get_model(self._ns(session_id), checkpoint_id, Checkpoint)

    async def list_by_session(self, session_id: str) -> list[Checkpoint]:
        cps = await self.repo.list_models(self._ns(session_id), Checkpoint)
        cps.sort(key=lambda c: c.created_at)
        return cps

    async def get_last_clean(self, session_id: str) -> Checkpoint | None:
        cps = await self.list_by_session(session_id)
        for cp in reversed(cps):
            if cp.safety_status == "clean":
                return cp
        return cps[0] if cps else None
