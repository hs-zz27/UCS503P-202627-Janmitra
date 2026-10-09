"""Application settings.

Everything that differs between local, staging and the load-test rig is read from the
environment, so the same image runs in all three (context.md §12: replicas are identical
and stateless).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    database_url: str = "postgresql+asyncpg://janmitra:janmitra@localhost:5438/janmitra"
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)
    db_echo: bool = False

    # Model adapter (context.md §11.7). Load and failure tests never touch the real provider.
    model_adapter: ModelAdapterMode = ModelAdapterMode.MOCK
    mock_latency_ms: int = Field(default=0, ge=0)
    mock_failure_rate: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    catalogue_data_dir: Path = Path("data")

    # Seeded demo accounts instead of a registration/OAuth product (context.md §11.6).
    admin_api_key: str = "dev-admin-key"
    operator_api_key: str = "dev-operator-key"
    voice_api_key: str = "dev-voice-key"

    # Optional LiveKit/Gemini voice worker. It uses the typed HTTP tool surface and never
    # reads the database directly.
    backend_base_url: str = "http://127.0.0.1:8000"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "janmitra-agent"
    gemini_live_model: Literal["gemini-3.1-flash-live-preview"] = "gemini-3.1-flash-live-preview"
    gemini_live_voice: str = "Puck"
    gemini_live_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"

    # Deterministic handoff trigger thresholds (context.md §18.3). Kept in config so the
    # labelled precision/recall run in §14 can be repeated against a recorded value.
    handoff_confidence_threshold: float = Field(default=0.55, ge=0, le=1, allow_inf_nan=False)
    handoff_tool_failure_streak: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _distinct_role_keys(self) -> Settings:
        keys = (self.admin_api_key, self.operator_api_key, self.voice_api_key)
        if any(not key.strip() for key in keys) or len(set(keys)) != 3:
            raise ValueError("API keys must be nonempty and distinct for each role")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
