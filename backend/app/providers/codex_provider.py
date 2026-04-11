from __future__ import annotations

import asyncio
import json
from enum import Enum

from pydantic import BaseModel, Field

from app.core.config import get_settings


class CodexProviderError(RuntimeError):
    pass


class CodexActionType(str, Enum):
    RUN_COMMAND = "run_command"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    FINISH = "finish"


class CodexPlan(BaseModel):
    summary: str
    steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    done_when: str = ""


class CodexAction(BaseModel):
    action_type: CodexActionType
    rationale: str
    command: str | None = None
    path: str | None = None
    content: str | None = None
    summary: str = ""


class CodexReflection(BaseModel):
    should_retry: bool = False
    should_replan: bool = False
    updated_plan: list[str] = Field(default_factory=list)
    notes: str = ""


class CodexSummary(BaseModel):
    outcome: str
    summary: str
    key_changes: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


class CodexProvider:
    def __init__(self):
        self.settings = get_settings()
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as exc:  # pragma: no cover - depends on local env
                raise CodexProviderError("The 'openai' package is required for real execution") from exc
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.openai_timeout_seconds,
                max_retries=self.settings.openai_max_retries,
            )
        return self._client

    async def _parse_response(self, schema: type[BaseModel], model: str, instructions: str, user_payload: dict) -> BaseModel:
        if not self.is_configured():
            raise CodexProviderError("OpenAI/Codex provider is not configured")
        client = self._get_client()
        parser = getattr(client.responses, "parse", None)
        if parser is None:
            raise CodexProviderError("Installed OpenAI SDK does not support responses.parse")

        response = await asyncio.to_thread(
            parser,
            model=model,
            instructions=instructions,
            input=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, indent=2),
                }
            ],
            text_format=schema,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise CodexProviderError("Codex returned no structured output")
        return parsed

    async def plan_task(self, payload: dict) -> CodexPlan:
        instructions = (
            "You are planning a safe sandboxed code task. "
            "Return a concise execution plan for a coding agent working inside an isolated repo."
        )
        parsed = await self._parse_response(CodexPlan, self.settings.openai_model_planner, instructions, payload)
        return CodexPlan.model_validate(parsed)

    async def choose_next_action(self, payload: dict) -> CodexAction:
        instructions = (
            "You are choosing the next safe action for a sandboxed coding agent. "
            "Prefer inspection before mutation, use short commands, and finish once enough evidence exists."
        )
        parsed = await self._parse_response(CodexAction, self.settings.openai_model_planner, instructions, payload)
        return CodexAction.model_validate(parsed)

    async def reflect_on_result(self, payload: dict) -> CodexReflection:
        instructions = (
            "You are reflecting on the latest sandbox result. "
            "Decide whether to retry, replan, or continue, keeping the plan compact and safety-aware."
        )
        parsed = await self._parse_response(CodexReflection, self.settings.openai_model_summary, instructions, payload)
        return CodexReflection.model_validate(parsed)

    async def summarize_run(self, payload: dict) -> CodexSummary:
        instructions = (
            "Summarize the completed sandboxed coding run for an operator-facing dashboard. "
            "Keep it concise and factual."
        )
        parsed = await self._parse_response(CodexSummary, self.settings.openai_model_summary, instructions, payload)
        return CodexSummary.model_validate(parsed)
