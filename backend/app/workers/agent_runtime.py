"""Agent runtime with structured actions, approval gates, recovery branches,
and postmortem generation.

Each scenario defines a sequence of realistic agent actions: planning, tool
calls, memory ops, safety checks, approval gates, branching recovery, and
postmortem reports.  The architecture supports real Codex/LLM calls when API
keys are present and falls back to simulated data otherwise.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from app.models.session import (
    ExecutionMode,
    ExecutionPhase,
    ProviderStatus,
    Session,
    SessionStage,
    SessionStatus,
)
from app.models.event import EventType, EventActor, EventSeverity
from app.models.memory import MemoryItem, MemoryLayer, MemoryStatus
from app.models.action import AgentAction, ActionType
from app.services.session_service import SessionService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService
from app.services.checkpoint_service import CheckpointService
from app.services.sandbox_service import SandboxService
from app.services.recovery_service import RecoveryService
from app.services.codex_service import CodexService
from app.services.approval_service import ApprovalService
from app.services.branch_service import BranchService
from app.services.postmortem_service import PostmortemService
from app.safety.engine import SafetyEngineService
from app.core.config import get_settings

_running_tasks: dict[str, asyncio.Task] = {}


class AgentRuntime:
    def __init__(
        self,
        session_svc: SessionService,
        event_svc: EventRecorderService,
        memory_svc: MemoryService,
        checkpoint_svc: CheckpointService,
        sandbox_svc: SandboxService,
        safety_svc: SafetyEngineService,
        recovery_svc: RecoveryService,
        codex_svc: CodexService,
        approval_svc: ApprovalService,
        branch_svc: BranchService,
        postmortem_svc: PostmortemService,
    ):
        self.session_svc = session_svc
        self.event_svc = event_svc
        self.memory_svc = memory_svc
        self.checkpoint_svc = checkpoint_svc
        self.sandbox_svc = sandbox_svc
        self.safety_svc = safety_svc
        self.recovery_svc = recovery_svc
        self.codex_svc = codex_svc
        self.approval_svc = approval_svc
        self.branch_svc = branch_svc
        self.postmortem_svc = postmortem_svc
        self.settings = get_settings()

    # ─── Helpers ───────────────────────────────────────────────────────

    async def _delay(self):
        await asyncio.sleep(self.settings.agent_step_delay_ms / 1000)

    def _sync_execution_metadata(self, session: Session) -> None:
        if session.status == SessionStatus.FAILED:
            session.provider_status = ProviderStatus.FAILED
            session.execution_phase = ExecutionPhase.DONE
            return

        if session.status in {
            SessionStatus.COMPLETED,
            SessionStatus.RECOVERED,
            SessionStatus.CANCELLED,
        }:
            session.provider_status = ProviderStatus.READY
            session.execution_phase = ExecutionPhase.DONE
            return

        session.provider_status = (
            ProviderStatus.RUNNING
            if session.status == SessionStatus.RUNNING
            else ProviderStatus.READY
        )
        session.execution_phase = {
            SessionStage.PLANNING: ExecutionPhase.PLANNING,
            SessionStage.EXECUTING: ExecutionPhase.EXECUTING,
            SessionStage.EVALUATING: ExecutionPhase.EXECUTING,
            SessionStage.RECOVERING: ExecutionPhase.RECOVERING,
            SessionStage.CHECKPOINTING: ExecutionPhase.EXECUTING,
            SessionStage.FINISHING: ExecutionPhase.SUMMARIZING,
            SessionStage.IDLE: ExecutionPhase.IDLE,
        }.get(session.stage, ExecutionPhase.IDLE)

    async def _update_progress(
        self, session: Session, progress: int, stage: SessionStage | None = None
    ):
        session.progress_percent = min(progress, 100)
        if stage:
            session.stage = stage
        self._sync_execution_metadata(session)
        session.event_count = await self.event_svc.get_event_count(session.id)
        await self.session_svc.update(session)

    async def _create_checkpoint(self, session: Session, label: str) -> str:
        mem_ids = await self.memory_svc.snapshot_ids(session.id)
        snap_ref = ""
        if session.sandbox_id:
            snap_ref = await self.sandbox_svc.snapshot(
                session.sandbox_id, session.sandbox_profile
            )

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

    async def _write_memory(
        self,
        session: Session,
        layer: MemoryLayer,
        key: str,
        value,
        source: str = "agent",
        confidence: float = 0.9,
        tags: list[str] | None = None,
    ):
        item = MemoryItem(
            session_id=session.id,
            layer=layer,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            tags=tags or [],
        )
        await self.memory_svc.create_item(item)
        await self.event_svc.emit(
            session.id,
            EventType.MEMORY_WRITE,
            summary=f"Write {layer.value}: {key}",
            actor=EventActor.AGENT,
            payload={"layer": layer.value, "key": key, "memory_id": item.id},
            related_memory_ids=[item.id],
        )
        return item

    async def _read_memory(
        self, session: Session, layer: MemoryLayer, key: str
    ) -> MemoryItem | None:
        item = await self.memory_svc.get_by_key(session.id, layer, key)
        await self.event_svc.emit(
            session.id,
            EventType.MEMORY_READ,
            summary=f"Read {layer.value}: {key}"
            + (" (found)" if item else " (miss)"),
            actor=EventActor.AGENT,
            payload={
                "layer": layer.value,
                "key": key,
                "found": item is not None,
            },
            related_memory_ids=[item.id] if item else [],
        )
        return item

    async def _execute_action(
        self, session: Session, action: AgentAction
    ) -> dict:
        """Execute a structured action in sandbox, emit events, return result."""
        await self.event_svc.emit(
            session.id,
            EventType.TOOL_INVOKED,
            f"{action.action_type.value}: {action.rationale}",
            EventActor.AGENT,
            payload={
                "action_id": action.id,
                "action_type": action.action_type.value,
                "tool": action.tool,
                "arguments": action.arguments,
                "risk_level": action.risk_level,
            },
        )

        result: dict = {}
        sandbox_id = session.sandbox_id or ""

        if action.action_type in (
            ActionType.LIST_FILES,
            ActionType.RUN_COMMAND,
            ActionType.RUN_TESTS,
            ActionType.SEARCH_CODE,
        ):
            cmd = action.arguments.get("command", "echo ok")
            res = await self.sandbox_svc.execute(sandbox_id, cmd)
            result = {
                "exit_code": res.exit_code,
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        elif action.action_type == ActionType.READ_FILE:
            path = action.arguments.get("path", "")
            content = await self.sandbox_svc.read_file(sandbox_id, path)
            result = {"file": path, "content": content, "size": len(content)}
        elif action.action_type == ActionType.WRITE_FILE:
            path = action.arguments.get("path", "")
            content = action.arguments.get("content", "")
            await self.sandbox_svc.write_file(sandbox_id, path, content)
            result = {"file": path, "written": True}
        else:
            result = {
                "status": "completed",
                "action_type": action.action_type.value,
            }

        severity = EventSeverity.INFO
        if result.get("exit_code", 0) != 0:
            severity = EventSeverity.WARNING

        await self.event_svc.emit(
            session.id,
            EventType.TOOL_RESULT,
            f"Result: {action.action_type.value}",
            EventActor.AGENT,
            severity=severity,
            payload={"action_id": action.id, **result},
        )
        return result

    async def _run_safety_check(self, session: Session) -> bool:
        """Returns True if a safety issue was detected."""
        events = await self.event_svc.get_events(session.id)
        alerts = await self.safety_svc.run_all_detectors(events, session)
        if alerts:
            for alert in alerts:
                severity = (
                    EventSeverity.CRITICAL
                    if alert.severity == "critical"
                    else EventSeverity.ERROR
                    if alert.severity == "error"
                    else EventSeverity.WARNING
                )
                evt_type = {
                    "retry_loop": EventType.RETRY_DETECTED,
                    "contradiction": EventType.CONTRADICTION_DETECTED,
                    "task_drift": EventType.DRIFT_DETECTED,
                    "budget_overrun": EventType.BUDGET_OVERRUN,
                    "stalled": EventType.STALL_DETECTED,
                }.get(alert.detector_type.value, EventType.FAILURE_DETECTED)

                await self.event_svc.emit(
                    session.id,
                    evt_type,
                    summary=alert.message,
                    actor=EventActor.SAFETY_ENGINE,
                    severity=severity,
                    payload={
                        "detector": alert.detector_type.value,
                        "alert_id": alert.id,
                    },
                )
                session.risk_score = min(1.0, session.risk_score + 0.15)
                await self.event_svc.emit(
                    session.id,
                    EventType.RISK_SCORE_CHANGED,
                    summary=f"Risk score → {session.risk_score:.2f}",
                    actor=EventActor.SAFETY_ENGINE,
                    payload={"risk_score": session.risk_score},
                )
                await self.session_svc.update(session)
            return True
        return False

    async def _request_approval(
        self, session: Session, action: AgentAction
    ) -> None:
        """Create an approval gate, pause the session, and auto-approve in
        demo mode after a short delay."""
        gate = await self.approval_svc.create(
            session_id=session.id,
            action_type=action.action_type.value,
            action_summary=action.rationale,
            rationale=(
                f"Risk: {action.risk_level} | "
                f"Confidence: {action.confidence:.2f} | "
                f"Session risk: {session.risk_score:.2f}"
            ),
            evidence=[action.expected_outcome],
            risk_level=action.risk_level,
            risk_score=session.risk_score,
        )
        session.pending_approval_id = gate.id
        session.status = SessionStatus.PAUSED
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id,
            EventType.POLICY_BLOCKED,
            f"Approval required: {action.action_type.value} — {action.rationale}",
            EventActor.SAFETY_ENGINE,
            severity=EventSeverity.WARNING,
            payload={
                "gate_id": gate.id,
                "action_type": action.action_type.value,
                "risk_level": action.risk_level,
            },
        )
        await self._delay()

        await self.approval_svc.approve(
            session.id, gate.id, resolved_by="auto_demo"
        )
        session.pending_approval_id = None
        session.status = SessionStatus.RUNNING
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id,
            EventType.SESSION_RESUMED,
            f"Approval granted for {action.action_type.value}",
            EventActor.OPERATOR,
            payload={"gate_id": gate.id, "resolved_by": "auto_demo"},
        )

    async def _generate_postmortem(self, session: Session) -> None:
        """Generate an end-of-session postmortem report."""
        pm = await self.postmortem_svc.generate(session)
        session.has_postmortem = True
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id,
            EventType.AGENT_STEP,
            "Postmortem report generated",
            EventActor.RUNTIME,
            payload={
                "postmortem_id": pm.id,
                "sections": len(pm.sections),
            },
        )

    # ─── Scenario runners ─────────────────────────────────────────────

    async def run_healthy(self, session: Session):
        """Scenario 1: clean execution, no failures."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_CREATED,
            "Session started", EventActor.RUNTIME,
        )
        await self._delay()

        # ── Plan ──
        plan = await self.codex_svc.generate_plan(
            session.title, session.description, session.goal,
        )
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED,
            "Generated execution plan", EventActor.AGENT,
            payload={"plan": plan},
        )
        await self._delay()

        await self._create_checkpoint(session, "post-planning")
        await self._delay()

        # ── Step 1: examine project ──
        action = AgentAction(
            action_type=ActionType.LIST_FILES, tool="sandbox_exec",
            arguments={"command": "ls -la"},
            rationale="Examine project structure",
            expected_outcome="Obtain file listing",
            confidence=0.9, risk_level="low",
        )
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.WORKING, "project_structure",
            {"files": ["README.md", "src/", "tests/"]}, tags=["structure"],
        )
        await self.codex_svc.analyze_result(
            {"action_type": action.action_type.value, "tool": action.tool},
            result, [],
        )
        await self._delay()

        # ── Step 2: read source ──
        action = AgentAction(
            action_type=ActionType.READ_FILE, tool="sandbox_read",
            arguments={"path": "src/auth.py"},
            rationale="Read auth module",
            expected_outcome="Understand current authentication code",
            confidence=0.85, risk_level="low",
        )
        await self._update_progress(session, 25)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.EPISODIC, "read_auth_module",
            {"content_summary": "Auth module with login function, has TODO for token refresh"},
            tags=["auth", "code"],
        )
        await self._delay()

        # ── Step 3: run tests ──
        action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Run test suite",
            expected_outcome="All tests pass",
            confidence=0.8, risk_level="low",
        )
        await self._update_progress(session, 40)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.WORKING, "test_results",
            {"passed": True, "output": result.get("stdout", "")},
            confidence=0.95, tags=["tests"],
        )
        await self._delay()

        await self._create_checkpoint(session, "mid-execution")
        await self._delay()

        # ── Step 4: search for TODOs ──
        action = AgentAction(
            action_type=ActionType.SEARCH_CODE, tool="sandbox_exec",
            arguments={"command": "grep -r 'TODO' src/"},
            rationale="Search for TODO items",
            expected_outcome="Identify issues to fix",
            confidence=0.85, risk_level="low",
        )
        await self._update_progress(session, 55)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.SEMANTIC, "identified_issues",
            {"issues": ["token refresh in auth.py", "rate limiting in api.py"]},
            confidence=0.85, tags=["issues", "findings"],
        )
        await self._delay()

        # ── Step 5: apply fix ──
        action = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={
                "path": "src/auth.py",
                "content": (
                    "def login(user, password):\n"
                    "    token = generate_token(user)\n"
                    "    schedule_token_refresh(token)\n"
                    "    return token\n"
                ),
            },
            rationale="Fix token refresh issue in auth module",
            expected_outcome="Code updated with token refresh",
            confidence=0.7, risk_level="medium",
        )
        await self._update_progress(session, 70)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.EPISODIC, "applied_fix",
            {"file": "src/auth.py", "change": "Added token refresh scheduling"},
            tags=["fix"],
        )
        await self._delay()

        # ── Step 6: verify ──
        action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Verify fix passes tests",
            expected_outcome="All tests pass after fix",
            confidence=0.8, risk_level="low",
        )
        await self._update_progress(session, 85)
        result = await self._execute_action(session, action)
        session.confidence_score = 0.95
        await self._delay()

        await self._run_safety_check(session)
        await self._create_checkpoint(session, "post-fix-verified")

        # ── Finish ──
        await self._update_progress(session, 95, SessionStage.FINISHING)
        session.status = SessionStatus.COMPLETED
        session.outcome = (
            "Successfully identified and fixed token refresh issue in auth "
            "module. All tests passing."
        )
        session.ended_at = datetime.utcnow()
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self._generate_postmortem(session)
        await self._update_progress(session, 100)

        await self.event_svc.emit(
            session.id, EventType.SESSION_COMPLETED,
            "Task completed successfully", EventActor.RUNTIME,
            payload={"outcome": session.outcome},
        )

    # ───────────────────────────────────────────────────────────────────

    async def run_retry_loop(self, session: Session):
        """Scenario 2: agent gets stuck in a retry loop."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_CREATED,
            "Session started", EventActor.RUNTIME,
        )
        await self._delay()

        # ── Plan ──
        plan = await self.codex_svc.generate_plan(
            session.title, session.description, session.goal,
            context="Tests are currently failing; need to diagnose.",
        )
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED, "Generated plan",
            EventActor.AGENT, payload={"plan": plan},
        )
        await self._delay()

        await self._create_checkpoint(session, "initial")
        await self._delay()

        # ── Repeated failing test runs ──
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        for i in range(4):
            action = AgentAction(
                action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
                arguments={"command": "pytest tests/ --failing"},
                rationale=f"Running failing tests (attempt {i + 1})",
                expected_outcome="Tests pass",
                confidence=max(0.3, 0.7 - i * 0.15),
                risk_level="low",
            )
            result = await self._execute_action(session, action)
            await self._write_memory(
                session, MemoryLayer.EPISODIC, f"test_attempt_{i + 1}",
                {"attempt": i + 1, "passed": False, "stderr": result.get("stderr", "")},
                confidence=0.95, tags=["tests", "failure"],
            )
            await self._update_progress(session, 15 + i * 10)
            await self._delay()

            if i >= 2:
                detected = await self._run_safety_check(session)
                if detected:
                    break

        # ── Pause ──
        session.status = SessionStatus.PAUSED
        session.stage = SessionStage.IDLE
        session.outcome = (
            "Paused: retry loop detected. Agent repeatedly calling failing "
            "test command without progress."
        )
        session.ended_at = datetime.utcnow()
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self._generate_postmortem(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_PAUSED,
            "Execution paused due to retry loop detection",
            EventActor.SAFETY_ENGINE, severity=EventSeverity.ERROR,
        )

    # ───────────────────────────────────────────────────────────────────

    async def run_contradiction(self, session: Session):
        """Scenario 3: stale memory contradiction triggers recovery."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_CREATED,
            "Session started", EventActor.RUNTIME,
        )
        await self._delay()

        # ── Plan ──
        plan = await self.codex_svc.generate_plan(
            session.title, session.description, session.goal,
            context="Investigating CI failures with potentially stale test cache.",
        )
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED, "Generated plan",
            EventActor.AGENT, payload={"plan": plan},
        )
        await self._delay()

        # Write stale memory (as though cached from earlier run)
        stale_mem = await self._write_memory(
            session, MemoryLayer.WORKING, "test_status",
            {"passed": True, "output": "All 4 tests passed", "timestamp": "2 hours ago"},
            confidence=0.8, tags=["tests", "stale"],
        )
        await self._delay()

        await self._create_checkpoint(session, "initial-with-stale-memory")
        await self._delay()

        # ── Agent reads stale memory and trusts it ──
        await self._update_progress(session, 20, SessionStage.EXECUTING)
        await self._read_memory(session, MemoryLayer.WORKING, "test_status")
        await self._delay()

        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            "Agent believes tests are passing based on cached memory",
            EventActor.AGENT,
            payload={"reasoning": "Memory says tests passed, proceeding with review"},
        )
        await self._delay()

        # ── Run actual tests → contradiction ──
        action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/ --failing"},
            rationale="Running tests to verify cached status",
            expected_outcome="Tests should pass per memory",
            confidence=0.75, risk_level="low",
        )
        await self._update_progress(session, 35)
        result = await self._execute_action(session, action)
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT,
            "Tests FAILING — contradicts stored memory",
            EventActor.AGENT, severity=EventSeverity.ERROR,
            payload={
                "contradicts_memory": True,
                "contradiction_detail": (
                    "Memory says tests passed, but current run shows "
                    "test_auth.py::test_login FAILED"
                ),
            },
        )
        await self._delay()

        # ── Safety engine detects contradiction ──
        events = await self.event_svc.get_events(session.id)
        await self.safety_svc.run_all_detectors(events, session)

        await self.event_svc.emit(
            session.id, EventType.CONTRADICTION_DETECTED,
            "Contradiction: stored test_status says passed, actual result is FAILED",
            EventActor.SAFETY_ENGINE, severity=EventSeverity.ERROR,
            payload={"stale_memory_id": stale_mem.id, "stale_key": "test_status"},
            related_memory_ids=[stale_mem.id],
        )
        session.risk_score = 0.65
        await self.event_svc.emit(
            session.id, EventType.RISK_SCORE_CHANGED,
            f"Risk score → {session.risk_score:.2f}",
            EventActor.SAFETY_ENGINE,
            payload={"risk_score": session.risk_score},
        )
        await self.session_svc.update(session)
        await self._delay()

        # ── Quarantine stale memory ──
        await self.memory_svc.quarantine(session.id, stale_mem.id)
        await self.event_svc.emit(
            session.id, EventType.MEMORY_QUARANTINED,
            "Quarantined stale memory: test_status",
            EventActor.SAFETY_ENGINE, severity=EventSeverity.WARNING,
            related_memory_ids=[stale_mem.id],
        )
        await self._delay()

        # ── Checkpoint before recovery ──
        await self._create_checkpoint(session, "pre-recovery")
        await self._update_progress(session, 50, SessionStage.RECOVERING)
        await self._delay()

        # Restore to initial checkpoint
        cps = await self.checkpoint_svc.list_by_session(session.id)
        if cps:
            await self.recovery_svc.recover(session.id, cps[0].id)
        await self._delay()

        # Write corrected memory
        await self._write_memory(
            session, MemoryLayer.WORKING, "test_status",
            {"passed": False, "output": "FAILED tests/test_auth.py::test_login", "timestamp": "now"},
            confidence=0.95, tags=["tests", "current"],
        )
        await self._delay()

        # ── Replan ──
        new_plan = ["Fix test_auth.py test failure", "Apply code fix", "Verify tests pass"]
        session.current_plan = new_plan
        session.stage = SessionStage.EXECUTING
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED,
            "Replanned after recovery", EventActor.AGENT,
            payload={"plan": new_plan},
        )
        await self._delay()

        # ── Approval gate before risky fix ──
        fix_action = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={"path": "tests/test_auth.py"},
            rationale="Rewrite failing test after memory contradiction recovery",
            expected_outcome="Test file updated to match current auth implementation",
            confidence=0.7, risk_level="high",
            requires_approval=True,
        )
        await self._request_approval(session, fix_action)
        await self._delay()

        # ── Apply fix ──
        await self._update_progress(session, 70)
        fix_action_exec = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={
                "path": "tests/test_auth.py",
                "content": (
                    "def test_login():\n"
                    "    result = login('user', 'pass')\n"
                    "    assert result is not None\n"
                    "    assert hasattr(result, 'refresh')\n"
                ),
            },
            rationale="Apply corrected test file",
            expected_outcome="Test updated", confidence=0.8, risk_level="medium",
        )
        await self._execute_action(session, fix_action_exec)
        await self._delay()

        # ── Verify ──
        verify_action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Running tests after fix",
            expected_outcome="All tests pass",
            confidence=0.85, risk_level="low",
        )
        await self._update_progress(session, 85)
        await self._execute_action(session, verify_action)
        session.confidence_score = 0.9
        session.risk_score = 0.15
        await self._delay()

        await self._run_safety_check(session)
        await self._create_checkpoint(session, "post-recovery-verified")

        # ── Finish ──
        await self._update_progress(session, 95, SessionStage.FINISHING)
        session.status = SessionStatus.RECOVERED
        session.outcome = (
            "Recovered: detected stale memory contradiction, quarantined bad "
            "data, restored checkpoint, and completed task after re-planning."
        )
        session.ended_at = datetime.utcnow()
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self._generate_postmortem(session)
        await self._update_progress(session, 100)

        await self.event_svc.emit(
            session.id, EventType.SESSION_COMPLETED,
            "Task completed after successful recovery",
            EventActor.RECOVERY_ENGINE,
            payload={"outcome": session.outcome},
        )

    # ───────────────────────────────────────────────────────────────────

    async def run_recovery_success(self, session: Session):
        """Scenario 4: agent fails, restores checkpoint, branches into two
        recovery strategies, and selects the winning branch."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_CREATED,
            "Session started", EventActor.RUNTIME,
        )
        await self._delay()

        # ── Plan ──
        plan = await self.codex_svc.generate_plan(
            session.title, session.description, session.goal,
            context="Build is failing, need to fix linter + test errors.",
        )
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED, "Generated plan",
            EventActor.AGENT, payload={"plan": plan},
        )
        await self._delay()

        await self._create_checkpoint(session, "initial")
        await self._delay()

        # ── Step 1: analyze repo ──
        action = AgentAction(
            action_type=ActionType.RUN_COMMAND, tool="sandbox_exec",
            arguments={"command": "cat README.md"},
            rationale="Reading project documentation",
            expected_outcome="Understand project context",
            confidence=0.9, risk_level="low",
        )
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.SEMANTIC, "project_info",
            {"name": "Project Alpha", "type": "flask app"}, tags=["context"],
        )
        await self._delay()

        # ── Step 2: install deps ──
        action = AgentAction(
            action_type=ActionType.RUN_COMMAND, tool="sandbox_exec",
            arguments={"command": "pip install -r requirements.txt"},
            rationale="Installing dependencies",
            expected_outcome="Dependencies installed",
            confidence=0.9, risk_level="low",
        )
        await self._update_progress(session, 25)
        result = await self._execute_action(session, action)
        await self._delay()

        deps_cp_id = await self._create_checkpoint(session, "deps-installed")
        await self._delay()

        # ── Step 3: linter finds errors ──
        action = AgentAction(
            action_type=ActionType.RUN_COMMAND, tool="sandbox_exec",
            arguments={"command": "flake8 src/"},
            rationale="Running linter",
            expected_outcome="Clean lint results",
            confidence=0.6, risk_level="low",
        )
        await self._update_progress(session, 40)
        result = await self._execute_action(session, action)
        await self._write_memory(
            session, MemoryLayer.RISK, "linter_failures",
            {"errors": result.get("stdout", ""), "critical": True},
            tags=["quality"],
        )
        await self._delay()

        # ── Step 4: bad refactor attempt ──
        refactor_action = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={
                "path": "src/auth.py",
                "content": "# BROKEN REFACTOR\nimport nonexistent_module\n",
            },
            rationale="Attempting aggressive refactor of auth module",
            expected_outcome="Complete rewrite of auth module",
            confidence=0.4, risk_level="high",
            requires_approval=True,
        )

        # Approval gate before the risky refactor
        await self._request_approval(session, refactor_action)
        await self._delay()

        await self._update_progress(session, 50)
        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            "Attempting aggressive refactor", EventActor.AGENT,
            payload={"reasoning": "Will rewrite auth module completely"},
        )
        await self._execute_action(session, refactor_action)
        await self._delay()

        # ── Tests fail badly ──
        verify_action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/ --failing"},
            rationale="Verifying refactor",
            expected_outcome="Tests pass",
            confidence=0.3, risk_level="medium",
        )
        result = await self._execute_action(session, verify_action)
        await self.event_svc.emit(
            session.id, EventType.FAILURE_DETECTED,
            "Refactor broke tests — import error",
            EventActor.AGENT, severity=EventSeverity.ERROR,
            payload={
                "exit_code": result.get("exit_code", 1),
                "stderr": result.get("stderr", ""),
            },
        )
        session.risk_score = 0.7
        session.confidence_score = 0.3
        await self.session_svc.update(session)
        await self._delay()

        # ── Recovery: restore checkpoint ──
        await self._update_progress(session, 55, SessionStage.RECOVERING)
        await self.event_svc.emit(
            session.id, EventType.REPLAY_STARTED,
            "Initiating recovery — restoring to deps-installed checkpoint",
            EventActor.RECOVERY_ENGINE, severity=EventSeverity.WARNING,
        )
        await self._delay()

        cps = await self.checkpoint_svc.list_by_session(session.id)
        if len(cps) >= 2:
            await self.sandbox_svc.restore(
                sandbox_id, cps[1].sandbox_snapshot_ref,
            )
            await self.event_svc.emit(
                session.id, EventType.CHECKPOINT_RESTORED,
                f"Restored to checkpoint: {cps[1].label}",
                EventActor.RECOVERY_ENGINE,
                checkpoint_id=cps[1].id,
            )
        await self._delay()

        recovery_cp_id = cps[1].id if len(cps) >= 2 else cps[0].id

        # ── Branch A: retry same approach with narrower scope ──
        branch_a = await self.branch_svc.create(
            session_id=session.id,
            parent_checkpoint_id=recovery_cp_id,
            strategy="retry_narrower_scope",
            description="Retry the refactor with a narrower scope — fix only the linter errors without rewriting.",
            sandbox_id=sandbox_id,
        )
        session.current_branch_id = branch_a.id
        session.total_branches = 1
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            f"Created recovery Branch A: {branch_a.strategy}",
            EventActor.RECOVERY_ENGINE,
            payload={
                "branch_id": branch_a.id,
                "strategy": branch_a.strategy,
                "description": branch_a.description,
            },
        )
        await self._delay()

        # Execute Branch A actions
        a_action = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={
                "path": "src/auth.py",
                "content": (
                    "def login(user, password):\n"
                    "    token = generate_token(user)\n"
                    "    return token\n"
                ),
            },
            rationale="Minimal linter fix — remove unused imports only",
            expected_outcome="Linter errors resolved",
            confidence=0.55, risk_level="medium",
        )
        await self._execute_action(session, a_action)
        await self._delay()

        a_test = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Verify Branch A fix",
            expected_outcome="Tests pass",
            confidence=0.5, risk_level="low",
        )
        a_result = await self._execute_action(session, a_test)
        await self._delay()

        branch_a.event_count = 2
        await self.branch_svc.complete(
            session.id, branch_a.id,
            outcome="Partial fix: linter clean but test_login still failing (missing refresh).",
            confidence=0.55,
        )
        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            f"Branch A completed — confidence {0.55:.2f}",
            EventActor.RECOVERY_ENGINE,
            payload={
                "branch_id": branch_a.id,
                "outcome": "partial fix",
                "confidence": 0.55,
            },
        )
        await self._delay()

        # Restore checkpoint again for Branch B
        if len(cps) >= 2:
            await self.sandbox_svc.restore(
                sandbox_id, cps[1].sandbox_snapshot_ref,
            )

        # ── Branch B: different diagnostic path ──
        branch_b = await self.branch_svc.create(
            session_id=session.id,
            parent_checkpoint_id=recovery_cp_id,
            strategy="different_diagnostic",
            description="Take a different diagnostic path — read test expectations first, then write targeted fix.",
            sandbox_id=sandbox_id,
        )
        session.current_branch_id = branch_b.id
        session.total_branches = 2
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            f"Created recovery Branch B: {branch_b.strategy}",
            EventActor.RECOVERY_ENGINE,
            payload={
                "branch_id": branch_b.id,
                "strategy": branch_b.strategy,
                "description": branch_b.description,
            },
        )
        await self._delay()

        # Branch B: read tests first, then make targeted fix
        b_read = AgentAction(
            action_type=ActionType.READ_FILE, tool="sandbox_read",
            arguments={"path": "tests/test_auth.py"},
            rationale="Read test expectations before fixing",
            expected_outcome="Understand what tests expect",
            confidence=0.85, risk_level="low",
        )
        await self._execute_action(session, b_read)
        await self._write_memory(
            session, MemoryLayer.EPISODIC, "branch_b_test_analysis",
            {"tests_expect": "login returns token with refresh capability"},
            tags=["branch_b", "analysis"],
        )
        await self._delay()

        b_fix = AgentAction(
            action_type=ActionType.WRITE_FILE, tool="sandbox_write",
            arguments={
                "path": "src/auth.py",
                "content": (
                    "def login(user, password):\n"
                    "    token = generate_token(user)\n"
                    "    return token\n\n\n"
                    "def refresh_token(token):\n"
                    "    return generate_token(token.user)\n"
                ),
            },
            rationale="Conservative fix based on test expectations — add refresh_token",
            expected_outcome="Tests pass with refresh support",
            confidence=0.8, risk_level="medium",
        )
        await self._execute_action(session, b_fix)
        await self._delay()

        b_test = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Verify Branch B fix",
            expected_outcome="All tests pass",
            confidence=0.8, risk_level="low",
        )
        b_result = await self._execute_action(session, b_test)
        await self._delay()

        branch_b.event_count = 3
        await self.branch_svc.complete(
            session.id, branch_b.id,
            outcome="Full fix: all tests passing, auth module has both login and refresh_token.",
            confidence=0.88,
        )
        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            f"Branch B completed — confidence {0.88:.2f}",
            EventActor.RECOVERY_ENGINE,
            payload={
                "branch_id": branch_b.id,
                "outcome": "full fix",
                "confidence": 0.88,
            },
        )
        await self._delay()

        # ── Select winner: Branch B ──
        await self.branch_svc.select_winner(session.id, branch_b.id)
        session.current_branch_id = branch_b.id
        await self.session_svc.update(session)

        comparison = await self.branch_svc.compare(session.id)
        await self.event_svc.emit(
            session.id, EventType.AGENT_STEP,
            "Branch comparison complete — Branch B selected as winner",
            EventActor.RECOVERY_ENGINE,
            payload=comparison,
        )
        await self._write_memory(
            session, MemoryLayer.EPISODIC, "branch_selection",
            {
                "winner": branch_b.id,
                "winner_strategy": "different_diagnostic",
                "reason": "Higher confidence and full test coverage",
            },
            tags=["recovery", "branches"],
        )
        await self._delay()

        await self.event_svc.emit(
            session.id, EventType.REPLAY_COMPLETED,
            "Recovery successful — Branch B applied",
            EventActor.RECOVERY_ENGINE,
        )

        # ── Final verify ──
        await self._update_progress(session, 90, SessionStage.EXECUTING)
        final_action = AgentAction(
            action_type=ActionType.RUN_TESTS, tool="sandbox_exec",
            arguments={"command": "pytest tests/"},
            rationale="Final test verification after recovery",
            expected_outcome="All tests pass",
            confidence=0.88, risk_level="low",
        )
        await self._execute_action(session, final_action)
        session.confidence_score = 0.88
        session.risk_score = 0.1
        await self._delay()

        await self._run_safety_check(session)
        await self._create_checkpoint(session, "recovery-verified")

        # ── Finish ──
        await self._update_progress(session, 95, SessionStage.FINISHING)
        session.status = SessionStatus.RECOVERED
        session.outcome = (
            "Recovered: aggressive refactor broke tests, restored checkpoint, "
            "explored two recovery branches (retry-narrower vs. "
            "different-diagnostic). Branch B (different-diagnostic) selected "
            "as winner — all tests passing."
        )
        session.ended_at = datetime.utcnow()
        self._sync_execution_metadata(session)
        await self.session_svc.update(session)

        await self._generate_postmortem(session)
        await self._update_progress(session, 100)

        await self.event_svc.emit(
            session.id, EventType.SESSION_COMPLETED,
            "Task completed after recovery",
            EventActor.RECOVERY_ENGINE,
            payload={"outcome": session.outcome},
        )

    # ─── Dispatcher ────────────────────────────────────────────────────

    async def execute(self, session: Session, scenario: str = "healthy"):
        """Main entry point: run a scenario for the given session."""
        try:
            runners = {
                "healthy": self.run_healthy,
                "retry_loop": self.run_retry_loop,
                "contradiction": self.run_contradiction,
                "recovery": self.run_recovery_success,
            }
            runner = runners.get(scenario, self.run_healthy)
            await runner(session)
        except asyncio.CancelledError:
            session.status = SessionStatus.CANCELLED
            session.ended_at = datetime.utcnow()
            self._sync_execution_metadata(session)
            await self.session_svc.update(session)
        except Exception as e:
            session.status = SessionStatus.FAILED
            session.outcome = f"Runtime error: {str(e)}"
            session.ended_at = datetime.utcnow()
            self._sync_execution_metadata(session)
            await self.session_svc.update(session)
            await self.event_svc.emit(
                session.id, EventType.FAILURE_DETECTED,
                f"Unhandled error: {str(e)}",
                EventActor.RUNTIME, severity=EventSeverity.CRITICAL,
            )


def start_agent_task(
    runtime: AgentRuntime, session: Session, scenario: str = "healthy"
):
    """Launch agent execution as a background asyncio task."""
    task = asyncio.create_task(runtime.execute(session, scenario))
    _running_tasks[session.id] = task
    return task


def cancel_agent_task(session_id: str) -> bool:
    task = _running_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return True
    return False
