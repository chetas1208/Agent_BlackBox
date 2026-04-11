"""Real LLM-powered agent runtime using OpenAI tool-calling + Blaxel sandboxes.

Flow:
  1. Create Blaxel sandbox
  2. Clone the user's GitHub repo into /workspace
  3. Run an OpenAI tool-calling loop (run_command / read_file / write_file / list_files / task_complete)
  4. After every tool call: record event, write memory, run safety checks, auto-checkpoint
  5. On safety alert: pause session (retry-loop) or trigger recovery (contradiction/failure)
  6. Loop ends when LLM calls `task_complete` or max iterations is reached
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from uuid import uuid4

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.models.event import EventType, EventActor, EventSeverity
from app.models.memory import MemoryItem, MemoryLayer
from app.models.session import Session, SessionStatus, SessionStage
from app.services.checkpoint_service import CheckpointService
from app.services.event_service import EventRecorderService
from app.services.memory_service import MemoryService
from app.services.recovery_service import RecoveryService
from app.services.sandbox_service import SandboxService
from app.services.session_service import SessionService
from app.safety.engine import SafetyEngineService

# ── Tool definitions sent to OpenAI ──────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the sandbox and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to /workspace"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file in the sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to /workspace"},
                    "content": {"type": "string", "description": "File content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to /workspace (default: .)",
                        "default": ".",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_complete",
            "description": "Signal that the task is fully complete. Call this when done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "A concise summary of what was accomplished",
                    }
                },
                "required": ["summary"],
            },
        },
    },
]


class LLMAgentRuntime:
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
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ── Helpers ──────────────────────────────────────────────────

    async def _emit(self, session_id: str, event_type: EventType, summary: str,
                    actor: EventActor = EventActor.AGENT,
                    severity: EventSeverity = EventSeverity.INFO,
                    payload: dict | None = None):
        await self.event_svc.emit(session_id, event_type, summary, actor,
                                  severity=severity, payload=payload or {})

    async def _write_memory(self, session: Session, layer: MemoryLayer,
                             key: str, value, confidence: float = 0.9,
                             tags: list[str] | None = None):
        item = MemoryItem(
            session_id=session.id,
            layer=layer,
            key=key,
            value=value,
            source="agent",
            confidence=confidence,
            tags=tags or [],
        )
        await self.memory_svc.create_item(item)
        await self._emit(
            session.id, EventType.MEMORY_WRITE,
            f"Write {layer.value}: {key}",
            EventActor.AGENT,
            payload={"layer": layer.value, "key": key},
        )
        return item

    async def _checkpoint(self, session: Session, label: str) -> str:
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
        await self._emit(session.id, EventType.CHECKPOINT_CREATED,
                         f"Checkpoint: {label}", EventActor.RUNTIME,
                         payload={"checkpoint_id": cp.id})
        return cp.id

    async def _run_safety_check(self, session: Session) -> bool:
        events = await self.event_svc.get_events(session.id)
        alerts = await self.safety_svc.run_all_detectors(events, session)
        if not alerts:
            return False
        for alert in alerts:
            sev_map = {"error": EventSeverity.ERROR, "critical": EventSeverity.CRITICAL,
                       "warning": EventSeverity.WARNING}
            sev = sev_map.get(alert.severity, EventSeverity.WARNING)
            type_map = {
                "retry_loop": EventType.RETRY_DETECTED,
                "contradiction": EventType.CONTRADICTION_DETECTED,
                "task_drift": EventType.DRIFT_DETECTED,
                "budget_overrun": EventType.BUDGET_OVERRUN,
                "stalled": EventType.STALL_DETECTED,
            }
            evt_type = type_map.get(alert.detector_type.value, EventType.FAILURE_DETECTED)
            await self._emit(session.id, evt_type, alert.message,
                             EventActor.SAFETY_ENGINE, sev,
                             payload={"detector": alert.detector_type.value})
            session.risk_score = min(1.0, session.risk_score + 0.15)
            await self._emit(session.id, EventType.RISK_SCORE_CHANGED,
                             f"Risk score → {session.risk_score:.2f}",
                             EventActor.SAFETY_ENGINE,
                             payload={"risk_score": session.risk_score})
        await self.session_svc.update(session)
        return True

    # ── Tool execution ────────────────────────────────────────────

    async def _execute_tool(self, session: Session, tool_name: str,
                             args: dict) -> str:
        sid = session.sandbox_id

        if tool_name == "run_command":
            cmd = args["command"]
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Run: {cmd}", payload={"command": cmd, "tool": "sandbox_exec"})
            result = await self.sandbox_svc.execute(sid, cmd)
            output = result.stdout or result.stderr or "(no output)"
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"exit={result.exit_code}",
                             severity=EventSeverity.WARNING if result.exit_code != 0 else EventSeverity.INFO,
                             payload={"exit_code": result.exit_code,
                                      "stdout": result.stdout[:500],
                                      "stderr": result.stderr[:500]})
            await self._write_memory(session, MemoryLayer.WORKING,
                                      f"cmd_{uuid4().hex[:6]}",
                                      {"cmd": cmd, "exit": result.exit_code, "out": output[:300]},
                                      confidence=0.9, tags=["command"])
            return json.dumps({"exit_code": result.exit_code,
                               "stdout": result.stdout[:1000],
                               "stderr": result.stderr[:500]})

        elif tool_name == "read_file":
            path = args["path"]
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Read: {path}", payload={"path": path, "tool": "sandbox_read"})
            content = await self.sandbox_svc.read_file(sid, path)
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"Read {path} ({len(content)} bytes)",
                             payload={"path": path, "size": len(content)})
            await self._write_memory(session, MemoryLayer.EPISODIC,
                                      f"file_{path.replace('/', '_')}",
                                      {"path": path, "size": len(content),
                                       "preview": content[:200]},
                                      confidence=0.95, tags=["file", "read"])
            return content[:4000] if content else "(file not found)"

        elif tool_name == "write_file":
            path, content = args["path"], args["content"]
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Write: {path}", payload={"path": path, "tool": "sandbox_write"})
            await self.sandbox_svc.write_file(sid, path, content)
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"Wrote {path}",
                             payload={"path": path, "bytes": len(content)})
            await self._write_memory(session, MemoryLayer.EPISODIC,
                                      f"write_{path.replace('/', '_')}",
                                      {"path": path, "action": "write", "bytes": len(content)},
                                      confidence=0.95, tags=["file", "write"])
            return f"Written: {path}"

        elif tool_name == "list_files":
            directory = args.get("directory", ".")
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"List: {directory}", payload={"directory": directory})
            result = await self.sandbox_svc.execute(sid, f"find {directory} -maxdepth 3 -type f | head -50")
            files = result.stdout or "(empty)"
            await self._emit(session.id, EventType.TOOL_RESULT,
                             "Listed files", payload={"files": files[:500]})
            return files

        elif tool_name == "task_complete":
            return "__DONE__"

        return f"Unknown tool: {tool_name}"

    # ── Main agent loop ───────────────────────────────────────────

    async def run(self, session: Session):
        settings = self.settings
        session.status = SessionStatus.RUNNING
        session.stage = SessionStage.PLANNING
        await self.session_svc.update(session)

        sandbox_id = f"abb-{session.id[:12]}"
        session.sandbox_id = sandbox_id
        await self.session_svc.update(session)

        await self._emit(session.id, EventType.SESSION_CREATED,
                         "Session started", EventActor.RUNTIME)

        # Create Blaxel sandbox
        await self._emit(session.id, EventType.AGENT_STEP,
                         "Creating Blaxel sandbox", EventActor.RUNTIME)
        await self.sandbox_svc.create(sandbox_id)

        # Clone repo if provided
        if session.repo_url:
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Cloning {session.repo_url}",
                             payload={"command": f"git clone {session.repo_url} /workspace",
                                      "tool": "sandbox_exec"})
            clone_result = await self.sandbox_svc.execute(
                sandbox_id,
                f"git clone --depth=1 --branch {session.branch} {session.repo_url} /workspace 2>&1 || "
                f"git clone --depth=1 {session.repo_url} /workspace 2>&1"
            )
            clone_out = clone_result.stdout or clone_result.stderr
            await self._emit(session.id, EventType.TOOL_RESULT,
                             "Repo cloned" if clone_result.exit_code == 0 else "Clone failed",
                             severity=EventSeverity.WARNING if clone_result.exit_code != 0 else EventSeverity.INFO,
                             payload={"exit_code": clone_result.exit_code, "output": clone_out[:500]})
            await self._write_memory(session, MemoryLayer.SEMANTIC,
                                      "repo_info",
                                      {"url": session.repo_url, "branch": session.branch,
                                       "cloned": clone_result.exit_code == 0},
                                      tags=["repo"])

        # Initial checkpoint
        await self._checkpoint(session, "initial")
        session.stage = SessionStage.EXECUTING
        session.progress_percent = 10
        await self.session_svc.update(session)

        # Build system prompt
        system_prompt = f"""You are an expert software engineer operating inside a Linux sandbox.
