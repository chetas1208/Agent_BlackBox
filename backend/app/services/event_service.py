from __future__ import annotations
import json
from app.models.event import Event, EventType, EventActor, EventSeverity
from app.repositories.redis_repo import RedisRepository


class EventRecorderService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    def _list_key(self, session_id: str) -> str:
        return f"events:{session_id}"

    async def record(self, event: Event) -> Event:
        list_key = self._list_key(event.session_id)
        await self.repo.append_to_list(list_key, event.model_dump_json())
        await self.repo.publish(
            f"events:stream:{event.session_id}",
            event.model_dump_json(),
        )
        return event

    async def emit(
        self,
        session_id: str,
        event_type: EventType,
        summary: str = "",
        actor: EventActor = EventActor.RUNTIME,
        severity: EventSeverity = EventSeverity.INFO,
        payload: dict | None = None,
        related_memory_ids: list[str] | None = None,
        checkpoint_id: str | None = None,
    ) -> Event:
        event = Event(
            session_id=session_id,
            event_type=event_type,
            actor=actor,
            severity=severity,
            summary=summary,
            payload=payload or {},
            related_memory_ids=related_memory_ids or [],
            checkpoint_id=checkpoint_id,
        )
        return await self.record(event)

    async def get_events(
        self,
        session_id: str,
        start: int = 0,
        end: int = -1,
    ) -> list[Event]:
        raw = await self.repo.get_list(self._list_key(session_id), start, end)
        return [Event.model_validate_json(r) for r in raw]

    async def get_event_count(self, session_id: str) -> int:
        return await self.repo.get_list_length(self._list_key(session_id))

    async def get_recent_critical(self, limit: int = 20) -> list[Event]:
        """Get recent critical/error events across all sessions for the dashboard."""
        from app.services.session_service import SessionService
        # This is a simplified approach; in production you'd use a dedicated index
        sessions_ids = await self.repo.list_ids("sessions")
        critical: list[Event] = []
        for sid in sessions_ids[-10:]:  # check last 10 sessions
            events = await self.get_events(sid, -50, -1)
            for e in events:
                if e.severity in (EventSeverity.ERROR, EventSeverity.CRITICAL, EventSeverity.WARNING):
                    critical.append(e)
        critical.sort(key=lambda e: e.created_at, reverse=True)
        return critical[:limit]
