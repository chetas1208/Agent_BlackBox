from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class DetectorType(str, Enum):
    RETRY_LOOP = "retry_loop"
    CONTRADICTION = "contradiction"
    TASK_DRIFT = "task_drift"
    BUDGET_OVERRUN = "budget_overrun"
    STALLED = "stalled"


class SafetyAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    detector_type: DetectorType
    severity: str = "warning"
    message: str = ""
    trigger_event_id: str | None = None
    resolved: bool = False
    action_taken: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
