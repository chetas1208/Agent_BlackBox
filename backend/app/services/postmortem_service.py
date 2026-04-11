from __future__ import annotations

from datetime import datetime

from app.models.branch import RecoveryBranch
from app.models.event import Event, EventSeverity, EventType
from app.models.memory import MemoryItem, MemoryStatus
from app.models.postmortem import Postmortem, PostmortemSection
from app.models.session import Session
from app.repositories.redis_repo import RedisRepository
from app.services.branch_service import BranchService
from app.services.checkpoint_service import CheckpointService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService

NS = "postmortems"


class PostmortemService:
    def __init__(
        self,
        repo: RedisRepository,
        event_svc: EventRecorderService,
        memory_svc: MemoryService,
        checkpoint_svc: CheckpointService,
        branch_svc: BranchService,
    ) -> None:
        self.repo = repo
        self.event_svc = event_svc
        self.memory_svc = memory_svc
        self.checkpoint_svc = checkpoint_svc
        self.branch_svc = branch_svc

    async def generate(self, session: Session) -> Postmortem:
        events = await self.event_svc.get_events(session.id)
        memories = await self.memory_svc.list_by_session(session.id)
        checkpoints = await self.checkpoint_svc.list_by_session(session.id)
        branches = await self.branch_svc.list_by_session(session.id)

        failure_events = [
            e
            for e in events
            if e.severity in (EventSeverity.ERROR, EventSeverity.CRITICAL)
        ]
        recovery_events = [
            e
            for e in events
            if e.event_type
            in (
                EventType.REPLAY_STARTED,
                EventType.REPLAY_COMPLETED,
                EventType.CHECKPOINT_RESTORED,
            )
        ]
        quarantined = [
            m for m in memories if m.status == MemoryStatus.QUARANTINED
        ]

        duration = 0.0
        if session.started_at and session.ended_at:
            start = (
                session.started_at
                if isinstance(session.started_at, datetime)
                else datetime.fromisoformat(str(session.started_at))
            )
            end = (
                session.ended_at
                if isinstance(session.ended_at, datetime)
                else datetime.fromisoformat(str(session.ended_at))
            )
            duration = (end - start).total_seconds()

        sections: list[PostmortemSection] = []
        sections.append(
            PostmortemSection(
                title="Mission",
                content=(
                    f"Task: {session.title}\n"
                    f"Goal: {session.goal}\n"
                    f"Outcome: {session.outcome or session.status}"
                ),
            )
        )

        if failure_events:
            failure_text = "\n".join(
                f"- [{e.severity}] {e.summary}" for e in failure_events[:10]
            )
            sections.append(
                PostmortemSection(
                    title="Failures Detected",
                    content=failure_text,
                    severity="error",
                )
            )

        if recovery_events:
            recovery_text = "\n".join(
                f"- {e.summary}" for e in recovery_events[:10]
            )
            sections.append(
                PostmortemSection(
                    title="Recovery Actions",
                    content=recovery_text,
                    severity="warning",
                )
            )

        if quarantined:
            q_text = "\n".join(
                f"- {m.key} (layer: {m.layer}, confidence: {m.confidence})"
                for m in quarantined
            )
            sections.append(
                PostmortemSection(
                    title="Quarantined Memories",
                    content=q_text,
                    severity="warning",
                )
            )

        if branches:
            b_text = "\n".join(
                f"- {b.strategy}: {b.status.value}"
                + (" (WINNER)" if b.is_winner else "")
                for b in branches
            )
            sections.append(
                PostmortemSection(title="Recovery Branches", content=b_text)
            )

        root_cause = "No failures detected"
        if failure_events:
            first_fail = failure_events[0]
            root_cause = first_fail.summary
            if quarantined:
                root_cause += (
                    f" — triggered by stale memory: {quarantined[0].key}"
                )

        recommendations: list[str] = []
        if any(e.event_type == EventType.RETRY_DETECTED for e in events):
            recommendations.append(
                "Lower retry threshold or add variation to retry strategies"
            )
        if quarantined:
            recommendations.append(
                "Enable aggressive memory validation for this task type"
            )
        if len(failure_events) > 3:
            recommendations.append(
                "Consider stricter safety policy for similar tasks"
            )
        if not recommendations:
            recommendations.append(
                "Current policy performed well — no changes recommended"
            )

        pm = Postmortem(
            session_id=session.id,
            mission_summary=f"{session.title}: {session.description}",
            final_outcome=session.outcome or session.status,
            root_cause=root_cause,
            key_events=[
                {
                    "type": e.event_type,
                    "summary": e.summary,
                    "severity": e.severity,
                }
                for e in (failure_events + recovery_events)[:15]
            ],
            memories_involved=[
                {
                    "key": m.key,
                    "layer": m.layer,
                    "status": m.status,
                    "confidence": m.confidence,
                }
                for m in memories[:20]
            ],
            quarantined_memories=[m.id for m in quarantined],
            failure_points=[e.summary for e in failure_events[:5]],
            recovery_actions=[e.summary for e in recovery_events[:5]],
            branches_used=[
                {
                    "id": b.id,
                    "strategy": b.strategy,
                    "status": b.status.value,
                    "is_winner": b.is_winner,
                }
                for b in branches
            ],
            winning_branch=next(
                (b.id for b in branches if b.is_winner), None
            ),
            policy_recommendations=recommendations,
            total_events=len(events),
            total_checkpoints=len(checkpoints),
            total_recovery_attempts=len(recovery_events),
            duration_seconds=duration,
            sections=sections,
        )

        await self.repo.save_model(NS, session.id, pm)
        return pm

    async def get(self, session_id: str) -> Postmortem | None:
        return await self.repo.get_model(NS, session_id, Postmortem)
