"""Postmortem report model."""
from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class PostmortemSection(BaseModel):
    title: str
    content: str
    severity: str = "info"


class Postmortem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    mission_summary: str = ""
    final_outcome: str = ""
    root_cause: str = ""
    key_events: list[dict] = Field(default_factory=list)
    memories_involved: list[dict] = Field(default_factory=list)
    quarantined_memories: list[str] = Field(default_factory=list)
    failure_points: list[str] = Field(default_factory=list)
    recovery_actions: list[str] = Field(default_factory=list)
    branches_used: list[dict] = Field(default_factory=list)
    winning_branch: str | None = None
    policy_recommendations: list[str] = Field(default_factory=list)
    total_events: int = 0
    total_checkpoints: int = 0
    total_recovery_attempts: int = 0
    duration_seconds: float = 0
    sections: list[PostmortemSection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
