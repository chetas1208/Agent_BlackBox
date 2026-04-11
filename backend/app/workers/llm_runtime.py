"""Real LLM-powered agent runtime using OpenAI tool-calling + Blaxel sandboxes.

Features:
- Real Blaxel sandbox execution
- OpenAI tool-calling loop (run_command, read_file, write_file, list_files, create_pr, task_complete)
- Guardrails: block destructive commands, scope violations, secret leaks
- Context window compression: summarise every N steps to stay within token limits
- Long-term user memory: persist learnings across sessions
- Safety Engine integration at every step
- Auto-checkpointing
"""
from __future__ import annotations

import asyncio
import json
import re
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

# ── Guardrail patterns ────────────────────────────────────────────

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r":\(\)\{.*\}",          # fork bomb
    r"dd\s+if=.*of=/dev/",   # disk wipe
    r"mkfs\.",               # format disk
    r"git\s+push.*--force.*main",
    r"git\s+push.*--force.*master",
    r"DROP\s+TABLE",
    r"DROP\s+DATABASE",
    r"chmod\s+777\s+/",
    r">\s*/etc/passwd",
    r"curl.*\|\s*bash",
    r"wget.*\|\s*bash",
]

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",       # OpenAI key
    r"ghp_[a-zA-Z0-9]{36}",       # GitHub token
    r"AKIA[A-Z0-9]{16}",           # AWS key
    r"password\s*=\s*['\"][^'\"]{8,}",
]

SCOPE_VIOLATION_PATTERNS = [
    r"(cat|rm|chmod|chown|mv|cp)\s+/etc/",
    r"(cat|rm)\s+/root/",
    r"(cat|rm)\s+~/\.",
]

# ── Tool definitions ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the sandbox. Returns stdout and stderr.",
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
            "description": "Read the contents of a file in /workspace.",
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
            "description": "Write or overwrite a file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to /workspace"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory of /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "default": "."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pr",
            "description": "Create a GitHub Pull Request with all changes made in the sandbox. Call this after completing the task to deliver results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description explaining the changes"},
                    "branch_name": {"type": "string", "description": "New branch name for the PR (e.g. fix/login-test)"},
                },
                "required": ["title", "body", "branch_name"],
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
                    "summary": {"type": "string", "description": "What was accomplished"},
                },
                "required": ["summary"],
            },
        },
    },
]


