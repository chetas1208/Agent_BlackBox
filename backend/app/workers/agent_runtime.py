"""Simulated agent runtime that executes tasks step-by-step.

Each scenario defines a sequence of realistic agent actions:
planning, tool calls, memory ops, safety checks, and recovery.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from uuid import uuid4

from app.models.session import Session, SessionStatus, SessionStage
from app.models.event import EventType, EventActor, EventSeverity
from app.models.memory import MemoryItem, MemoryLayer, MemoryStatus
from app.services.session_service import SessionService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService
from app.services.checkpoint_service import CheckpointService
from app.services.sandbox_service import SandboxService
from app.services.recovery_service import RecoveryService
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
    ):
        self.session_svc = session_svc
        self.event_svc = event_svc
        self.memory_svc = memory_svc
        self.checkpoint_svc = checkpoint_svc
        self.sandbox_svc = sandbox_svc
        self.safety_svc = safety_svc
        self.recovery_svc = recovery_svc
        self.settings = get_settings()

    async def _delay(self):
        await asyncio.sleep(self.settings.agent_step_delay_ms / 1000)

    async def _update_progress(self, session: Session, progress: int, stage: SessionStage | None = None):
        session.progress_percent = min(progress, 100)
        if stage:
            session.stage = stage
        session.event_count = await self.event_svc.get_event_count(session.id)
        await self.session_svc.update(session)

    async def _create_checkpoint(self, session: Session, label: str) -> str:
        mem_ids = await self.memory_svc.snapshot_ids(session.id)
        snap_ref = ""
        if session.sandbox_id:
            snap_ref = await self.sandbox_svc.snapshot(session.sandbox_id)

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

    async def _write_memory(self, session: Session, layer: MemoryLayer, key: str, value, source: str = "agent", confidence: float = 0.9, tags: list[str] | None = None):
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

    async def _read_memory(self, session: Session, layer: MemoryLayer, key: str) -> MemoryItem | None:
        item = await self.memory_svc.get_by_key(session.id, layer, key)
        await self.event_svc.emit(
            session.id,
            EventType.MEMORY_READ,
            summary=f"Read {layer.value}: {key}" + (" (found)" if item else " (miss)"),
            actor=EventActor.AGENT,
            payload={"layer": layer.value, "key": key, "found": item is not None},
            related_memory_ids=[item.id] if item else [],
        )
        return item

    async def _run_safety_check(self, session: Session) -> bool:
        """Returns True if a safety issue was detected."""
        events = await self.event_svc.get_events(session.id)
        alerts = await self.safety_svc.run_all_detectors(events, session)
        if alerts:
            for alert in alerts:
                severity = EventSeverity.ERROR if alert.severity == "error" else EventSeverity.CRITICAL if alert.severity == "critical" else EventSeverity.WARNING
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
                    payload={"detector": alert.detector_type.value, "alert_id": alert.id},
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

    # ─── Scenario runners ─────────────────────────────────────────

    async def run_healthy(self, session: Session):
        """Scenario 1: clean execution, no failures."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        await self.session_svc.update(session)

        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        await self.session_svc.update(session)

        await self.event_svc.emit(session.id, EventType.SESSION_CREATED, "Session started", EventActor.RUNTIME)
        await self._delay()

        # Planning
        plan = [
            "Examine project structure",
            "Run existing tests",
            "Identify failing component",
            "Apply fix",
            "Verify fix with tests",
        ]
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED, "Generated execution plan",
            EventActor.AGENT, payload={"plan": plan},
        )
        await self._delay()

        # Checkpoint after planning
        await self._create_checkpoint(session, "post-planning")
        await self._delay()

        # Step 1: Examine project
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Listing project files",
            EventActor.AGENT, payload={"command": "ls -la", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "ls -la")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Got project listing",
            EventActor.AGENT, payload={"exit_code": result.exit_code, "stdout": result.stdout},
        )
        await self._write_memory(session, MemoryLayer.WORKING, "project_structure", {"files": ["README.md", "src/", "tests/"]}, tags=["structure"])
        await self._delay()

        # Step 2: Read source
        await self._update_progress(session, 25)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Reading auth module",
            EventActor.AGENT, payload={"command": "cat src/auth.py", "tool": "sandbox_read"},
        )
        content = await self.sandbox_svc.read_file(sandbox_id, "src/auth.py")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Read auth.py",
            EventActor.AGENT, payload={"file": "src/auth.py", "size": len(content)},
        )
        await self._write_memory(session, MemoryLayer.EPISODIC, "read_auth_module", {"content_summary": "Auth module with login function, has TODO for token refresh"}, tags=["auth", "code"])
        await self._delay()

        # Step 3: Run tests
        await self._update_progress(session, 40)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Running test suite",
            EventActor.AGENT, payload={"command": "pytest tests/", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Tests passed",
            EventActor.AGENT, payload={"exit_code": result.exit_code, "stdout": result.stdout},
        )
        await self._write_memory(session, MemoryLayer.WORKING, "test_results", {"passed": True, "output": result.stdout}, confidence=0.95, tags=["tests"])
        await self._delay()

        # Checkpoint mid-execution
        await self._create_checkpoint(session, "mid-execution")
        await self._delay()

        # Step 4: Identify issue via grep
        await self._update_progress(session, 55)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Searching for TODOs",
            EventActor.AGENT, payload={"command": "grep -r 'TODO' src/", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "grep -r 'TODO' src/")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Found TODO items",
            EventActor.AGENT, payload={"stdout": result.stdout},
        )
        await self._write_memory(session, MemoryLayer.SEMANTIC, "identified_issues", {"issues": ["token refresh in auth.py", "rate limiting in api.py"]}, confidence=0.85, tags=["issues", "findings"])
        await self._delay()

        # Step 5: Apply fix
        await self._update_progress(session, 70)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Applying fix to auth module",
            EventActor.AGENT, payload={"tool": "sandbox_write", "file": "src/auth.py"},
        )
        fixed_code = "def login(user, password):\n    token = generate_token(user)\n    schedule_token_refresh(token)\n    return token\n"
        await self.sandbox_svc.write_file(sandbox_id, "src/auth.py", fixed_code)
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Applied token refresh fix",
            EventActor.AGENT, payload={"file": "src/auth.py", "action": "updated"},
        )
        await self._write_memory(session, MemoryLayer.EPISODIC, "applied_fix", {"file": "src/auth.py", "change": "Added token refresh scheduling"}, tags=["fix"])
        await self._delay()

        # Step 6: Verify
        await self._update_progress(session, 85)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Re-running tests after fix",
            EventActor.AGENT, payload={"command": "pytest tests/", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "All tests pass after fix",
            EventActor.AGENT, payload={"exit_code": result.exit_code, "stdout": result.stdout},
        )
        session.confidence_score = 0.95
        await self._delay()

        # Safety check (should be clean)
        await self._run_safety_check(session)

        # Final checkpoint
        await self._create_checkpoint(session, "post-fix-verified")

        # Complete
        await self._update_progress(session, 100, SessionStage.FINISHING)
        session.status = SessionStatus.COMPLETED
        session.outcome = "Successfully identified and fixed token refresh issue in auth module. All tests passing."
        session.ended_at = datetime.utcnow()
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_COMPLETED,
            "Task completed successfully",
            EventActor.RUNTIME,
            payload={"outcome": session.outcome},
        )

    async def run_retry_loop(self, session: Session):
        """Scenario 2: agent gets stuck in a retry loop."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        await self.session_svc.update(session)

        await self.event_svc.emit(session.id, EventType.SESSION_CREATED, "Session started", EventActor.RUNTIME)
        await self._delay()

        plan = ["Run failing tests", "Analyze failure", "Retry with fix", "Verify"]
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(session.id, EventType.PLAN_GENERATED, "Generated plan", EventActor.AGENT, payload={"plan": plan})
        await self._delay()

        await self._create_checkpoint(session, "initial")
        await self._delay()

        # Agent tries the same failing command repeatedly
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        for i in range(4):
            await self.event_svc.emit(
                session.id, EventType.TOOL_INVOKED,
                f"Running failing tests (attempt {i+1})",
                EventActor.AGENT,
                payload={"command": "pytest tests/ --failing", "tool": "sandbox_exec", "attempt": i + 1},
            )
            result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/ --failing")
            await self.event_svc.emit(
                session.id, EventType.TOOL_RESULT,
                f"Tests failed (attempt {i+1})",
                EventActor.AGENT,
                severity=EventSeverity.WARNING,
                payload={"exit_code": result.exit_code, "stderr": result.stderr, "attempt": i + 1},
            )
            await self._update_progress(session, 15 + i * 10)
            await self._delay()

            # Safety check after 3rd retry
            if i >= 2:
                detected = await self._run_safety_check(session)
                if detected:
                    break

        # System pauses execution
        session.status = SessionStatus.PAUSED
        session.stage = SessionStage.IDLE
        session.outcome = "Paused: retry loop detected. Agent repeatedly calling failing test command without progress."
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_PAUSED,
            "Execution paused due to retry loop detection",
            EventActor.SAFETY_ENGINE,
            severity=EventSeverity.ERROR,
        )

    async def run_contradiction(self, session: Session):
        """Scenario 3: stale memory contradiction triggers recovery."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        await self.session_svc.update(session)

        await self.event_svc.emit(session.id, EventType.SESSION_CREATED, "Session started", EventActor.RUNTIME)
        await self._delay()

        plan = ["Check test status", "Review recent changes", "Investigate CI issue", "Fix and verify"]
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(session.id, EventType.PLAN_GENERATED, "Generated plan", EventActor.AGENT, payload={"plan": plan})
        await self._delay()

        # Write initial memory (stale data)
        stale_mem = await self._write_memory(
            session, MemoryLayer.WORKING, "test_status",
            {"passed": True, "output": "All 4 tests passed", "timestamp": "2 hours ago"},
            confidence=0.8,
            tags=["tests", "stale"],
        )
        await self._delay()

        await self._create_checkpoint(session, "initial-with-stale-memory")
        await self._delay()

        # Agent reads stale memory
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

        # Now agent runs actual tests and gets contradiction
        await self._update_progress(session, 35)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Running tests to verify",
            EventActor.AGENT,
            payload={"command": "pytest tests/ --failing", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/ --failing")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT,
            "Tests FAILING — contradicts stored memory",
            EventActor.AGENT,
            severity=EventSeverity.ERROR,
            payload={
                "exit_code": result.exit_code,
                "stderr": result.stderr,
                "contradicts_memory": True,
                "contradiction_detail": "Memory says tests passed, but current run shows test_auth.py::test_login FAILED",
            },
        )
        await self._delay()

        # Safety engine detects contradiction
        events = await self.event_svc.get_events(session.id)
        await self.safety_svc.run_all_detectors(events, session)

        await self.event_svc.emit(
            session.id, EventType.CONTRADICTION_DETECTED,
            "Contradiction: stored test_status says passed, actual result is FAILED",
            EventActor.SAFETY_ENGINE,
            severity=EventSeverity.ERROR,
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

        # Quarantine stale memory
        await self.memory_svc.quarantine(session.id, stale_mem.id)
        await self.event_svc.emit(
            session.id, EventType.MEMORY_QUARANTINED,
            f"Quarantined stale memory: test_status",
            EventActor.SAFETY_ENGINE,
            severity=EventSeverity.WARNING,
            related_memory_ids=[stale_mem.id],
        )
        await self._delay()

        # Create checkpoint before recovery
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
            confidence=0.95,
            tags=["tests", "current"],
        )
        await self._delay()

        # Replan and continue
        new_plan = ["Fix test_auth.py test failure", "Apply code fix", "Verify tests pass"]
        session.current_plan = new_plan
        session.stage = SessionStage.EXECUTING
        await self.session_svc.update(session)
        await self.event_svc.emit(
            session.id, EventType.PLAN_GENERATED,
            "Replanned after recovery",
            EventActor.AGENT,
            payload={"plan": new_plan},
        )
        await self._delay()

        # Fix and verify
        await self._update_progress(session, 70)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Applying fix",
            EventActor.AGENT,
            payload={"tool": "sandbox_write", "file": "tests/test_auth.py"},
        )
        await self.sandbox_svc.write_file(sandbox_id, "tests/test_auth.py", "def test_login():\n    result = login('user', 'pass')\n    assert result is not None\n    assert hasattr(result, 'refresh')\n")
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "Updated test file", EventActor.AGENT)
        await self._delay()

        await self._update_progress(session, 85)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Running tests after fix",
            EventActor.AGENT,
            payload={"command": "pytest tests/", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Tests passing after recovery",
            EventActor.AGENT,
            payload={"exit_code": result.exit_code, "stdout": result.stdout},
        )
        session.confidence_score = 0.9
        session.risk_score = 0.15
        await self._delay()

        await self._create_checkpoint(session, "post-recovery-verified")

        # Complete as recovered
        await self._update_progress(session, 100, SessionStage.FINISHING)
        session.status = SessionStatus.RECOVERED
        session.outcome = "Recovered: detected stale memory contradiction, quarantined bad data, restored checkpoint, and completed task after re-planning."
        session.ended_at = datetime.utcnow()
        await self.session_svc.update(session)

        await self.event_svc.emit(
            session.id, EventType.SESSION_COMPLETED,
            "Task completed after successful recovery",
            EventActor.RECOVERY_ENGINE,
            payload={"outcome": session.outcome},
        )

    async def run_recovery_success(self, session: Session):
        """Scenario 4: agent fails, restores checkpoint, succeeds on second try."""
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        sandbox_id = f"sbx-{session.id[:8]}"
        session.sandbox_id = sandbox_id
        await self.sandbox_svc.create(sandbox_id)
        await self.session_svc.update(session)

        await self.event_svc.emit(session.id, EventType.SESSION_CREATED, "Session started", EventActor.RUNTIME)
        await self._delay()

        plan = ["Analyze repo", "Install dependencies", "Run build", "Fix build errors", "Verify"]
        session.current_plan = plan
        await self._update_progress(session, 5, SessionStage.PLANNING)
        await self.event_svc.emit(session.id, EventType.PLAN_GENERATED, "Generated plan", EventActor.AGENT, payload={"plan": plan})
        await self._delay()

        await self._create_checkpoint(session, "initial")
        await self._delay()

        # Step 1: Analyze
        await self._update_progress(session, 15, SessionStage.EXECUTING)
        await self.event_svc.emit(session.id, EventType.TOOL_INVOKED, "Reading README", EventActor.AGENT, payload={"command": "cat README.md", "tool": "sandbox_exec"})
        result = await self.sandbox_svc.execute(sandbox_id, "cat README.md")
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "Read project docs", EventActor.AGENT, payload={"stdout": result.stdout})
        await self._write_memory(session, MemoryLayer.SEMANTIC, "project_info", {"name": "Project Alpha", "type": "flask app"}, tags=["context"])
        await self._delay()

        # Step 2: Install deps
        await self._update_progress(session, 25)
        await self.event_svc.emit(session.id, EventType.TOOL_INVOKED, "Installing dependencies", EventActor.AGENT, payload={"command": "pip install -r requirements.txt", "tool": "sandbox_exec"})
        result = await self.sandbox_svc.execute(sandbox_id, "pip install -r requirements.txt")
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "Dependencies installed", EventActor.AGENT, payload={"stdout": result.stdout})
        await self._delay()

        await self._create_checkpoint(session, "deps-installed")
        await self._delay()

        # Step 3: First attempt fails
        await self._update_progress(session, 40)
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Running linter",
            EventActor.AGENT, payload={"command": "flake8 src/", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "flake8 src/")
        await self.event_svc.emit(
            session.id, EventType.TOOL_RESULT, "Linter errors found",
            EventActor.AGENT,
            severity=EventSeverity.WARNING,
            payload={"stdout": result.stdout},
        )
        await self._write_memory(session, MemoryLayer.RISK, "linter_failures", {"errors": result.stdout, "critical": True}, tags=["quality"])
        await self._delay()

        # Simulate a bad fix that breaks things more
        await self._update_progress(session, 50)
        await self.event_svc.emit(session.id, EventType.AGENT_STEP, "Attempting aggressive refactor", EventActor.AGENT, payload={"reasoning": "Will rewrite auth module completely"})
        await self.sandbox_svc.write_file(sandbox_id, "src/auth.py", "# BROKEN REFACTOR\nimport nonexistent_module\n")
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "Wrote refactored auth module", EventActor.AGENT, payload={"file": "src/auth.py"})
        await self._delay()

        # Tests now fail badly
        await self.event_svc.emit(
            session.id, EventType.TOOL_INVOKED, "Verifying refactor",
            EventActor.AGENT, payload={"command": "pytest tests/ --failing", "tool": "sandbox_exec"},
        )
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/ --failing")
        await self.event_svc.emit(
            session.id, EventType.FAILURE_DETECTED,
            "Refactor broke tests — import error",
            EventActor.AGENT,
            severity=EventSeverity.ERROR,
            payload={"exit_code": result.exit_code, "stderr": result.stderr},
        )
        session.risk_score = 0.7
        session.confidence_score = 0.3
        await self.session_svc.update(session)
        await self._delay()

        # Recovery: restore to pre-refactor checkpoint
        await self._update_progress(session, 55, SessionStage.RECOVERING)
        await self.event_svc.emit(session.id, EventType.REPLAY_STARTED, "Initiating recovery — restoring to deps-installed checkpoint", EventActor.RECOVERY_ENGINE, severity=EventSeverity.WARNING)
        await self._delay()

        cps = await self.checkpoint_svc.list_by_session(session.id)
        if len(cps) >= 2:
            await self.sandbox_svc.restore(sandbox_id, cps[1].sandbox_snapshot_ref)
            await self.event_svc.emit(
                session.id, EventType.CHECKPOINT_RESTORED,
                f"Restored to checkpoint: {cps[1].label}",
                EventActor.RECOVERY_ENGINE,
                checkpoint_id=cps[1].id,
            )
        await self._delay()

        # Second attempt with conservative fix
        await self._update_progress(session, 65, SessionStage.EXECUTING)
        new_plan = ["Apply minimal linter fixes", "Run tests", "Verify"]
        session.current_plan = new_plan
        await self.session_svc.update(session)
        await self.event_svc.emit(session.id, EventType.PLAN_GENERATED, "Replanned with conservative approach", EventActor.AGENT, payload={"plan": new_plan})
        await self._delay()

        # Conservative fix
        await self._update_progress(session, 75)
        fixed_auth = "def login(user, password):\n    token = generate_token(user)\n    return token\n\n\ndef refresh_token(token):\n    return generate_token(token.user)\n"
        await self.sandbox_svc.write_file(sandbox_id, "src/auth.py", fixed_auth)
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "Applied conservative fix", EventActor.AGENT, payload={"file": "src/auth.py"})
        await self._delay()

        # Tests pass
        await self._update_progress(session, 90)
        await self.event_svc.emit(session.id, EventType.TOOL_INVOKED, "Final test verification", EventActor.AGENT, payload={"command": "pytest tests/", "tool": "sandbox_exec"})
        result = await self.sandbox_svc.execute(sandbox_id, "pytest tests/")
        await self.event_svc.emit(session.id, EventType.TOOL_RESULT, "All tests pass", EventActor.AGENT, payload={"exit_code": result.exit_code, "stdout": result.stdout})
        session.confidence_score = 0.88
        session.risk_score = 0.1
        await self._delay()

        await self.event_svc.emit(session.id, EventType.REPLAY_COMPLETED, "Recovery successful", EventActor.RECOVERY_ENGINE)
        await self._create_checkpoint(session, "recovery-verified")

        # Complete
        await self._update_progress(session, 100, SessionStage.FINISHING)
        session.status = SessionStatus.RECOVERED
        session.outcome = "Recovered: aggressive refactor broke tests, restored checkpoint, applied conservative fix. All tests passing."
        session.ended_at = datetime.utcnow()
        await self.session_svc.update(session)

        await self.event_svc.emit(session.id, EventType.SESSION_COMPLETED, "Task completed after recovery", EventActor.RECOVERY_ENGINE, payload={"outcome": session.outcome})

    async def execute(self, session: Session, scenario: str = "healthy",
                      user_id: str | None = None, github_token: str | None = None):
        """Main entry point.

        If session has a repo_url → use the real LLM agent runtime.
        Otherwise → run the requested demo scenario.
        """
        try:
            if session.repo_url:
                from app.workers.llm_runtime import LLMAgentRuntime
                llm = LLMAgentRuntime(
                    session_svc=self.session_svc,
                    event_svc=self.event_svc,
                    memory_svc=self.memory_svc,
                    checkpoint_svc=self.checkpoint_svc,
                    sandbox_svc=self.sandbox_svc,
                    safety_svc=self.safety_svc,
                    recovery_svc=self.recovery_svc,
                    user_id=user_id,
                    github_token=github_token,
                )
                await llm.run(session)
            else:
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
            await self.session_svc.update(session)
        except Exception as e:
            session.status = SessionStatus.FAILED
            session.outcome = f"Runtime error: {str(e)}"
            session.ended_at = datetime.utcnow()
            await self.session_svc.update(session)
            await self.event_svc.emit(
                session.id, EventType.FAILURE_DETECTED,
                f"Unhandled error: {str(e)}",
                EventActor.RUNTIME,
                severity=EventSeverity.CRITICAL,
            )


def start_agent_task(runtime: AgentRuntime, session: Session, scenario: str = "healthy",
                     user_id: str | None = None, github_token: str | None = None):
    """Launch agent execution as a background asyncio task."""
    task = asyncio.create_task(runtime.execute(session, scenario, user_id=user_id, github_token=github_token))
    _running_tasks[session.id] = task
    return task


def cancel_agent_task(session_id: str) -> bool:
    task = _running_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return True
    return False
