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

    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    max_events_per_session: int = 10000
    checkpoint_auto_interval: int = 10
    safety_check_interval: int = 3

    retry_loop_threshold: int = 3
    drift_threshold: float = 0.6
    budget_event_limit: int = 200
    budget_time_limit_seconds: int = 600
    stall_event_threshold: int = 10

    agent_step_delay_ms: int = 800

    # Sandbox profile: "blaxel" | "local_mock"
    sandbox_profile: str = "local_mock"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_max_iterations: int = 30

    model_config = {"env_file": ".env", "env_prefix": "ABB_", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
