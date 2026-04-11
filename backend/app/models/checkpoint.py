from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class Checkpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    label: str = ""
    event_index: int = 0
    plan_snapshot: list[str] = Field(default_factory=list)
    memory_snapshot_ref: str = ""
    sandbox_snapshot_ref: str = ""
    safety_status: str = "clean"
    risk_score_at: float = 0.0
    confidence_at: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
