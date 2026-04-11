from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import (
    get_session_svc, get_event_svc, get_checkpoint_svc,
    get_memory_svc, get_recovery_svc, get_agent_runtime,
    get_sandbox_svc,
)
from app.schemas.session import CreateSessionRequest
from app.models.session import Session
from app.workers.agent_runtime import start_agent_task, cancel_agent_task

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=Session)
async def create_session(req: CreateSessionRequest):
    svc = await get_session_svc()
    return await svc.create(req)


@router.get("", response_model=list[Session])
async def list_sessions():
    svc = await get_session_svc()
    return await svc.list_all()


@router.get("/summary")
async def session_summary():
    svc = await get_session_svc()
    return await svc.summary()


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    svc = await get_session_svc()
    session = await svc.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.post("/{session_id}/start")
async def start_session(session_id: str, scenario: str = Query("healthy")):
    svc = await get_session_svc()
    session = await svc.start(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    runtime = await get_agent_runtime()
    start_agent_task(runtime, session, scenario)
    return {"status": "started", "session_id": session_id, "scenario": scenario}


@router.post("/{session_id}/pause")
async def pause_session(session_id: str):
    cancel_agent_task(session_id)
    svc = await get_session_svc()
    session = await svc.pause(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.post("/{session_id}/resume")
async def resume_session(session_id: str, scenario: str = Query("healthy")):
    svc = await get_session_svc()
    session = await svc.resume(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    runtime = await get_agent_runtime()
    start_agent_task(runtime, session, scenario)
    return session


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str):
    cancel_agent_task(session_id)
    svc = await get_session_svc()
    session = await svc.cancel(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


# ─── Events ────────────────────────────────────────────────────

@router.get("/{session_id}/events")
async def get_events(session_id: str, start: int = 0, end: int = -1):
    svc = await get_event_svc()
    return await svc.get_events(session_id, start, end)


# ─── Memory ────────────────────────────────────────────────────

@router.get("/{session_id}/memory")
async def get_memory(
    session_id: str,
    layer: str | None = None,
    status: str | None = None,
):
    from app.models.memory import MemoryLayer, MemoryStatus
    svc = await get_memory_svc()
    l = MemoryLayer(layer) if layer else None
    s = MemoryStatus(status) if status else None
    return await svc.list_by_session(session_id, l, s)


@router.post("/{session_id}/memory")
async def create_memory(session_id: str, req: dict):
    from app.schemas.memory import CreateMemoryRequest
    svc = await get_memory_svc()
    return await svc.create(session_id, CreateMemoryRequest(**req))


# ─── Checkpoints ───────────────────────────────────────────────

@router.get("/{session_id}/checkpoints")
async def get_checkpoints(session_id: str):
    svc = await get_checkpoint_svc()
    return await svc.list_by_session(session_id)


@router.post("/{session_id}/checkpoints")
async def create_checkpoint(session_id: str, label: str = "manual"):
    session_svc = await get_session_svc()
    session = await session_svc.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    cp_svc = await get_checkpoint_svc()
    mem_svc = await get_memory_svc()
    sandbox_svc = await get_sandbox_svc()
    event_svc = await get_event_svc()

    mem_ids = await mem_svc.snapshot_ids(session_id)
    snap_ref = ""
    if session.sandbox_id:
        snap_ref = await sandbox_svc.snapshot(session.sandbox_id)
    event_count = await event_svc.get_event_count(session_id)

    return await cp_svc.create(
        session_id=session_id,
        label=label,
        event_index=event_count,
        plan_snapshot=session.current_plan,
        memory_ids=mem_ids,
        sandbox_ref=snap_ref,
        risk_score=session.risk_score,
        confidence=session.confidence_score,
    )


@router.post("/{session_id}/restore/{checkpoint_id}")
async def restore_checkpoint(session_id: str, checkpoint_id: str):
    svc = await get_recovery_svc()
    return await svc.recover(session_id, checkpoint_id)


# ─── Recovery ──────────────────────────────────────────────────

@router.post("/{session_id}/replay")
async def replay_session(session_id: str, checkpoint_id: str | None = None):
    svc = await get_recovery_svc()
    return await svc.recover(session_id, checkpoint_id)


@router.get("/{session_id}/recovery-report")
async def recovery_report(session_id: str):
    svc = await get_recovery_svc()
    return await svc.get_recovery_report(session_id)


# ─── Sandbox ───────────────────────────────────────────────────

@router.get("/{session_id}/sandbox")
async def get_sandbox_info(session_id: str):
    session_svc = await get_session_svc()
    session = await session_svc.get(session_id)
    if not session or not session.sandbox_id:
        return {"sandbox_id": None, "files": []}
    svc = await get_sandbox_svc()
    files = await svc.list_files(session.sandbox_id)
    return {"sandbox_id": session.sandbox_id, "files": [f.model_dump() for f in files]}


@router.post("/{session_id}/sandbox/exec")
async def sandbox_exec(session_id: str, body: dict):
    session_svc = await get_session_svc()
    session = await session_svc.get(session_id)
    if not session or not session.sandbox_id:
        raise HTTPException(400, "No sandbox for session")
    svc = await get_sandbox_svc()
    result = await svc.execute(session.sandbox_id, body.get("command", "echo hello"))
    return result.model_dump()


@router.get("/{session_id}/sandbox/files")
async def sandbox_files(session_id: str):
    session_svc = await get_session_svc()
    session = await session_svc.get(session_id)
    if not session or not session.sandbox_id:
        return []
    svc = await get_sandbox_svc()
    files = await svc.list_files(session.sandbox_id)
    return [f.model_dump() for f in files]


# ─── Safety Alerts ─────────────────────────────────────────────

@router.get("/{session_id}/alerts")
async def get_alerts(session_id: str):
    from app.api.deps import get_safety_svc
    svc = await get_safety_svc()
    return await svc.list_alerts(session_id)
