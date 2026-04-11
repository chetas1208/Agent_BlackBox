"""Structured action types for the agent runtime."""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from uuid import uuid4


class ActionType(str, Enum):
    LIST_FILES = "list_files"
    READ_FILE = "read_file"
    SEARCH_CODE = "search_code"
    RUN_COMMAND = "run_command"
    RUN_TESTS = "run_tests"
    WRITE_FILE = "write_file"
    CREATE_CHECKPOINT = "create_checkpoint"
    RESTORE_CHECKPOINT = "restore_checkpoint"
    REQUEST_APPROVAL = "request_approval"
    SUMMARIZE_FINDINGS = "summarize_findings"
    GENERATE_PLAN = "generate_plan"
    ANALYZE_RESULT = "analyze_result"


class AgentAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: ActionType
    tool: str = ""
    arguments: dict = Field(default_factory=dict)
    rationale: str = ""
    expected_outcome: str = ""
    confidence: float = 0.8
    requires_approval: bool = False
    risk_level: str = "low"  # low, medium, high, critical
