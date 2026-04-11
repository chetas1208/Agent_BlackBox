"""Dependency injection for FastAPI routes."""
from __future__ import annotations

from app.core.redis import get_redis
from app.repositories.redis_repo import RedisRepository
from app.services.session_service import SessionService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService
from app.services.checkpoint_service import CheckpointService
from app.services.sandbox_service import SandboxService
from app.services.recovery_service import RecoveryService
from app.services.artifact_service import ArtifactService
from app.services.redis_ops_service import RedisOpsService
from app.services.execution_guard_service import ExecutionGuardService
from app.services.repo_bootstrap_service import RepoBootstrapService
from app.services.real_execution_orchestrator import RealExecutionOrchestrator
from app.providers.codex_provider import CodexProvider
from app.safety.engine import SafetyEngineService

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


async def get_artifact_svc() -> ArtifactService:
    return ArtifactService(await get_repo())


async def get_redis_ops_svc() -> RedisOpsService:
    return RedisOpsService(await get_redis())


async def get_execution_guard_svc() -> ExecutionGuardService:
    return ExecutionGuardService()


async def get_codex_provider() -> CodexProvider:
    return CodexProvider()


async def get_repo_bootstrap_svc() -> RepoBootstrapService:
    return RepoBootstrapService(
        sandbox_svc=await get_sandbox_svc(),
        guard_svc=await get_execution_guard_svc(),
    )


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


async def get_real_execution_orchestrator() -> RealExecutionOrchestrator:
    return RealExecutionOrchestrator(
        session_svc=await get_session_svc(),
        event_svc=await get_event_svc(),
        memory_svc=await get_memory_svc(),
        checkpoint_svc=await get_checkpoint_svc(),
        sandbox_svc=await get_sandbox_svc(),
        safety_svc=await get_safety_svc(),
        recovery_svc=await get_recovery_svc(),
        artifact_svc=await get_artifact_svc(),
        redis_ops_svc=await get_redis_ops_svc(),
        guard_svc=await get_execution_guard_svc(),
        repo_bootstrap_svc=await get_repo_bootstrap_svc(),
        codex_provider=await get_codex_provider(),
    )


async def get_approval_svc():
    from app.services.approval_service import ApprovalService
    return ApprovalService(await get_repo())


async def get_branch_svc():
    from app.services.branch_service import BranchService
    return BranchService(await get_repo())


async def get_codex_svc():
    from app.services.codex_service import CodexService
    return CodexService()


async def get_postmortem_svc():
    from app.services.postmortem_service import PostmortemService
    return PostmortemService(
        repo=await get_repo(),
        event_svc=await get_event_svc(),
        memory_svc=await get_memory_svc(),
        checkpoint_svc=await get_checkpoint_svc(),
        branch_svc=await get_branch_svc(),
    )


async def get_agent_runtime():
    from app.workers.agent_runtime import AgentRuntime
    return AgentRuntime(
        session_svc=await get_session_svc(),
        event_svc=await get_event_svc(),
        memory_svc=await get_memory_svc(),
        checkpoint_svc=await get_checkpoint_svc(),
        sandbox_svc=await get_sandbox_svc(),
        safety_svc=await get_safety_svc(),
        recovery_svc=await get_recovery_svc(),
        codex_svc=await get_codex_svc(),
        approval_svc=await get_approval_svc(),
        branch_svc=await get_branch_svc(),
        postmortem_svc=await get_postmortem_svc(),
    )
