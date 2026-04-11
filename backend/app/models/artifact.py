from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    SUMMARY = "summary"
    DIFF = "diff"
    COMMAND_LOG = "command_log"
    FILE_PREVIEW = "file_preview"
    FINAL_RESULT = "final_result"


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    artifact_type: ArtifactType
    title: str
    content: str
    path: str | None = None
    content_type: str = "text/plain"
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
