"""Runtime safety engine that inspects execution and detects failure modes."""
from __future__ import annotations

from app.models.event import Event, EventType, EventSeverity
from app.models.safety import SafetyAlert, DetectorType
from app.models.session import Session
from app.repositories.redis_repo import RedisRepository
from app.core.config import get_settings

NS = "alerts"


class SafetyEngineService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo
        self.settings = get_settings()

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def save_alert(self, alert: SafetyAlert) -> SafetyAlert:
        await self.repo.save_model(self._ns(alert.session_id), alert.id, alert)
        return alert

    async def list_alerts(self, session_id: str) -> list[SafetyAlert]:
        alerts = await self.repo.list_models(self._ns(session_id), SafetyAlert)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return alerts

    async def detect_retry_loop(self, events: list[Event]) -> SafetyAlert | None:
        """Detect repeated tool calls with similar arguments and no progress."""
        if len(events) < self.settings.retry_loop_threshold:
            return None

        tool_events = [e for e in events if e.event_type == EventType.TOOL_INVOKED]
        if len(tool_events) < self.settings.retry_loop_threshold:
            return None

        recent = tool_events[-self.settings.retry_loop_threshold:]
        commands = [e.payload.get("command", e.payload.get("tool", "")) for e in recent]

        if len(set(commands)) == 1 and commands[0]:
            return SafetyAlert(
                session_id=events[-1].session_id,
                detector_type=DetectorType.RETRY_LOOP,
                severity="error",
                message=f"Retry loop detected: '{commands[0]}' called {len(recent)} times consecutively",
                trigger_event_id=recent[-1].id,
            )
        return None

    async def detect_contradiction(
        self,
        events: list[Event],
        session: Session,
    ) -> SafetyAlert | None:
        """Detect when new evidence contradicts stored memory."""
        for e in reversed(events[-5:]):
            if e.event_type == EventType.TOOL_RESULT and e.payload.get("contradicts_memory"):
                return SafetyAlert(
                    session_id=session.id,
                    detector_type=DetectorType.CONTRADICTION,
                    severity="error",
                    message=f"Contradiction: {e.payload.get('contradiction_detail', 'New result conflicts with stored memory')}",
                    trigger_event_id=e.id,
                )
        return None

    async def detect_drift(
        self,
        events: list[Event],
        session: Session,
    ) -> SafetyAlert | None:
        """Detect when agent moves away from original goal."""
        recent_steps = [
            e for e in events[-10:]
            if e.event_type in (EventType.TOOL_INVOKED, EventType.AGENT_STEP)
        ]
        if not recent_steps:
            return None

        drift_signals = sum(
            1 for e in recent_steps
            if e.payload.get("drift_score", 0) > self.settings.drift_threshold
        )
        if drift_signals >= 3:
            return SafetyAlert(
                session_id=session.id,
                detector_type=DetectorType.TASK_DRIFT,
                severity="warning",
                message=f"Task drift detected: {drift_signals} recent steps diverging from goal",
                trigger_event_id=recent_steps[-1].id,
            )
        return None

    async def detect_budget_overrun(
        self,
        events: list[Event],
        session: Session,
    ) -> SafetyAlert | None:
        if len(events) > self.settings.budget_event_limit:
            return SafetyAlert(
                session_id=session.id,
                detector_type=DetectorType.BUDGET_OVERRUN,
                severity="critical",
                message=f"Budget overrun: {len(events)} events exceed limit of {self.settings.budget_event_limit}",
                trigger_event_id=events[-1].id,
            )
        return None

    async def detect_stall(
        self,
        events: list[Event],
        session: Session,
    ) -> SafetyAlert | None:
        """Detect no forward progress after N events."""
        if len(events) < self.settings.stall_event_threshold:
            return None

        recent = events[-self.settings.stall_event_threshold:]
        progress_types = {
            EventType.TOOL_RESULT,
            EventType.MEMORY_WRITE,
            EventType.CHECKPOINT_CREATED,
            EventType.SESSION_COMPLETED,
        }
        progress_count = sum(1 for e in recent if e.event_type in progress_types)
        if progress_count == 0:
            return SafetyAlert(
                session_id=session.id,
                detector_type=DetectorType.STALLED,
                severity="warning",
                message=f"Stalled: no meaningful progress in last {self.settings.stall_event_threshold} events",
                trigger_event_id=recent[-1].id,
            )
        return None

    async def run_all_detectors(
        self,
        events: list[Event],
        session: Session,
    ) -> list[SafetyAlert]:
        alerts: list[SafetyAlert] = []
        detectors = [
            self.detect_retry_loop(events),
            self.detect_contradiction(events, session),
            self.detect_drift(events, session),
            self.detect_budget_overrun(events, session),
            self.detect_stall(events, session),
        ]
        import asyncio
        results = await asyncio.gather(*detectors)
        for r in results:
            if r is not None:
                await self.save_alert(r)
                alerts.append(r)
        return alerts
