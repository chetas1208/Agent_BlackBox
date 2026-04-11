from __future__ import annotations
from pydantic import BaseModel
from app.models.memory import MemoryLayer, MemoryStatus


class CreateMemoryRequest(BaseModel):
    layer: MemoryLayer
    key: str
    value: dict | str | list = {}
    source: str = "agent"
    confidence: float = 1.0
    importance_score: float = 0.5
    tags: list[str] = []


class UpdateMemoryRequest(BaseModel):
    value: dict | str | list | None = None
    confidence: float | None = None
    contradiction_score: float | None = None
    importance_score: float | None = None
    status: MemoryStatus | None = None
    tags: list[str] | None = None
