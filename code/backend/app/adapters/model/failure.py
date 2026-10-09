"""Failure adapter: every call raises.

Exists so the "failed model calls must return a recoverable message and must not corrupt a
handoff or service record" requirement (context.md §13) has a test that can actually run.
"""

from __future__ import annotations

from app.adapters.model.base import (
    DraftRecord,
    Intent,
    IssueSummary,
    KnowledgeAnswer,
    ModelAdapter,
    ModelUnavailable,
)


class FailureModelAdapter(ModelAdapter):
    mode = "failure"

    async def extract_intent(self, utterance: str, *, language: str = "en") -> Intent:
        raise ModelUnavailable("failure adapter: model is unavailable")

    async def summarize_issue(self, transcript: str, *, language: str = "en") -> IssueSummary:
        raise ModelUnavailable("failure adapter: model is unavailable")

    async def answer_scheme_question(
        self,
        query: str,
        *,
        language: str = "en",
        reference_records: list[dict[str, object]] | None = None,
    ) -> KnowledgeAnswer:
        raise ModelUnavailable("failure adapter: model is unavailable")

    async def draft_service_record(self, source_text: str, *, source_url: str) -> DraftRecord:
        raise ModelUnavailable("failure adapter: model is unavailable")
