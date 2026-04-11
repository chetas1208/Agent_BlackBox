from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.api.deps import get_memory_svc
from app.schemas.memory import UpdateMemoryRequest

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, session_id: str, body: UpdateMemoryRequest):
    svc = await get_memory_svc()
    item = await svc.update(session_id, memory_id, body)
    if not item:
        raise HTTPException(404, "Memory item not found")
    return item


@router.post("/{memory_id}/quarantine")
async def quarantine_memory(memory_id: str, session_id: str):
    svc = await get_memory_svc()
    item = await svc.quarantine(session_id, memory_id)
    if not item:
        raise HTTPException(404, "Memory item not found")
    return item


@router.post("/{memory_id}/promote")
async def promote_memory(memory_id: str, session_id: str):
    svc = await get_memory_svc()
    item = await svc.promote(session_id, memory_id)
    if not item:
        raise HTTPException(404, "Memory item not found")
    return item
