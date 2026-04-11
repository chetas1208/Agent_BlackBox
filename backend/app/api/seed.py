"""Seed endpoint to create demo scenarios."""
from __future__ import annotations

from fastapi import APIRouter
from app.api.deps import get_session_svc, get_agent_runtime
from app.schemas.session import CreateSessionRequest
from app.models.session import TaskType
from app.workers.agent_runtime import start_agent_task

router = APIRouter(prefix="/api/seed", tags=["seed"])

DEMO_SCENARIOS = [
    {
        "title": "Debug auth module test failure",
        "description": "Investigate and fix failing test_login test in the auth module. Tests were passing yesterday but started failing after a recent merge.",
        "goal": "Fix the failing test and ensure all tests pass",
        "task_type": TaskType.DEBUG,
        "scenario": "healthy",
    },
    {
        "title": "Investigate flaky CI pipeline",
        "description": "CI pipeline intermittently failing on test_auth.py. Agent should identify root cause and fix the flaky test.",
        "goal": "Stabilize CI pipeline",
        "task_type": TaskType.INVESTIGATE,
        "scenario": "retry_loop",
    },
    {
        "title": "Review repo after dependency update",
        "description": "After updating dependencies, verify tests still pass. Cached memory says tests were green, but CI shows failures.",
        "goal": "Reconcile test status and fix any regressions",
        "task_type": TaskType.REVIEW,
        "scenario": "contradiction",
    },
    {
        "title": "Refactor and lint cleanup",
        "description": "Clean up linter errors and refactor auth module. First attempt may break things, but system should recover.",
        "goal": "Clean codebase with passing tests",
        "task_type": TaskType.REFACTOR,
        "scenario": "recovery",
    },
]


async def _run_demo(demo: dict) -> dict:
    scenario = demo["scenario"]
    req_data = {k: v for k, v in demo.items() if k != "scenario"}
    session_svc = await get_session_svc()
    runtime = await get_agent_runtime()

    req = CreateSessionRequest(**req_data)
    session = await session_svc.create(req)
    session = await session_svc.start(session.id)
    start_agent_task(runtime, session, scenario)
    return {"session_id": session.id, "title": session.title, "scenario": scenario}


@router.post("")
async def seed_all():
    """Create and run all demo scenarios."""
    results = []
    for demo in DEMO_SCENARIOS:
        result = await _run_demo(demo)
        results.append(result)
    return {"seeded": len(results), "sessions": results}


@router.post("/{scenario}")
async def seed_single(scenario: str):
    """Create and run a single demo scenario."""
    demo_map = {d["scenario"]: d for d in DEMO_SCENARIOS}
    if scenario not in demo_map:
        return {"error": f"Unknown scenario: {scenario}", "available": list(demo_map.keys())}
    return await _run_demo(demo_map[scenario])
