from __future__ import annotations
from fastapi import APIRouter
from app.api.deps import get_session_svc, get_event_svc

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard():
    session_svc = await get_session_svc()
    event_svc = await get_event_svc()

    summary = await session_svc.summary()
    recent_sessions = await session_svc.list_all()
    critical_events = await event_svc.get_recent_critical(20)

    return {
        "summary": summary.model_dump(),
        "recent_sessions": [s.model_dump() for s in recent_sessions[:10]],
        "critical_events": [e.model_dump() for e in critical_events],
    }
