from __future__ import annotations

from datetime import datetime

from app.models.approval import ApprovalGate, ApprovalStatus
from app.repositories.redis_repo import RedisRepository

NS = "approvals"


class ApprovalService:
    def __init__(self, repo: RedisRepository) -> None:
        self.repo = repo

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def create(
        self,
        session_id: str,
        action_type: str,
        action_summary: str,
        rationale: str,
        evidence: list[str] | None = None,
        risk_level: str = "medium",
        risk_score: float = 0.5,
    ) -> ApprovalGate:
        gate = ApprovalGate(
            session_id=session_id,
            action_type=action_type,
            action_summary=action_summary,
            rationale=rationale,
            evidence=evidence or [],
            risk_level=risk_level,
            risk_score=risk_score,
        )
        await self.repo.save_model(self._ns(session_id), gate.id, gate)
        return gate

    async def get(self, session_id: str, gate_id: str) -> ApprovalGate | None:
        return await self.repo.get_model(
            self._ns(session_id), gate_id, ApprovalGate
        )

    async def get_pending(self, session_id: str) -> ApprovalGate | None:
        gates = await self.repo.list_models(self._ns(session_id), ApprovalGate)
        for g in reversed(gates):
            if g.status == ApprovalStatus.PENDING:
                return g
        return None

    async def approve(
        self,
        session_id: str,
        gate_id: str,
        resolved_by: str = "operator",
    ) -> ApprovalGate | None:
        gate = await self.get(session_id, gate_id)
        if not gate:
            return None
        gate.status = ApprovalStatus.APPROVED
        gate.resolved_by = resolved_by
        gate.resolved_at = datetime.utcnow()
        await self.repo.save_model(self._ns(session_id), gate.id, gate)
        return gate

    async def deny(
        self,
        session_id: str,
        gate_id: str,
        resolved_by: str = "operator",
    ) -> ApprovalGate | None:
        gate = await self.get(session_id, gate_id)
        if not gate:
            return None
        gate.status = ApprovalStatus.DENIED
        gate.resolved_by = resolved_by
        gate.resolved_at = datetime.utcnow()
        await self.repo.save_model(self._ns(session_id), gate.id, gate)
        return gate

    async def list_by_session(self, session_id: str) -> list[ApprovalGate]:
        gates = await self.repo.list_models(self._ns(session_id), ApprovalGate)
        gates.sort(key=lambda g: g.created_at, reverse=True)
        return gates
