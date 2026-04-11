"""Dependency injection for FastAPI routes."""
from __future__ import annotations

from functools import lru_cache
from app.core.redis import get_redis
from app.repositories.redis_repo import RedisRepository
from app.services.session_service import SessionService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService
from app.services.checkpoint_service import CheckpointService
from app.services.sandbox_service import SandboxService
from app.services.recovery_service import RecoveryService
from app.safety.engine import SafetyEngineService
from app.workers.agent_runtime import AgentRuntime

_repo: RedisRepository | None = None


async def get_repo() -> RedisRepository:
    global _repo
    if _repo is None:
        r = await get_redis()
        _repo = RedisRepository(r)
    return _repo


async def get_session_svc() -> SessionService:
    return SessionService(await get_repo())


async def get_event_svc() -> EventRecorderService:
    return EventRecorderService(await get_repo())


async def get_memory_svc() -> MemoryService:
    return MemoryService(await get_repo())


async def get_checkpoint_svc() -> CheckpointService:
    return CheckpointService(await get_repo())


async def get_sandbox_svc() -> SandboxService:
    return SandboxService()


async def get_safety_svc() -> SafetyEngineService:
    return SafetyEngineService(await get_repo())


async def get_recovery_svc() -> RecoveryService:
    return RecoveryService(
        session_svc=await get_session_svc(),
        event_svc=await get_event_svc(),
        checkpoint_svc=await get_checkpoint_svc(),
        memory_svc=await get_memory_svc(),
        sandbox_svc=await get_sandbox_svc(),
    )


async def get_agent_runtime() -> AgentRuntime:
    return AgentRuntime(
        session_svc=await get_session_svc(),
        event_svc=await get_event_svc(),
        memory_svc=await get_memory_svc(),
        checkpoint_svc=await get_checkpoint_svc(),
        sandbox_svc=await get_sandbox_svc(),
        safety_svc=await get_safety_svc(),
        recovery_svc=await get_recovery_svc(),
    )
