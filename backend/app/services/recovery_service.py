"""Recovery engine: identifies failures, restores checkpoints, replays execution."""
from __future__ import annotations

from datetime import datetime
from app.models.session import Session, SessionStatus, SessionStage, ExecutionPhase, ProviderStatus
from app.models.event import EventType, EventActor, EventSeverity
from app.models.checkpoint import Checkpoint
from app.services.event_service import EventRecorderService
from app.services.checkpoint_service import CheckpointService
from app.services.memory_service import MemoryService
from app.services.session_service import SessionService
from app.services.sandbox_service import SandboxService


class RecoveryService:
    def __init__(
        self,
        session_svc: SessionService,
        event_svc: EventRecorderService,
        checkpoint_svc: CheckpointService,
        memory_svc: MemoryService,
        sandbox_svc: SandboxService,
    ):
        self.session_svc = session_svc
        self.event_svc = event_svc
        self.checkpoint_svc = checkpoint_svc
        self.memory_svc = memory_svc
        self.sandbox_svc = sandbox_svc

    async def recover(self, session_id: str, checkpoint_id: str | None = None) -> dict:
        session = await self.session_svc.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.RECOVERING
        session.execution_phase = ExecutionPhase.RECOVERING
        session.provider_status = ProviderStatus.RUNNING
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session_id,
            EventType.REPLAY_STARTED,
            summary="Recovery initiated",
            actor=EventActor.RECOVERY_ENGINE,
            severity=EventSeverity.WARNING,
        )

        if checkpoint_id:
            cp = await self.checkpoint_svc.get(session_id, checkpoint_id)
        else:
            cp = await self.checkpoint_svc.get_last_clean(session_id)

        if not cp:
            await self.event_svc.emit(
                session_id,
                EventType.FAILURE_DETECTED,
                summary="No clean checkpoint available for recovery",
                actor=EventActor.RECOVERY_ENGINE,
                severity=EventSeverity.CRITICAL,
            )
            return {"error": "No checkpoint available"}

        await self.event_svc.emit(
            session_id,
            EventType.CHECKPOINT_RESTORED,
            summary=f"Restored checkpoint: {cp.label or cp.id[:8]}",
            actor=EventActor.RECOVERY_ENGINE,
            payload={"checkpoint_id": cp.id, "event_index": cp.event_index},
            checkpoint_id=cp.id,
        )

        if cp.sandbox_snapshot_ref and session.sandbox_id:
            await self.sandbox_svc.restore(session.sandbox_id, cp.sandbox_snapshot_ref, session.sandbox_profile)

        session.current_plan = cp.plan_snapshot
        session.last_checkpoint_id = cp.id
        session.risk_score = max(0, session.risk_score - 0.2)
        session.confidence_score = min(1.0, cp.confidence_at + 0.1)
        session.stage = SessionStage.EXECUTING
        session.execution_phase = ExecutionPhase.EXECUTING
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session_id,
            EventType.REPLAY_COMPLETED,
            summary="Recovery complete, execution resumed from checkpoint",
            actor=EventActor.RECOVERY_ENGINE,
        )

        return {
            "status": "recovered",
            "checkpoint_id": cp.id,
            "restored_event_index": cp.event_index,
        }

    async def get_recovery_report(self, session_id: str) -> dict:
        events = await self.event_svc.get_events(session_id)
        checkpoints = await self.checkpoint_svc.list_by_session(session_id)

        failure_events = [
            e for e in events
            if e.event_type in (
                EventType.FAILURE_DETECTED,
                EventType.CONTRADICTION_DETECTED,
                EventType.RETRY_DETECTED,
            )
        ]
        recovery_events = [
            e for e in events
            if e.event_type in (
                EventType.REPLAY_STARTED,
                EventType.REPLAY_COMPLETED,
                EventType.CHECKPOINT_RESTORED,
            )
        ]

        return {
            "session_id": session_id,
            "total_events": len(events),
            "failure_count": len(failure_events),
            "recovery_count": len(recovery_events),
            "checkpoints": len(checkpoints),
            "failures": [e.model_dump() for e in failure_events[-10:]],
            "recoveries": [e.model_dump() for e in recovery_events[-10:]],
        }
