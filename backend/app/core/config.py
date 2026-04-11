from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Agent Black Box"
    app_version: str = "0.1.0"
    debug: bool = True

    redis_url: str = "redis://localhost:6379"
    redis_prefix: str = "abb:"

    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    allowed_repo_hosts: List[str] = ["github.com"]

    max_events_per_session: int = 10000
    checkpoint_auto_interval: int = 10  # events between auto-checkpoints
    safety_check_interval: int = 3  # events between safety checks

    retry_loop_threshold: int = 3
    drift_threshold: float = 0.6
    budget_event_limit: int = 200
    budget_time_limit_seconds: int = 600
    stall_event_threshold: int = 10

    agent_step_delay_ms: int = 800  # delay between simulated agent steps
    real_execution_enabled: bool = False

    openai_api_key: str | None = None
    openai_model_planner: str = "gpt-5-mini"
    openai_model_summary: str = "gpt-5-nano"
    openai_timeout_seconds: int = 60
    openai_max_retries: int = 2

    blaxel_api_key: str | None = None
    bl_workspace: str | None = None
    blaxel_region: str = "us-pdx-1"
    blaxel_image: str = "blaxel/base-image:latest"
    blaxel_memory_mb: int = 4096
    blaxel_sandbox_ttl: int = 3600
    blaxel_max_list_files: int = 40

    task_max_steps: int = 5
    command_timeout_ms: int = 60000
    lock_ttl_seconds: int = 120
    idempotency_ttl_seconds: int = 3600
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 10
    run_state_ttl_seconds: int = 7200
    artifact_ttl_seconds: int = 86400
    max_command_output_chars: int = 20000
    max_artifact_preview_chars: int = 8000
    git_access_token: str | None = None

    approval_timeout_seconds: int = 300
    auto_approve_low_risk: bool = True
    risky_action_types: List[str] = ["write_file", "run_command"]

    model_config = {"env_file": ".env", "env_prefix": "ABB_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
