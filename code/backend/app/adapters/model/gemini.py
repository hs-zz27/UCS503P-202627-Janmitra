"""Real adapter — Gemini, used for functional demos and the AI-evaluation run.

Scope note: this adapter covers the *text and structured-extraction* calls the backend
makes. The realtime speech leg (Gemini Live inside the LiveKit worker) is the voice
worker's business and does not pass through the API — see the voice spike in context.md
§18.1.

`google-genai` is an optional dependency, imported lazily, so the backend, its tests and
the load rig all run with it absent.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.adapters.model.base import (
    DraftRecord,
    Intent,
    IssueSummary,
    ModelAdapter,
    ModelOutputInvalid,
    ModelUnavailable,
)

logger = logging.getLogger("janmitra.model.gemini")

_INTENT_INSTRUCTION = """You classify a citizen's spoken request to an Indian government
scheme helpline. Reply with JSON only, matching this shape:
{"action": "find_service|check_eligibility|request_handoff|clarify",
 "category": "loan|banking|grant|insurance|pension|other|null",
 "query": string, "answers": {}, "confidence": 0.0-1.0,
 "wants_human": bool, "language": BCP-47 tag}
Never invent scheme facts. If unsure, use action "clarify" with a low confidence."""

_SUMMARY_INSTRUCTION = """Summarise this citizen's problem in at most three sentences for a
human operator who will call them back. Reply with JSON only:
{"summary": string, "language": BCP-47 tag}. State only what the citizen said."""

_DRAFT_INSTRUCTION = """Extract government-scheme fields from the official source text
below. Reply with JSON only: {"fields": {...}, "evidence": {field: quoted sentence}}.
Copy values from the source; never infer a rule the source does not state. Omit any field
the source does not support."""


class GeminiModelAdapter(ModelAdapter):
    mode = "real"

    def __init__(self, *, api_key: str, model: str) -> None:
        try:
            from google import genai  # noqa: PLC0415 — optional dependency, imported lazily
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ModelUnavailable(
                "JANMITRA_MODEL_ADAPTER=real needs the 'gemini' extra: pip install -e '.[gemini]'"
            ) from exc
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract_intent(self, utterance: str, *, language: str = "en") -> Intent:
        payload = await self._json_call(
            _INTENT_INSTRUCTION, f"Spoken language hint: {language}\nUtterance: {utterance}"
        )
        payload.setdefault("language", language)
        payload.setdefault("query", utterance)
        return _validate(Intent, payload)

    async def summarize_issue(self, transcript: str, *, language: str = "en") -> IssueSummary:
        payload = await self._json_call(_SUMMARY_INSTRUCTION, transcript)
        payload.setdefault("language", language)
        return _validate(IssueSummary, payload)

    async def draft_service_record(self, source_text: str, *, source_url: str) -> DraftRecord:
        payload = await self._json_call(
            _DRAFT_INSTRUCTION, f"Source URL: {source_url}\n\n{source_text}"
        )
        return _validate(DraftRecord, payload)

    async def _json_call(self, instruction: str, content: str) -> dict[str, Any]:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=content,
                config={
                    "system_instruction": instruction,
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )
        except Exception as exc:  # provider SDK raises its own exception hierarchy
            logger.warning("gemini call failed", extra={"error": str(exc)})
            raise ModelUnavailable(str(exc)) from exc

        text = (response.text or "").strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelOutputInvalid(f"model did not return JSON: {text[:200]!r}") from exc
        if not isinstance(parsed, dict):
            raise ModelOutputInvalid(f"expected a JSON object, got {type(parsed).__name__}")
        return parsed


def _validate(model_cls, payload: dict[str, Any]):
    """Schema validation is the gate: unvalidated model output never reaches a tool."""
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise ModelOutputInvalid(str(exc)) from exc
