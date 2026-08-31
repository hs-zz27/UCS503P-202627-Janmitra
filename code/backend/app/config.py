"""Application settings.

Everything that differs between local, staging and the load-test rig is read from the
environment, so the same image runs in all three (context.md §12: replicas are identical
and stateless).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelAdapterMode(StrEnum):
    MOCK = "mock"
    FAILURE = "failure"
    REAL = "real"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JANMITRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://janmitra:janmitra@localhost:5432/janmitra"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # Model adapter (context.md §11.7). Load and failure tests never touch the real provider.
    model_adapter: ModelAdapterMode = ModelAdapterMode.MOCK
    mock_latency_ms: int = 0
    mock_failure_rate: float = 0.0
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    # Seeded demo accounts instead of a registration/OAuth product (context.md §11.6).
    admin_api_key: str = "dev-admin-key"
    operator_api_key: str = "dev-operator-key"
    voice_api_key: str = "dev-voice-key"

    # Deterministic handoff trigger thresholds (context.md §18.3). Kept in config so the
    # labelled precision/recall run in §14 can be repeated against a recorded value.
    handoff_confidence_threshold: float = 0.55
    handoff_tool_failure_streak: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