def _check_guardrails(command: str) -> str | None:
    """Return a guardrail violation message, or None if safe."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"BLOCKED by guardrail: dangerous pattern detected ({pattern})"
    for pattern in SCOPE_VIOLATION_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"BLOCKED by guardrail: scope violation — agent tried to access system files"
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, command):
            return "BLOCKED by guardrail: potential secret/credential detected in command"
    return None


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
        user_id: str | None = None,
        github_token: str | None = None,
    ):
        self.session_svc = session_svc
        self.event_svc = event_svc
        self.memory_svc = memory_svc
        self.checkpoint_svc = checkpoint_svc
        self.sandbox_svc = sandbox_svc
        self.safety_svc = safety_svc
        self.recovery_svc = recovery_svc
        self.user_id = user_id
        self.github_token = github_token
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    # ── Helpers ───────────────────────────────────────────────────

    async def _emit(self, session_id: str, event_type: EventType, summary: str,
                    actor: EventActor = EventActor.AGENT,
                    severity: EventSeverity = EventSeverity.INFO,
                    payload: dict | None = None):
        await self.event_svc.emit(session_id, event_type, summary, actor,
                                  severity=severity, payload=payload or {})

    async def _write_memory(self, session: Session, layer: MemoryLayer, key: str,
                             value, confidence: float = 0.9, tags: list[str] | None = None):
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
        await self._emit(session.id, EventType.MEMORY_WRITE,
                         f"Write {layer.value}: {key}", EventActor.AGENT,
                         payload={"layer": layer.value, "key": key})
        return item

    async def _checkpoint(self, session: Session, label: str) -> str:
        mem_ids = await self.memory_svc.snapshot_ids(session.id)
        snap_ref = ""
        if session.sandbox_id:
            try:
                snap_ref = await self.sandbox_svc.snapshot(session.sandbox_id)
            except Exception:
                pass
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
        await self.session_svc.update(session)
        return True

    async def _compress_context(self, messages: list[dict], session_id: str) -> list[dict]:
        """Summarise old messages to keep context window small."""
        if len(messages) <= 12:
            return messages

        system_msg = messages[0]
        to_summarise = messages[1:-6]  # keep system + last 6
        recent = messages[-6:]

        history_text = "\n".join([
            f"{m.get('role','?').upper()}: {str(m.get('content',''))[:300]}"
            for m in to_summarise
            if isinstance(m.get('content'), str)
        ])

        try:
            resp = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": "Summarise this agent conversation history in 3-5 bullet points. Focus on: what was found, what was changed, current state."},
                    {"role": "user", "content": history_text[:6000]},
                ],
                max_tokens=400,
            )
            summary = resp.choices[0].message.content or "Prior steps executed."
        except Exception:
            summary = f"Prior {len(to_summarise)} steps executed."

        await self._emit(session_id, EventType.AGENT_STEP,
                         "Context compressed for efficiency",
                         EventActor.RUNTIME,
                         payload={"compressed_steps": len(to_summarise)})

        return [
            system_msg,
            {"role": "assistant", "content": f"[Context Summary]\n{summary}"},
            *recent,
        ]

    async def _load_user_long_term_memory(self, session: Session) -> str:
        """Load long-term memory from previous sessions for this user."""
        if not self.user_id:
            return ""
        try:
            # Long-term memory is stored under a special session id per user
            ltm_session_id = f"ltm:{self.user_id}"
            items = await self.memory_svc.list_items(ltm_session_id)
            if not items:
                return ""
            parts = []
            for item in items[:10]:
                if isinstance(item.value, dict):
                    parts.append(f"- {item.key}: {json.dumps(item.value)[:200]}")
                else:
                    parts.append(f"- {item.key}: {str(item.value)[:200]}")
            return "\n".join(parts)
        except Exception:
            return ""

    async def _save_user_long_term_memory(self, session: Session, summary: str):
        """Persist key learnings to user's long-term memory."""
        if not self.user_id:
            return
        ltm_session_id = f"ltm:{self.user_id}"
        repo_key = session.repo_url.split("/")[-1] if session.repo_url else "unknown"
        item = MemoryItem(
            session_id=ltm_session_id,
            layer=MemoryLayer.SEMANTIC,
            key=f"session_{session.id[:8]}_{repo_key}",
            value={
                "repo": session.repo_url,
                "task": session.goal or session.title,
                "outcome": summary,
                "timestamp": datetime.utcnow().isoformat(),
            },
            source="system",
            confidence=0.9,
            tags=["long_term", repo_key],
        )
        await self.memory_svc.create_item(item)

    # ── Tool execution ────────────────────────────────────────────

    async def _execute_tool(self, session: Session, tool_name: str, args: dict) -> str:
        sid = session.sandbox_id

        if tool_name == "run_command":
            cmd = args.get("command", "")

            # Guardrail check
            violation = _check_guardrails(cmd)
            if violation:
                await self._emit(session.id, EventType.FAILURE_DETECTED,
                                 violation, EventActor.SAFETY_ENGINE,
                                 severity=EventSeverity.ERROR,
                                 payload={"command": cmd, "blocked": True})
                session.risk_score = min(1.0, session.risk_score + 0.2)
                await self.session_svc.update(session)
                return json.dumps({"error": violation, "exit_code": 1})

            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Run: {cmd[:80]}", payload={"command": cmd, "tool": "sandbox_exec"})
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
                               "stdout": result.stdout[:1500],
                               "stderr": result.stderr[:500]})

        elif tool_name == "read_file":
            path = args.get("path", "")
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Read: {path}", payload={"path": path, "tool": "sandbox_read"})
            content = await self.sandbox_svc.read_file(sid, path)
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"Read {path} ({len(content)} bytes)",
                             payload={"path": path, "size": len(content)})
            await self._write_memory(session, MemoryLayer.EPISODIC,
                                      f"file_{path.replace('/', '_')[:40]}",
                                      {"path": path, "size": len(content), "preview": content[:300]},
                                      confidence=0.95, tags=["file", "read"])
            return content[:5000] if content else "(file not found or empty)"

        elif tool_name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")

            # Guardrail: check content for secrets before writing
            for pattern in SECRET_PATTERNS:
                if re.search(pattern, content):
                    return json.dumps({"error": "BLOCKED: potential secret detected in file content", "written": False})

            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Write: {path}", payload={"path": path, "tool": "sandbox_write"})
            await self.sandbox_svc.write_file(sid, path, content)
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"Wrote {path} ({len(content)} bytes)",
                             payload={"path": path, "bytes": len(content)})
            await self._write_memory(session, MemoryLayer.EPISODIC,
                                      f"write_{path.replace('/', '_')[:40]}",
                                      {"path": path, "action": "write", "bytes": len(content)},
                                      confidence=0.95, tags=["file", "write"])
            return f"Written: {path}"

        elif tool_name == "list_files":
            directory = args.get("directory", ".")
            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"List: {directory}", payload={"directory": directory})
            result = await self.sandbox_svc.execute(sid, f"find {directory} -maxdepth 3 -type f | head -60")
            files = result.stdout or "(empty)"
            await self._emit(session.id, EventType.TOOL_RESULT,
                             "Listed files", payload={"files": files[:500]})
            return files

        elif tool_name == "create_pr":
            return await self._create_pr(session, args)

        elif tool_name == "task_complete":
            return "__DONE__"

        return f"Unknown tool: {tool_name}"

    async def _create_pr(self, session: Session, args: dict) -> str:
        """Create a GitHub PR with all changes made in the sandbox."""
        title = args.get("title", "Agent fix")
        body = args.get("body", "Automated fix by Agent Black Box")
        branch_name = args.get("branch_name", f"agent-fix-{session.id[:8]}")

        if not session.repo_url:
            return "No repo URL configured for this session"

        token = self.github_token
        if not token:
            return "No GitHub token available — cannot create PR"

        await self._emit(session.id, EventType.TOOL_INVOKED,
                         f"Creating PR: {title}",
                         payload={"title": title, "branch": branch_name})

        # Create branch and commit in sandbox, then push
        git_cmds = [
            f"cd /workspace && git config user.email 'agent@agentblackbox.ai'",
            f"cd /workspace && git config user.name 'Agent Black Box'",
            f"cd /workspace && git checkout -b {branch_name}",
            f"cd /workspace && git add -A",
            f"cd /workspace && git commit -m '{title}'",
        ]

        # Embed token in remote URL for push auth
        repo_with_token = session.repo_url.replace("https://", f"https://{token}@")
        git_cmds.append(f"cd /workspace && git push {repo_with_token} {branch_name}")

        for cmd in git_cmds:
            result = await self.sandbox_svc.execute(session.sandbox_id, cmd)
            if result.exit_code != 0 and "nothing to commit" not in result.stdout:
                await self._emit(session.id, EventType.TOOL_RESULT,
                                 f"Git step failed: {result.stderr[:100]}",
                                 severity=EventSeverity.WARNING)

        # Create PR via GitHub API
        try:
            from github import Github
            g = Github(token)
            repo_name = "/".join(session.repo_url.rstrip("/").split("/")[-2:])
            repo_name = repo_name.replace(".git", "")
            gh_repo = g.get_repo(repo_name)
            pr = gh_repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=session.branch or gh_repo.default_branch,
            )
            pr_url = pr.html_url
            await self._emit(session.id, EventType.TOOL_RESULT,
                             f"PR created: {pr_url}",
                             payload={"pr_url": pr_url, "title": title})
            await self._write_memory(session, MemoryLayer.SEMANTIC,
                                      "pull_request",
                                      {"url": pr_url, "title": title, "branch": branch_name},
                                      confidence=1.0, tags=["pr", "github"])
            return f"PR created: {pr_url}"
        except Exception as e:
            return f"Push succeeded but PR creation failed: {e}. Branch: {branch_name}"

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

        # Load user's long-term memory from prior sessions
        ltm_context = await self._load_user_long_term_memory(session)

        # Create sandbox
        await self._emit(session.id, EventType.AGENT_STEP,
                         "Creating Blaxel sandbox", EventActor.RUNTIME)
        await self.sandbox_svc.create(sandbox_id)

        # Clone repo
        if session.repo_url:
            clone_url = session.repo_url
            if self.github_token and "github.com" in clone_url:
                clone_url = clone_url.replace("https://", f"https://{self.github_token}@")

            await self._emit(session.id, EventType.TOOL_INVOKED,
                             f"Cloning {session.repo_url}",
                             payload={"command": f"git clone {session.repo_url}", "tool": "sandbox_exec"})
            clone_result = await self.sandbox_svc.execute(
                sandbox_id,
                f"git clone --depth=1 --branch {session.branch} {clone_url} /workspace 2>&1 || "
                f"git clone --depth=1 {clone_url} /workspace 2>&1"
            )
            await self._emit(session.id, EventType.TOOL_RESULT,
                             "Repo cloned" if clone_result.exit_code == 0 else "Clone failed",
                             severity=EventSeverity.WARNING if clone_result.exit_code != 0 else EventSeverity.INFO,
                             payload={"exit_code": clone_result.exit_code,
                                      "output": (clone_result.stdout or clone_result.stderr)[:300]})

            # Read README for RAG context
            readme_content = await self.sandbox_svc.read_file(sandbox_id, "README.md")
            if readme_content:
                await self._write_memory(session, MemoryLayer.SEMANTIC,
                                          "readme",
                                          {"content": readme_content[:2000]},
                                          confidence=0.95, tags=["readme", "rag"])

        await self._checkpoint(session, "initial")
        session.stage = SessionStage.EXECUTING
        session.progress_percent = 10
        await self.session_svc.update(session)

        # Build system prompt with long-term memory
        ltm_section = f"\n\nYour long-term memory from previous sessions:\n{ltm_context}" if ltm_context else ""
        readme_section = ""
        readme_mem = await self.memory_svc.get_by_key(session.id, MemoryLayer.SEMANTIC, "readme")
        if readme_mem and readme_mem.value:
            readme_section = f"\n\nREADME context:\n{str(readme_mem.value.get('content',''))[:1500]}"

        system_prompt = f"""You are an expert software engineer operating inside a Linux sandbox.
Your task: {session.goal or session.description or session.title}
Working directory: /workspace
{"Repository: " + session.repo_url if session.repo_url else ""}
{readme_section}
{ltm_section}

Guidelines:
- Use run_command for shell commands (pytest, pip, git, grep, find, etc.)
- Use read_file / write_file for file operations
- Use list_files to explore structure
- After fixing, always verify with tests
- When done, use create_pr to deliver your changes as a GitHub PR
- Then call task_complete with a clear summary
- Be systematic: explore → understand → plan → fix → verify → PR
"""

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please complete this task: {session.goal or session.title}"},
        ]

        await self._emit(session.id, EventType.PLAN_GENERATED,
                         "LLM agent loop started", EventActor.AGENT,
                         payload={"goal": session.goal or session.title})

        step_count = 0
        checkpoint_counter = 0
        final_summary = ""

        for iteration in range(settings.llm_max_iterations):
            # Check for external pause/cancel
            fresh = await self.session_svc.get(session.id)
            if fresh and fresh.status in (SessionStatus.PAUSED, SessionStatus.CANCELLED, SessionStatus.FAILED):
                break

            # Context window compression every 10 steps
            if step_count > 0 and step_count % 10 == 0:
                messages = await self._compress_context(messages, session.id)

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
                                 f"LLM call failed: {exc}", EventActor.RUNTIME,
                                 severity=EventSeverity.ERROR)
                break

            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                final_text = msg.content or "Task complete."
                await self._emit(session.id, EventType.AGENT_STEP, final_text[:200], EventActor.AGENT)
                if not final_summary:
                    final_summary = final_text
                break

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
                    final_summary = args.get("summary", "Task completed.")
                    done = True
                    await self._write_memory(session, MemoryLayer.SEMANTIC,
                                              "task_outcome",
                                              {"summary": final_summary},
                                              confidence=0.99, tags=["outcome"])
                    result_str = final_summary

                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result_str,
                })

                step_count += 1
                checkpoint_counter += 1

                if checkpoint_counter >= settings.checkpoint_auto_interval:
                    await self._checkpoint(session, f"auto-step-{step_count}")
                    checkpoint_counter = 0

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

        # Save to long-term memory
        if final_summary:
            await self._save_user_long_term_memory(session, final_summary)

        await self._checkpoint(session, "final")

        fresh = await self.session_svc.get(session.id)
        if fresh and fresh.status == SessionStatus.RUNNING:
            if not final_summary:
                outcome_mem = await self.memory_svc.get_by_key(
                    session.id, MemoryLayer.SEMANTIC, "task_outcome"
                )
                final_summary = (
                    outcome_mem.value.get("summary", "Task completed.")
                    if outcome_mem else "Task completed successfully."
                )
            session.status = SessionStatus.COMPLETED
            session.stage = SessionStage.FINISHING
            session.progress_percent = 100
            session.outcome = final_summary
            session.ended_at = datetime.utcnow()
            await self.session_svc.update(session)
            await self._emit(session.id, EventType.SESSION_COMPLETED,
                             "Task completed", EventActor.RUNTIME,
                             payload={"outcome": final_summary})