Your task: {session.goal or session.description or session.title}
Working directory: /workspace
{"Repository: " + session.repo_url if session.repo_url else ""}

Guidelines:
- Use run_command to execute shell commands (git, pytest, pip, etc.)
- Use read_file / write_file for file operations
- Use list_files to explore the codebase
- After making changes, always verify with tests
- When the task is fully done, call task_complete with a clear summary
- Be systematic: plan, execute, verify
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please complete this task: {session.goal or session.title}"},
        ]

        await self._emit(session.id, EventType.PLAN_GENERATED,
                         "LLM agent loop started",
                         EventActor.AGENT,
                         payload={"goal": session.goal or session.title})

        step_count = 0
        checkpoint_counter = 0

        for iteration in range(settings.llm_max_iterations):
            # Check if session was paused/cancelled externally
            fresh = await self.session_svc.get(session.id)
            if fresh and fresh.status in (SessionStatus.PAUSED,
                                           SessionStatus.CANCELLED,
                                           SessionStatus.FAILED):
                break

            progress = min(10 + int((iteration / settings.llm_max_iterations) * 85), 90)
            session.progress_percent = progress
            await self.session_svc.update(session)

            try:
                response = await self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            except Exception as exc:
                await self._emit(session.id, EventType.FAILURE_DETECTED,
                                 f"LLM call failed: {exc}",
                                 EventActor.RUNTIME,
                                 severity=EventSeverity.ERROR)
                break

            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            # No more tool calls → LLM finished naturally
            if not msg.tool_calls:
                final_text = msg.content or "Task complete."
                await self._emit(session.id, EventType.AGENT_STEP,
                                 final_text[:200], EventActor.AGENT)
                break

            # Execute each tool call
            done = False
            tool_results = []
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result_str = await self._execute_tool(session, tool_name, args)

                if result_str == "__DONE__":
                    summary = args.get("summary", "Task completed.")
                    done = True
                    # Store final outcome summary
                    await self._write_memory(session, MemoryLayer.SEMANTIC,
                                              "task_outcome",
                                              {"summary": summary},
                                              confidence=0.99, tags=["outcome"])
                    result_str = summary

                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result_str,
                })

                step_count += 1
                checkpoint_counter += 1

                # Auto-checkpoint every N steps
                if checkpoint_counter >= settings.checkpoint_auto_interval:
                    await self._checkpoint(session, f"auto-step-{step_count}")
                    checkpoint_counter = 0

                # Safety check every 3 steps
                if step_count % settings.safety_check_interval == 0:
                    safety_triggered = await self._run_safety_check(session)
                    if safety_triggered and session.risk_score >= 0.7:
                        session.status = SessionStatus.PAUSED
                        session.stage = SessionStage.IDLE
                        session.outcome = "Paused: safety engine detected critical issue."
                        await self.session_svc.update(session)
                        await self._emit(session.id, EventType.SESSION_PAUSED,
                                         "Execution paused by safety engine",
                                         EventActor.SAFETY_ENGINE,
                                         severity=EventSeverity.ERROR)
                        return

            messages.extend(tool_results)

            if done:
                break

        # Final checkpoint + complete
        await self._checkpoint(session, "final")

        fresh = await self.session_svc.get(session.id)
        if fresh and fresh.status == SessionStatus.RUNNING:
            outcome_mem = await self.memory_svc.get_by_key(
                session.id, MemoryLayer.SEMANTIC, "task_outcome"
            )
            outcome_text = (
                outcome_mem.value.get("summary", "Task completed.")
                if outcome_mem else "Task completed successfully."
            )
            session.status = SessionStatus.COMPLETED
            session.stage = SessionStage.FINISHING
            session.progress_percent = 100
            session.outcome = outcome_text
            session.ended_at = datetime.utcnow()
            await self.session_svc.update(session)
            await self._emit(session.id, EventType.SESSION_COMPLETED,
                             "Task completed", EventActor.RUNTIME,
                             payload={"outcome": outcome_text})
