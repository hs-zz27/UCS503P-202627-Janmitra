"""The model adapter interface.

One interface, three modes — real, mock and failure (context.md §11.7). Functional demos
and the AI-evaluation set run against the real provider; load and failure testing run
against the mock, so capacity numbers cost nothing and are repeatable.

Every method returns a *validated* Pydantic model. That is the invariant from context.md
§8.3 in code form: model output that does not fit the schema never reaches a backend tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.service_record import ServiceCategory


class ModelUnavailable(RuntimeError):
    """The provider could not be reached or refused the call. Callers must degrade
    gracefully — never corrupt a handoff or a service record (context.md §13)."""


class ModelOutputInvalid(ValueError):
    """The provider replied, but the reply did not fit the schema."""


class IntentAction(StrEnum):
    FIND_SERVICE = "find_service"
    CHECK_ELIGIBILITY = "check_eligibility"
    REQUEST_HANDOFF = "request_handoff"
    CLARIFY = "clarify"


class Intent(BaseModel):
    """A free-form citizen utterance turned into a typed action (context.md §8.3)."""

    model_config = ConfigDict(extra="forbid")

    action: IntentAction
    category: ServiceCategory | None = None
    query: str | None = None
    #: Eligibility answers the citizen volunteered, keyed by question id.
    answers: dict[str, str | int | float | bool] = Field(default_factory=dict)
    #: The model's own confidence. Advisory input to a deterministic trigger, never the
    #: trigger itself.
    confidence: float = Field(ge=0.0, le=1.0)
    wants_human: bool = False
    language: str = "en"


class IssueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    language: str = "en"


class DraftRecord(BaseModel):
    """Fields proposed from an imported source, for human review. Deliberately loose: the
    reviewer, not the model, is what makes it a service record (context.md §18.3)."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, object]
    #: Sentences from the source the model says it drew each field from.
    evidence: dict[str, str] = Field(default_factory=dict)


class ModelAdapter(ABC):
    """Implementations must be safe to call concurrently from every API replica."""

    mode: str

    @abstractmethod
    async def extract_intent(self, utterance: str, *, language: str = "en") -> Intent: ...

    @abstractmethod
    async def summarize_issue(self, transcript: str, *, language: str = "en") -> IssueSummary: ...

    @abstractmethod
    async def draft_service_record(self, source_text: str, *, source_url: str) -> DraftRecord: ...
