"""Approval gate model."""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class ApprovalGate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    action_type: str = ""
    action_summary: str = ""
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    risk_score: float = 0.5
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
