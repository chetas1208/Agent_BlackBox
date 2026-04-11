from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class MemoryLayer(str, Enum):
    WORKING = "working_memory"
    EPISODIC = "episodic_memory"
    SEMANTIC = "semantic_memory"
    RISK = "risk_memory"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    layer: MemoryLayer
    key: str
    value: dict | str | list = Field(default_factory=dict)
    source: str = "agent"
    confidence: float = 1.0
    contradiction_score: float = 0.0
    importance_score: float = 0.5
    recency_score: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    dependency_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
