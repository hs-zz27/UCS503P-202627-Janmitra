"""Adapter selection.

One process, one adapter, chosen by configuration — so a load-test run can state which
mode produced its numbers, which the load-test report is required to record
(context.md §13).
"""

from __future__ import annotations

from functools import lru_cache

from app.adapters.model.base import ModelAdapter, ModelUnavailable
from app.adapters.model.failure import FailureModelAdapter
from app.adapters.model.mock import MockModelAdapter
from app.config import ModelAdapterMode, Settings, get_settings


def build_adapter(settings: Settings) -> ModelAdapter:
    match settings.model_adapter:
        case ModelAdapterMode.MOCK:
            return MockModelAdapter(
                latency_ms=settings.mock_latency_ms, failure_rate=settings.mock_failure_rate
            )
        case ModelAdapterMode.FAILURE:
            return FailureModelAdapter()
        case ModelAdapterMode.REAL:
            if not settings.gemini_api_key:
                raise ModelUnavailable(
                    "JANMITRA_MODEL_ADAPTER=real requires JANMITRA_GEMINI_API_KEY"
                )
            from app.adapters.model.gemini import (  # noqa: PLC0415 — optional dependency
                GeminiModelAdapter,
            )

            return GeminiModelAdapter(
                api_key=settings.gemini_api_key, model=settings.gemini_model
            )
    raise ModelUnavailable(f"unknown model adapter mode {settings.model_adapter!r}")


@lru_cache
def _cached_adapter(cache_key: tuple) -> ModelAdapter:
    return build_adapter(get_settings())


def get_model_adapter() -> ModelAdapter:
    """FastAPI dependency. Cached per settings so one adapter is shared per process."""
    settings = get_settings()
    return _cached_adapter(
        (settings.model_adapter, settings.mock_latency_ms, settings.mock_failure_rate)
    )
