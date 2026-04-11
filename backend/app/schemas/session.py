from __future__ import annotations
from pydantic import BaseModel, model_validator
from app.models.session import TaskType, ExecutionMode


class CreateSessionRequest(BaseModel):
    title: str
    description: str = ""
    goal: str = ""
    task_type: TaskType = TaskType.CUSTOM
    execution_mode: ExecutionMode = ExecutionMode.DEMO
    sandbox_profile: str | None = None
    repo_url: str | None = None
    repo_ref: str | None = None
    idempotency_key: str | None = None
    auto_checkpoint: bool = True
    safety_policy: str = "standard"
    memory_strategy: str = "default"

    @model_validator(mode="after")
    def validate_real_mode(self) -> "CreateSessionRequest":
        if self.execution_mode == ExecutionMode.REAL and not self.repo_url:
            raise ValueError("repo_url is required when execution_mode is 'real'")
        if self.sandbox_profile is None:
            self.sandbox_profile = "blaxel" if self.execution_mode == ExecutionMode.REAL else "local_mock"
        return self


class SessionSummary(BaseModel):
    total: int = 0
    active: int = 0
    paused: int = 0
    failed: int = 0
    completed: int = 0
    recovered: int = 0
