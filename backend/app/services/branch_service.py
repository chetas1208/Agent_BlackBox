from __future__ import annotations

from datetime import datetime

from app.models.branch import BranchStatus, RecoveryBranch
from app.repositories.redis_repo import RedisRepository

NS = "branches"


class BranchService:
    def __init__(self, repo: RedisRepository) -> None:
        self.repo = repo

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def create(
        self,
        session_id: str,
        parent_checkpoint_id: str,
        strategy: str,
        description: str = "",
        sandbox_id: str | None = None,
    ) -> RecoveryBranch:
        branch = RecoveryBranch(
            session_id=session_id,
            parent_checkpoint_id=parent_checkpoint_id,
            strategy=strategy,
            description=description,
            sandbox_id=sandbox_id,
        )
        await self.repo.save_model(self._ns(session_id), branch.id, branch)
        return branch

    async def get(
        self, session_id: str, branch_id: str
    ) -> RecoveryBranch | None:
        return await self.repo.get_model(
            self._ns(session_id), branch_id, RecoveryBranch
        )

    async def update(self, branch: RecoveryBranch) -> RecoveryBranch:
        await self.repo.save_model(
            self._ns(branch.session_id), branch.id, branch
        )
        return branch

    async def complete(
        self,
        session_id: str,
        branch_id: str,
        outcome: str,
        confidence: float = 0.5,
    ) -> RecoveryBranch | None:
        b = await self.get(session_id, branch_id)
        if not b:
            return None
        b.status = BranchStatus.COMPLETED
        b.outcome = outcome
        b.confidence_score = confidence
        b.completed_at = datetime.utcnow()
        return await self.update(b)

    async def select_winner(
        self, session_id: str, branch_id: str
    ) -> RecoveryBranch | None:
        b = await self.get(session_id, branch_id)
        if not b:
            return None
        b.status = BranchStatus.SELECTED
        b.is_winner = True
        return await self.update(b)

    async def list_by_session(self, session_id: str) -> list[RecoveryBranch]:
        branches = await self.repo.list_models(
            self._ns(session_id), RecoveryBranch
        )
        branches.sort(key=lambda b: b.created_at)
        return branches

    async def compare(self, session_id: str) -> dict:
        branches = await self.list_by_session(session_id)
        return {
            "total_branches": len(branches),
            "branches": [
                {
                    "id": b.id,
                    "strategy": b.strategy,
                    "status": b.status.value,
                    "outcome": b.outcome,
                    "confidence": b.confidence_score,
                    "is_winner": b.is_winner,
                    "event_count": b.event_count,
                }
                for b in branches
            ],
            "winner": next((b.id for b in branches if b.is_winner), None),
        }
