"""Deterministic mock adapter.

Used by every load test, failure test and unit test. Deterministic is the requirement: the
same utterance must give the same intent on every run, or a capacity number means nothing.
Latency and failure rate are injectable so the load harness can model a slow or flaky
provider without paying one (context.md §12).
"""

from __future__ import annotations

import asyncio
import hashlib

from app.adapters.model.base import (
    DraftRecord,
    Intent,
    IntentAction,
    IssueSummary,
    ModelAdapter,
    ModelUnavailable,
)
from app.schemas.service_record import ServiceCategory

_HUMAN_PHRASES = (
    "talk to a person", "speak to someone", "human", "operator", "agent",
    "kisi se baat", "vyakti se baat",
)
_CATEGORY_HINTS: dict[ServiceCategory, tuple[str, ...]] = {
    ServiceCategory.LOAN: ("loan", "credit", "borrow", "udhaar", "karz", "rin"),
    ServiceCategory.BANKING: ("bank", "account", "khata", "passbook", "deposit"),
    ServiceCategory.GRANT: ("grant", "subsidy", "assistance", "anudan", "sahayata"),
    ServiceCategory.INSURANCE: ("insurance", "bima", "cover"),
    ServiceCategory.PENSION: ("pension", "old age", "vridha", "budhapa"),
}
_ELIGIBILITY_HINTS = ("eligible", "qualify", "can i get", "patra", "yogya")


class MockModelAdapter(ModelAdapter):
    mode = "mock"

    def __init__(self, *, latency_ms: int = 0, failure_rate: float = 0.0) -> None:
        self._latency_ms = latency_ms
        self._failure_rate = failure_rate

    async def _simulate(self, key: str) -> None:
        if self._latency_ms:
            await asyncio.sleep(self._latency_ms / 1000)
        if self._failure_rate > 0 and _stable_unit_interval(key) < self._failure_rate:
            raise ModelUnavailable("mock adapter: injected failure")

    async def extract_intent(self, utterance: str, *, language: str = "en") -> Intent:
        await self._simulate(utterance)
        lowered = utterance.lower()

        if any(phrase in lowered for phrase in _HUMAN_PHRASES):
            return Intent(
                action=IntentAction.REQUEST_HANDOFF,
                query=utterance,
                confidence=0.95,
                wants_human=True,
                language=language,
            )

        category = next(
            (cat for cat, hints in _CATEGORY_HINTS.items() if any(h in lowered for h in hints)),
            None,
        )
        if any(hint in lowered for hint in _ELIGIBILITY_HINTS):
            action = IntentAction.CHECK_ELIGIBILITY
        elif category is not None:
            action = IntentAction.FIND_SERVICE
        else:
            action = IntentAction.CLARIFY

        # Confidence tracks how much of the utterance the mock actually recognised, so a
        # vague request deterministically lands below the handoff threshold.
        confidence = 0.9 if category else 0.3
        return Intent(
            action=action,
            category=category,
            query=utterance,
            confidence=confidence,
            language=language,
        )

    async def summarize_issue(self, transcript: str, *, language: str = "en") -> IssueSummary:
        await self._simulate(transcript)
        collapsed = " ".join(transcript.split())
        return IssueSummary(summary=collapsed[:1000] or "(no summary captured)", language=language)

    async def draft_service_record(self, source_text: str, *, source_url: str) -> DraftRecord:
        await self._simulate(source_url)
        first_line = next((line.strip() for line in source_text.splitlines() if line.strip()), "")
        return DraftRecord(
            fields={
                "name": {"en": first_line[:120]},
                "description": {"en": " ".join(source_text.split())[:400]},
                "citation": {"source_url": source_url},
            },
            evidence={"name": first_line[:200]},
        )


def _stable_unit_interval(key: str) -> float:
    """Hash-derived pseudo-random in [0, 1) — same input, same verdict, every run."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64
