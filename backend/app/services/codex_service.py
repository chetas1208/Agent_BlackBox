from __future__ import annotations

import json
import logging
from typing import Any

import openai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_PLAN_SYSTEM = (
    "You are a planning engine for an autonomous software agent. "
    "Given a task, generate a concrete execution plan as a JSON array of short step strings. "
    "Respond ONLY with valid JSON: [\"step 1\", \"step 2\", ...]"
)

_ACTION_SYSTEM = (
    "You are the decision engine for an autonomous agent. "
    "Given the goal, plan, completed steps, recent events, and memory context, "
    "choose the next action. Respond ONLY with valid JSON containing these keys: "
    "action_type (str), tool (str), arguments (dict), rationale (str), "
    "expected_outcome (str), confidence (float 0-1), risk_level (str: low/medium/high)."
)

_ANALYZE_SYSTEM = (
    "You are an analysis engine. Given an action and its result, produce a JSON object with: "
    "observation (str), should_continue (bool), confidence_delta (float -1 to 1), "
    "memory_updates (list of dicts with key/value/layer), concerns (list of str)."
)

_SUMMARY_SYSTEM = (
    "You are a technical writer. Produce a concise, human-readable session summary. "
    "Return plain text, not JSON."
)

_DEFAULT_PLAN = [
    "Analyze the task and identify key objectives",
    "Gather context from available memory and tools",
    "Execute primary actions toward the goal",
    "Validate results against the goal criteria",
    "Summarize findings and record outcomes",
]

_SIMULATED_ACTIONS = [
    {
        "action_type": "read_file",
        "tool": "file_reader",
        "arguments": {"path": "src/main.py"},
        "rationale": "Need to understand the current codebase structure",
        "expected_outcome": "Obtain source code for analysis",
        "confidence": 0.85,
        "risk_level": "low",
    },
    {
        "action_type": "search",
        "tool": "code_search",
        "arguments": {"query": "error handling"},
        "rationale": "Search for relevant patterns in the codebase",
        "expected_outcome": "Find related code sections",
        "confidence": 0.75,
        "risk_level": "low",
    },
    {
        "action_type": "write_file",
        "tool": "file_writer",
        "arguments": {"path": "src/fix.py", "content": "# proposed fix"},
        "rationale": "Apply the identified fix",
        "expected_outcome": "Code change applied successfully",
        "confidence": 0.70,
        "risk_level": "medium",
    },
    {
        "action_type": "run_command",
        "tool": "shell",
        "arguments": {"command": "python -m pytest tests/"},
        "rationale": "Verify the fix passes existing tests",
        "expected_outcome": "All tests pass",
        "confidence": 0.80,
        "risk_level": "medium",
    },
    {
        "action_type": "done",
        "tool": "none",
        "arguments": {},
        "rationale": "All steps completed successfully",
        "expected_outcome": "Task marked as complete",
        "confidence": 0.90,
        "risk_level": "low",
    },
]


class CodexService:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_planner = settings.openai_model_planner
        self.model_summary = settings.openai_model_summary
        self.timeout = settings.openai_timeout_seconds
        self.client: openai.AsyncOpenAI | None = None
        if self.api_key:
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key, timeout=self.timeout
            )

    async def _chat(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        json_mode: bool = True,
    ) -> str:
        if self.client is None:
            raise RuntimeError("OpenAI client is not configured")
        kwargs: dict[str, Any] = {
            "model": model or self.model_planner,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------

    async def generate_plan(
        self,
        task_title: str,
        task_description: str,
        goal: str,
        context: str = "",
    ) -> list[str]:
        """Ask Codex to generate an execution plan. Returns list of plan steps."""
        if self.client is None:
            return list(_DEFAULT_PLAN)

        prompt = (
            f"Task: {task_title}\n"
            f"Description: {task_description}\n"
            f"Goal: {goal}\n"
        )
        if context:
            prompt += f"Context: {context}\n"

        try:
            raw = await self._chat(_PLAN_SYSTEM, prompt)
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(s) for s in data]
            if isinstance(data, dict) and "steps" in data:
                return [str(s) for s in data["steps"]]
            return _DEFAULT_PLAN[:]
        except Exception:
            logger.exception("generate_plan failed, returning default plan")
            return _DEFAULT_PLAN[:]

    # ------------------------------------------------------------------

    async def choose_next_action(
        self,
        goal: str,
        plan: list[str],
        completed_steps: list[str],
        recent_events: list[dict],
        memory_context: list[dict],
    ) -> dict:
        """Ask Codex what to do next.

        Returns a dict with: action_type, tool, arguments, rationale,
        expected_outcome, confidence, risk_level.
        """
        if self.client is None:
            idx = min(len(completed_steps), len(_SIMULATED_ACTIONS) - 1)
            return dict(_SIMULATED_ACTIONS[idx])

        prompt = json.dumps(
            {
                "goal": goal,
                "plan": plan,
                "completed_steps": completed_steps,
                "recent_events": recent_events[-10:],
                "memory_context": memory_context[-10:],
            },
            default=str,
        )

        try:
            raw = await self._chat(_ACTION_SYSTEM, prompt)
            return json.loads(raw)
        except Exception:
            logger.exception("choose_next_action failed, returning simulated action")
            idx = min(len(completed_steps), len(_SIMULATED_ACTIONS) - 1)
            return dict(_SIMULATED_ACTIONS[idx])

    # ------------------------------------------------------------------

    async def analyze_result(
        self,
        action: dict,
        result: dict,
        memory_context: list[dict],
    ) -> dict:
        """Ask Codex to analyze a tool result.

        Returns dict with: observation, should_continue, confidence_delta,
        memory_updates, concerns.
        """
        if self.client is None:
            return {
                "observation": f"Action '{action.get('action_type', '?')}' completed",
                "should_continue": True,
                "confidence_delta": 0.05,
                "memory_updates": [],
                "concerns": [],
            }

        prompt = json.dumps(
            {
                "action": action,
                "result": result,
                "memory_context": memory_context[-10:],
            },
            default=str,
        )

        try:
            raw = await self._chat(_ANALYZE_SYSTEM, prompt)
            return json.loads(raw)
        except Exception:
            logger.exception("analyze_result failed, returning safe default")
            return {
                "observation": "Analysis unavailable — continuing with caution",
                "should_continue": True,
                "confidence_delta": 0.0,
                "memory_updates": [],
                "concerns": ["LLM analysis failed"],
            }

    # ------------------------------------------------------------------

    async def generate_summary(
        self,
        session_title: str,
        events_summary: list[str],
        outcome: str,
    ) -> str:
        """Generate a human-readable summary of the session."""
        if self.client is None:
            bullet_list = "\n".join(f"  - {e}" for e in events_summary[:10])
            return (
                f"Session '{session_title}' completed with outcome: {outcome}.\n"
                f"Key events:\n{bullet_list}"
            )

        prompt = (
            f"Session: {session_title}\n"
            f"Outcome: {outcome}\n"
            f"Events:\n" + "\n".join(f"- {e}" for e in events_summary[:30])
        )

        try:
            return await self._chat(
                _SUMMARY_SYSTEM,
                prompt,
                model=self.model_summary,
                json_mode=False,
            )
        except Exception:
            logger.exception("generate_summary failed, returning basic summary")
            return f"Session '{session_title}' finished with outcome: {outcome}."
