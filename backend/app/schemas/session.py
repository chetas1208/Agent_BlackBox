from __future__ import annotations
from pydantic import BaseModel
from app.models.session import TaskType


class CreateSessionRequest(BaseModel):
    title: str
    description: str = ""
    goal: str = ""
    task_type: TaskType = TaskType.CUSTOM
    sandbox_profile: str = "local_mock"
    repo_url: str | None = None
    branch: str = "main"
    auto_checkpoint: bool = True
    safety_policy: str = "standard"
    memory_strategy: str = "default"


class SessionSummary(BaseModel):
    total: int = 0
    active: int = 0
    paused: int = 0
    failed: int = 0
    completed: int = 0
    recovered: int = 0
