from __future__ import annotations

import json
from datetime import datetime

from app.models.artifact import ArtifactType
from app.models.event import EventActor, EventSeverity, EventType
from app.models.memory import MemoryItem, MemoryLayer
from app.models.session import (
    ExecutionMode,
    ExecutionPhase,
    ProviderStatus,
    Session,
    SessionStage,
    SessionStatus,
)
from app.providers.codex_provider import CodexProvider, CodexActionType, CodexPlan
from app.services.artifact_service import ArtifactService
from app.services.checkpoint_service import CheckpointService
from app.services.event_service import EventRecorderService
from app.services.execution_guard_service import ExecutionGuardError, ExecutionGuardService
from app.services.memory_service import MemoryService
from app.services.redis_ops_service import RedisOpsService
from app.services.recovery_service import RecoveryService
from app.services.repo_bootstrap_service import RepoBootstrapResult, RepoBootstrapService
from app.services.sandbox_service import SandboxService
from app.services.session_service import SessionService
from app.safety.engine import SafetyEngineService
from app.core.config import get_settings


class RealExecutionOrchestrator:
    def __init__(
        self,
        session_svc: SessionService,
        event_svc: EventRecorderService,
        memory_svc: MemoryService,
        checkpoint_svc: CheckpointService,
        sandbox_svc: SandboxService,
        safety_svc: SafetyEngineService,
        recovery_svc: RecoveryService,
        artifact_svc: ArtifactService,
        redis_ops_svc: RedisOpsService,
        guard_svc: ExecutionGuardService,
        repo_bootstrap_svc: RepoBootstrapService,
        codex_provider: CodexProvider,
    ):
        self.session_svc = session_svc
        self.event_svc = event_svc
        self.memory_svc = memory_svc
        self.checkpoint_svc = checkpoint_svc
        self.sandbox_svc = sandbox_svc
        self.safety_svc = safety_svc
        self.recovery_svc = recovery_svc
        self.artifact_svc = artifact_svc
        self.redis_ops_svc = redis_ops_svc
        self.guard_svc = guard_svc
        self.repo_bootstrap_svc = repo_bootstrap_svc
        self.codex_provider = codex_provider
        self.settings = get_settings()

    def validate_create_request(self, execution_mode: ExecutionMode, repo_url: str | None) -> list[str]:
        if execution_mode != ExecutionMode.REAL:
            return []
        errors = self.guard_svc.configuration_errors()
        if repo_url:
            try:
                self.guard_svc.validate_repo_url(repo_url)
            except ExecutionGuardError as exc:
                errors.append(str(exc))
        return errors

    async def _update_session(
        self,
        session: Session,
        *,
        progress: int | None = None,
        stage: SessionStage | None = None,
        phase: ExecutionPhase | None = None,
        provider_status: ProviderStatus | None = None,
        last_error: str | None = None,
    ) -> Session:
        if progress is not None:
            session.progress_percent = min(progress, 100)
        if stage is not None:
            session.stage = stage
        if phase is not None:
            session.execution_phase = phase
        if provider_status is not None:
            session.provider_status = provider_status
        if last_error is not None:
            session.last_error = last_error
        session.event_count = await self.event_svc.get_event_count(session.id)
        return await self.session_svc.update(session)

    async def _create_checkpoint(self, session: Session, label: str) -> str:
        mem_ids = await self.memory_svc.snapshot_ids(session.id)
        snap_ref = ""
        if session.sandbox_id:
            snap_ref = await self.sandbox_svc.snapshot(session.sandbox_id, session.sandbox_profile)

        cp = await self.checkpoint_svc.create(
            session_id=session.id,
            label=label,
            event_index=await self.event_svc.get_event_count(session.id),
            plan_snapshot=session.current_plan,
            memory_ids=mem_ids,
            sandbox_ref=snap_ref,
            risk_score=session.risk_score,
            confidence=session.confidence_score,
        )
        session.last_checkpoint_id = cp.id
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id,
            EventType.CHECKPOINT_CREATED,
            summary=f"Checkpoint: {label}",
            actor=EventActor.RUNTIME,
            checkpoint_id=cp.id,
        )
        return cp.id

    async def _write_memory(self, session: Session, layer: MemoryLayer, key: str, value: dict | str | list, source: str = "runtime") -> MemoryItem:
        item = MemoryItem(
            session_id=session.id,
            layer=layer,
            key=key,
            value=value,
            source=source,
        )
        await self.memory_svc.create_item(item)
        await self.event_svc.emit(
            session.id,
            EventType.MEMORY_WRITE,
            summary=f"Write {layer.value}: {key}",
            actor=EventActor.RUNTIME,
            payload={"layer": layer.value, "key": key, "memory_id": item.id},
            related_memory_ids=[item.id],
        )
        return item

    async def _execute_command(self, session: Session, bootstrap: RepoBootstrapResult, command: str, transcript: list[dict]) -> tuple[int, str, str]:
        approved = self.guard_svc.validate_command(command)
        await self.event_svc.emit(
            session.id,
            EventType.TOOL_INVOKED,
            summary=approved,
            actor=EventActor.AGENT,
            payload={"command": approved, "tool": "sandbox_exec", "working_dir": bootstrap.working_dir},
        )
        result = await self.sandbox_svc.execute(
            session.sandbox_id or "",
            approved,
            profile=session.sandbox_profile,
            working_dir=bootstrap.working_dir,
            timeout_ms=self.settings.command_timeout_ms,
        )
        stdout = self.guard_svc.truncate_output(result.stdout)
        stderr = self.guard_svc.truncate_output(result.stderr)
        transcript.append({
            "type": "command",
            "command": approved,
            "exit_code": result.exit_code,
            "stdout": stdout,
            "stderr": stderr,
        })
        await self.event_svc.emit(
            session.id,
            EventType.TOOL_RESULT,
            summary=f"Command finished: {approved}",
            actor=EventActor.AGENT,
            severity=EventSeverity.INFO if result.exit_code == 0 else EventSeverity.WARNING,
            payload={"command": approved, "exit_code": result.exit_code, "stdout": stdout, "stderr": stderr},
        )
        return result.exit_code, stdout, stderr

    async def _attempt_recovery(self, session: Session, notes: str, updated_plan: list[str]) -> Session:
        await self._update_session(
            session,
            stage=SessionStage.RECOVERING,
            phase=ExecutionPhase.RECOVERING,
            provider_status=ProviderStatus.RUNNING,
        )
        await self.recovery_svc.recover(session.id, session.last_checkpoint_id)
        refreshed = await self.session_svc.get(session.id)
        if refreshed is None:
            return session
        refreshed.current_plan = updated_plan or refreshed.current_plan
        refreshed.execution_phase = ExecutionPhase.PLANNING
        refreshed.stage = SessionStage.PLANNING
        await self.session_svc.update(refreshed)
        if updated_plan:
            await self.event_svc.emit(
                refreshed.id,
                EventType.PLAN_GENERATED,
                summary=f"Replanned after recovery: {notes or 'sandbox recovery'}",
                actor=EventActor.RECOVERY_ENGINE,
                payload={"plan": updated_plan},
            )
        return refreshed

    async def _collect_diff_artifact(self, session: Session, bootstrap: RepoBootstrapResult) -> None:
        if not session.sandbox_id:
            return
        for title, command in (
            ("Git Diff Stat", "git diff --stat"),
            ("Git Diff", "git diff --unified=1"),
        ):
            try:
                _, stdout, stderr = await self._execute_command(session, bootstrap, command, [])
            except ExecutionGuardError:
                continue
            content = stdout or stderr
            if content.strip():
                await self.artifact_svc.create(
                    session.id,
                    ArtifactType.DIFF,
                    title=title,
                    content=content[: self.settings.max_artifact_preview_chars],
                )

    async def _finalize(self, session: Session, transcript: list[dict], recovered: bool) -> Session:
        summary = await self.codex_provider.summarize_run(
            {
                "title": session.title,
                "goal": session.goal,
                "repo_url": session.repo_url,
                "transcript": transcript[-12:],
                "plan": session.current_plan,
                "recovered": recovered,
            }
        )
        await self.artifact_svc.create(
            session.id,
            ArtifactType.COMMAND_LOG,
            title="Command Log",
            content=json.dumps(transcript, indent=2),
            content_type="application/json",
        )
        await self.artifact_svc.create(
            session.id,
            ArtifactType.SUMMARY,
            title="Execution Summary",
            content=summary.summary,
            metadata={"key_changes": summary.key_changes, "follow_up": summary.follow_up},
        )
        await self.artifact_svc.create(
            session.id,
            ArtifactType.FINAL_RESULT,
            title="Final Result",
            content=summary.outcome,
        )
        await self._write_memory(
            session,
            MemoryLayer.SEMANTIC,
            "final_summary",
            {
                "summary": summary.summary,
                "outcome": summary.outcome,
                "key_changes": summary.key_changes,
            },
            source="codex",
        )

        await self._create_checkpoint(session, "final")
        session.outcome = summary.outcome
        session.status = SessionStatus.RECOVERED if recovered else SessionStatus.COMPLETED
        session.stage = SessionStage.FINISHING
        session.execution_phase = ExecutionPhase.DONE
        session.provider_status = ProviderStatus.READY
        session.ended_at = datetime.utcnow()
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id,
            EventType.SESSION_COMPLETED,
            summary="Real execution completed",
            actor=EventActor.RUNTIME,
            payload={"outcome": summary.outcome, "recovered": recovered},
        )
        await self.redis_ops_svc.set_run_state(session.id, {"status": "completed", "recovered": recovered})
        return session

    async def _fail(self, session: Session, message: str) -> None:
        session.status = SessionStatus.FAILED
        session.stage = SessionStage.IDLE
        session.execution_phase = ExecutionPhase.DONE
        session.provider_status = ProviderStatus.FAILED
        session.last_error = message
        session.outcome = message
        session.ended_at = datetime.utcnow()
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id,
            EventType.FAILURE_DETECTED,
            summary=message,
            actor=EventActor.RUNTIME,
            severity=EventSeverity.ERROR,
        )
        await self.redis_ops_svc.set_run_state(session.id, {"status": "failed", "error": message})

    async def run(self, session: Session) -> None:
        if session.execution_mode != ExecutionMode.REAL:
            raise ValueError("RealExecutionOrchestrator can only run real sessions")

        validation_errors = self.validate_create_request(session.execution_mode, session.repo_url)
        if validation_errors:
            await self._fail(session, "; ".join(validation_errors))
            return

        acquired = await self.redis_ops_svc.acquire_session_lock(session.id)
        if not acquired:
            await self._fail(session, "Another execution is already active for this session")
            return

        recovered = False
        transcript: list[dict] = []
        try:
            allowed, remaining = await self.redis_ops_svc.check_rate_limit()
            if not allowed:
                raise RuntimeError("Rate limit exceeded for real execution")
            await self.redis_ops_svc.set_run_state(session.id, {"status": "starting", "remaining_quota": remaining})

            if session.idempotency_key:
                created, existing = await self.redis_ops_svc.register_idempotency(session.idempotency_key, session.id)
                if not created and existing != session.id:
                    raise RuntimeError(f"Duplicate idempotency key already used by session {existing}")

            if not session.sandbox_id:
                session.sandbox_id = f"sbx-{session.id[:8]}"
            await self._update_session(
                session,
                progress=5,
                stage=SessionStage.PLANNING,
                phase=ExecutionPhase.BOOTSTRAPPING,
                provider_status=ProviderStatus.RUNNING,
            )
            await self.sandbox_svc.create(session.sandbox_id, session.sandbox_profile)
            await self.event_svc.emit(
                session.id,
                EventType.SESSION_CREATED,
                summary="Real session started",
                actor=EventActor.RUNTIME,
                payload={"repo_url": session.repo_url, "execution_mode": session.execution_mode.value},
            )

            bootstrap = await self.repo_bootstrap_svc.bootstrap(session)
            await self._write_memory(
                session,
                MemoryLayer.SEMANTIC,
                "repo_context",
                {
                    "repo_url": bootstrap.repo_url,
                    "repo_ref": bootstrap.repo_ref,
                    "git_status": bootstrap.git_status,
                    "file_listing": bootstrap.file_listing[: self.settings.max_artifact_preview_chars],
                },
                source="bootstrap",
            )
            await self.artifact_svc.create(
                session.id,
                ArtifactType.FILE_PREVIEW,
                title="Repository Snapshot",
                content=bootstrap.file_listing[: self.settings.max_artifact_preview_chars],
                path=bootstrap.working_dir,
            )

            await self._update_session(session, progress=15, stage=SessionStage.PLANNING, phase=ExecutionPhase.PLANNING)
            cache_key = f"{session.repo_url}:{session.repo_ref}:{session.goal}:{session.task_type.value}"
            cached_plan = await self.redis_ops_svc.get_cached_plan(cache_key)
            if cached_plan:
                plan = CodexPlan.model_validate(cached_plan)
            else:
                plan = await self.codex_provider.plan_task(
                    {
                        "title": session.title,
                        "description": session.description,
                        "goal": session.goal,
                        "task_type": session.task_type.value,
                        "repo_url": bootstrap.repo_url,
                        "repo_ref": bootstrap.repo_ref,
                        "git_status": bootstrap.git_status,
                        "file_listing": bootstrap.file_listing[: self.settings.max_artifact_preview_chars],
                    }
                )
                await self.redis_ops_svc.cache_plan(cache_key, plan.model_dump())

            session.current_plan = plan.steps
            await self.session_svc.update(session)
            await self.event_svc.emit(
                session.id,
                EventType.PLAN_GENERATED,
                summary=plan.summary,
                actor=EventActor.AGENT,
                payload={"plan": plan.steps, "risks": plan.risks, "done_when": plan.done_when},
            )
            await self._create_checkpoint(session, "post-bootstrap")

            for step_index in range(self.settings.task_max_steps):
                await self._update_session(
                    session,
                    progress=min(20 + step_index * 12, 85),
                    stage=SessionStage.EXECUTING,
                    phase=ExecutionPhase.EXECUTING,
                )
                action = await self.codex_provider.choose_next_action(
                    {
                        "title": session.title,
                        "goal": session.goal,
                        "plan": session.current_plan,
                        "step_index": step_index,
                        "repo_url": bootstrap.repo_url,
                        "repo_ref": bootstrap.repo_ref,
                        "working_dir": bootstrap.working_dir,
                        "transcript": transcript[-8:],
                    }
                )

                if action.action_type == CodexActionType.FINISH:
                    transcript.append({"type": "finish", "summary": action.summary, "rationale": action.rationale})
                    break

                if action.action_type == CodexActionType.READ_FILE:
                    if not action.path:
                        raise RuntimeError("Codex selected read_file without a path")
                    content = await self.sandbox_svc.read_file(session.sandbox_id or "", action.path, session.sandbox_profile)
                    content = self.guard_svc.truncate_output(content)
                    transcript.append({"type": "read_file", "path": action.path, "content": content})
                    await self.event_svc.emit(
                        session.id,
                        EventType.TOOL_RESULT,
                        summary=action.summary or f"Read file: {action.path}",
                        actor=EventActor.AGENT,
                        payload={"path": action.path, "content": content},
                    )
                    await self.artifact_svc.create(
                        session.id,
                        ArtifactType.FILE_PREVIEW,
                        title=f"File Preview: {action.path}",
                        content=content[: self.settings.max_artifact_preview_chars],
                        path=action.path,
                    )
                    continue

                if action.action_type == CodexActionType.WRITE_FILE:
                    if not action.path or action.content is None:
                        raise RuntimeError("Codex selected write_file without a path or content")
                    self.guard_svc.validate_write_target(action.path, action.content)
                    await self.event_svc.emit(
                        session.id,
                        EventType.TOOL_INVOKED,
                        summary=action.summary or f"Write file: {action.path}",
                        actor=EventActor.AGENT,
                        payload={"path": action.path, "tool": "sandbox_write"},
                    )
                    await self.sandbox_svc.write_file(session.sandbox_id or "", action.path, action.content, session.sandbox_profile)
                    transcript.append({"type": "write_file", "path": action.path, "content": action.content[:2000]})
                    await self.event_svc.emit(
                        session.id,
                        EventType.TOOL_RESULT,
                        summary=f"Wrote file: {action.path}",
                        actor=EventActor.AGENT,
                        payload={"path": action.path},
                    )
                    await self.artifact_svc.create(
                        session.id,
                        ArtifactType.FILE_PREVIEW,
                        title=f"Written File: {action.path}",
                        content=action.content[: self.settings.max_artifact_preview_chars],
                        path=action.path,
                    )
                    await self._create_checkpoint(session, f"write-{step_index + 1}")
                    continue

                if action.action_type == CodexActionType.RUN_COMMAND:
                    if not action.command:
                        raise RuntimeError("Codex selected run_command without a command")
                    exit_code, stdout, stderr = await self._execute_command(session, bootstrap, action.command, transcript)
                    if exit_code != 0:
                        reflection = await self.codex_provider.reflect_on_result(
                            {
                                "title": session.title,
                                "goal": session.goal,
                                "plan": session.current_plan,
                                "failed_command": action.command,
                                "stdout": stdout,
                                "stderr": stderr,
                                "transcript": transcript[-6:],
                            }
                        )
                        if not recovered and session.last_checkpoint_id:
                            recovered = True
                            session = await self._attempt_recovery(session, reflection.notes, reflection.updated_plan)
                            continue
                        if reflection.should_replan and reflection.updated_plan:
                            session.current_plan = reflection.updated_plan
                            await self.session_svc.update(session)
                            await self.event_svc.emit(
                                session.id,
                                EventType.PLAN_GENERATED,
                                summary="Updated plan after command failure",
                                actor=EventActor.AGENT,
                                payload={"plan": reflection.updated_plan, "notes": reflection.notes},
                            )
                            continue
                        raise RuntimeError(stderr or stdout or f"Command failed: {action.command}")

                if (step_index + 1) % self.settings.safety_check_interval == 0:
                    alerts = await self.safety_svc.run_all_detectors(await self.event_svc.get_events(session.id), session)
                    if alerts and not recovered and session.last_checkpoint_id:
                        recovered = True
                        session = await self._attempt_recovery(session, "Safety recovery", session.current_plan)

            await self._update_session(
                session,
                progress=90,
                stage=SessionStage.FINISHING,
                phase=ExecutionPhase.SUMMARIZING,
                provider_status=ProviderStatus.RUNNING,
            )
            await self._collect_diff_artifact(session, bootstrap)
            await self._finalize(session, transcript, recovered)
        except Exception as exc:
            await self._fail(session, str(exc))
        finally:
            await self.redis_ops_svc.release_session_lock(session.id)
