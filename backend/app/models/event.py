from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class EventType(str, Enum):
    SESSION_CREATED = "session_created"
    PLAN_GENERATED = "plan_generated"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    TOOL_INVOKED = "tool_invoked"
    TOOL_RESULT = "tool_result"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    FAILURE_DETECTED = "failure_detected"
    CONTRADICTION_DETECTED = "contradiction_detected"
    RETRY_DETECTED = "retry_detected"
    RISK_SCORE_CHANGED = "risk_score_changed"
    DRIFT_DETECTED = "drift_detected"
    POLICY_BLOCKED = "policy_blocked"
    REPLAY_STARTED = "replay_started"
    REPLAY_COMPLETED = "replay_completed"
    SESSION_COMPLETED = "session_completed"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SANDBOX_ACTION = "sandbox_action"
    STALL_DETECTED = "stall_detected"
    BUDGET_OVERRUN = "budget_overrun"
    MEMORY_QUARANTINED = "memory_quarantined"
    MEMORY_PROMOTED = "memory_promoted"
    AGENT_STEP = "agent_step"


class EventActor(str, Enum):
    AGENT = "agent"
    RUNTIME = "runtime"
    SAFETY_ENGINE = "safety_engine"
    OPERATOR = "operator"
    RECOVERY_ENGINE = "recovery_engine"


class EventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    event_type: EventType
    actor: EventActor = EventActor.RUNTIME
    severity: EventSeverity = EventSeverity.INFO
    summary: str = ""
    payload: dict = Field(default_factory=dict)
    related_memory_ids: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
