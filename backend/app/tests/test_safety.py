"""Tests for the safety engine detectors."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from app.models.event import Event, EventType, EventActor, EventSeverity
from app.models.session import Session, SessionStatus
from app.safety.engine import SafetyEngineService


def make_event(session_id: str, event_type: EventType, payload: dict | None = None) -> Event:
    return Event(
        session_id=session_id,
        event_type=event_type,
        actor=EventActor.AGENT,
        payload=payload or {},
    )


def make_session(session_id: str = "test-session") -> Session:
    return Session(id=session_id, title="Test Session", goal="Test")


@pytest.fixture
def safety_engine():
    repo = AsyncMock()
    repo.save_model = AsyncMock()
    return SafetyEngineService(repo)


@pytest.mark.asyncio
async def test_retry_loop_detected(safety_engine):
    session_id = "sess-1"
    events = [
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "pytest tests/"}),
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "pytest tests/"}),
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "pytest tests/"}),
    ]
    alert = await safety_engine.detect_retry_loop(events)
    assert alert is not None
    assert alert.detector_type.value == "retry_loop"


@pytest.mark.asyncio
async def test_no_retry_loop_for_different_commands(safety_engine):
    session_id = "sess-2"
    events = [
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "ls"}),
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "cat file.py"}),
        make_event(session_id, EventType.TOOL_INVOKED, {"command": "pytest tests/"}),
    ]
    alert = await safety_engine.detect_retry_loop(events)
    assert alert is None


@pytest.mark.asyncio
async def test_contradiction_detected(safety_engine):
    session_id = "sess-3"
    session = make_session(session_id)
    events = [
        make_event(session_id, EventType.TOOL_RESULT, {
            "contradicts_memory": True,
            "contradiction_detail": "Tests say fail but memory says pass",
        }),
    ]
    alert = await safety_engine.detect_contradiction(events, session)
    assert alert is not None
    assert alert.detector_type.value == "contradiction"


@pytest.mark.asyncio
async def test_no_contradiction_when_clean(safety_engine):
    session_id = "sess-4"
    session = make_session(session_id)
    events = [
        make_event(session_id, EventType.TOOL_RESULT, {"exit_code": 0}),
    ]
    alert = await safety_engine.detect_contradiction(events, session)
    assert alert is None


@pytest.mark.asyncio
async def test_budget_overrun_detected(safety_engine):
    session_id = "sess-5"
    session = make_session(session_id)
    events = [make_event(session_id, EventType.AGENT_STEP) for _ in range(201)]
    alert = await safety_engine.detect_budget_overrun(events, session)
    assert alert is not None
    assert alert.detector_type.value == "budget_overrun"


@pytest.mark.asyncio
async def test_no_budget_overrun_under_limit(safety_engine):
    session_id = "sess-6"
    session = make_session(session_id)
    events = [make_event(session_id, EventType.AGENT_STEP) for _ in range(50)]
    alert = await safety_engine.detect_budget_overrun(events, session)
    assert alert is None
