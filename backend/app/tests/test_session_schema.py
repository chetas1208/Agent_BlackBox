from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.session import CreateSessionRequest


def test_real_session_requires_repo_url():
    with pytest.raises(ValidationError):
        CreateSessionRequest(
            title="Real task",
            goal="Run against repo",
            task_type="debug",
            execution_mode="real",
        )


def test_demo_session_defaults_to_local_mock():
    req = CreateSessionRequest(
        title="Demo task",
        goal="Run locally",
        task_type="debug",
        execution_mode="demo",
    )

    assert req.sandbox_profile == "local_mock"


def test_real_session_defaults_to_blaxel_profile():
    req = CreateSessionRequest(
        title="Real task",
        goal="Run in sandbox",
        task_type="debug",
        execution_mode="real",
        repo_url="https://github.com/example/repo.git",
    )

    assert req.sandbox_profile == "blaxel"
