from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.execution_guard_service import ExecutionGuardError, ExecutionGuardService


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_configuration_errors_surface_missing_real_provider_env(monkeypatch):
    monkeypatch.setenv("ABB_REAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("ABB_REDIS_URL", "localhost:6379")
    service = ExecutionGuardService()

    errors = service.configuration_errors()

    assert "ABB_OPENAI_API_KEY is not configured" in errors
    assert "ABB_BLAXEL_API_KEY is not configured" in errors
    assert "ABB_BL_WORKSPACE is not configured" in errors
    assert "ABB_REDIS_URL must be a full redis:// or rediss:// URL" in errors


def test_validate_repo_url_rejects_unapproved_host(monkeypatch):
    monkeypatch.setenv("ABB_ALLOWED_REPO_HOSTS", '["github.com"]')
    service = ExecutionGuardService()

    with pytest.raises(ExecutionGuardError, match="not in ABB_ALLOWED_REPO_HOSTS"):
        service.validate_repo_url("https://gitlab.com/example/repo.git")


def test_validate_command_blocks_shell_control_operators():
    service = ExecutionGuardService()

    with pytest.raises(ExecutionGuardError, match="Blocked command token"):
        service.validate_command("pytest tests/ && echo done")


def test_validate_command_allows_safe_test_commands():
    service = ExecutionGuardService()

    assert service.validate_command("pytest tests/") == "pytest tests/"
