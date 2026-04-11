from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"
    CANCELLED = "cancelled"


class SessionStage(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    RECOVERING = "recovering"
    CHECKPOINTING = "checkpointing"
    FINISHING = "finishing"
    IDLE = "idle"


class TaskType(str, Enum):
    DEBUG = "debug"
    INVESTIGATE = "investigate"
    REVIEW = "review"
    RESEARCH = "research"
    REFACTOR = "refactor"
    CUSTOM = "custom"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    goal: str = ""
    task_type: TaskType = TaskType.CUSTOM
    status: SessionStatus = SessionStatus.PENDING
    stage: SessionStage = SessionStage.IDLE
    sandbox_id: str | None = None
    risk_score: float = 0.0
    confidence_score: float = 1.0
    progress_percent: int = 0
    current_plan: list[str] = Field(default_factory=list)
    last_checkpoint_id: str | None = None
    event_count: int = 0
    auto_checkpoint: bool = True
    safety_policy: str = "standard"
    memory_strategy: str = "default"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: str | None = None
