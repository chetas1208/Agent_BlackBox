"""Recovery branch model."""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class BranchStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SELECTED = "selected"
    DISCARDED = "discarded"


class RecoveryBranch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    parent_checkpoint_id: str
    strategy: str = ""
    description: str = ""
    sandbox_id: str | None = None
    status: BranchStatus = BranchStatus.RUNNING
    event_count: int = 0
    risk_score: float = 0.0
    confidence_score: float = 0.5
    outcome: str | None = None
    is_winner: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
