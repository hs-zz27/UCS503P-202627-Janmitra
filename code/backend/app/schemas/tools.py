"""Typed tool envelopes.

These are the contracts the LiveKit voice worker binds as Gemini Live tools. They are
plain HTTP endpoints first and tools second, deliberately: built and unit-tested on their
own, a model failure can never look like a logic bug (context.md §18.2).

Every factual response carries `citation` and `service_version`, because FR-04 requires the
source and its verification date on every factual answer, and a citation without a version
cannot be checked later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import HandoffTrigger
from app.schemas.service_record import Citation, ServiceCategory


class ToolRequest(BaseModel):
    """Common to every tool call: which call is this for, and in which language do we speak."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    language: str = "en"


class ServiceSummary(BaseModel):
    """What the agent needs to say a scheme's name and cite it — not the whole record."""

    slug: str
    name: str
    category: ServiceCategory
    description: str
    benefit_summary: str | None = None
    eligibility_summary: str | None = None
    first_action: str | None = None
    is_rule_backed: bool
    service_version: int
    citation: Citation
    score: float | None = None
    matched_on: str | None = None


class FindServiceRequest(ToolRequest):
    query: str = Field(min_length=1, max_length=500)
    #: Category-first discovery narrows the search before free-form matching (FR-02).
    category: ServiceCategory | None = None
    limit: int = Field(default=3, ge=1, le=10)
    #: Realtime voice already has a language model: return retrieval context directly
    #: rather than waiting for a second model to draft the same answer.
    response_mode: Literal["prepared_answer", "context"] = "prepared_answer"


class FindServiceResponse(BaseModel):
    matches: list[ServiceSummary]
    #: An empty verified catalogue is not a reason to stop helping. These fields make the
    #: permitted trained-knowledge fallback explicit in the model-visible tool result.
    knowledge_fallback_allowed: bool = False
    response_guidance: str | None = None
    answer_to_citizen: str | None = None
    answer_basis: (
        Literal[
            "pending_catalogue_and_trained_knowledge",
            "trained_knowledge",
            "pending_catalogue",
            "published_and_pending_catalogue",
            "no_matching_reference",
        ]
        | None
    ) = None
    reference_slugs: list[str] = Field(default_factory=list)
    reference_context: list[dict[str, Any]] = Field(default_factory=list)
    context_order: list[str] = Field(default_factory=list)
    verification_state: Literal["verified", "unverified", "mixed"] = "verified"
    retrieval_elapsed_ms: float = Field(default=0, ge=0)
    #: Set when zero matches came back. The agent answers from general knowledge first and
    #: offers this handoff when the citizen wants current official verification.
    suggested_handoff_trigger: HandoffTrigger | None = None
    asked_category: ServiceCategory | None = None


class ConditionTrace(BaseModel):
    """One line of the explanation the agent reads back to the citizen."""

    id: str
    description: str
    applicable: bool | None
    passed: bool | None
    depends_on: str
    source_text: str | None = None


class PendingQuestion(BaseModel):
    id: str
    prompt: str
    type: str
    options: list[str] | None = None
    unit: str | None = None


class ChecklistItem(BaseModel):
    id: str
    name: str
    notes: str | None = None
    required: bool
    conditional: bool
    depends_on: str | None = None


class CheckEligibilityRequest(ToolRequest):
    slug: str
    answers: dict[str, Any] = Field(default_factory=dict)


class CheckEligibilityResponse(BaseModel):
    slug: str
    outcome: Literal["eligible", "not_eligible", "needs_more_info"]
    conditions: list[ConditionTrace]
    missing_answers: list[str]
    failed_conditions: list[str]
    next_questions: list[PendingQuestion]
    documents: list[ChecklistItem]
    service_version: int
    citation: Citation
    #: Read aloud with every result (context.md §8.1): guidance, not an official decision.
    disclaimer: str


class GetDocumentsRequest(ToolRequest):
    slug: str
    answers: dict[str, Any] = Field(default_factory=dict)


class GetDocumentsResponse(BaseModel):
    slug: str
    documents: list[ChecklistItem]
    service_version: int
    citation: Citation


class RequestHandoffRequest(ToolRequest):
    """The signals a deterministic trigger is computed from.

    The voice worker reports what it observed; `app.modules.handoff.service.decide_trigger`
    decides. If nothing fires, the tool refuses and the agent keeps helping.
    """

    model_config = ConfigDict(extra="forbid")

    issue_summary: str | None = Field(default=None, max_length=2000)
    #: Used to draft a summary when the citizen did not give one in so many words.
    transcript: str | None = Field(default=None, max_length=8000)
    contact_name: str | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=20)
    citizen_asked_for_person: bool = False
    out_of_scope: bool = False
    match_count: int | None = None
    agent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class HandoffView(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    category: str | None
    contact_name: str | None
    contact_phone: str | None
    issue_summary: str
    trigger_reason: str
    status: str
    language: str | None
    operator_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestHandoffResponse(BaseModel):
    handoff: HandoffView
    #: Short, spoken confirmation the agent reads back before ending (context.md §5).
    spoken_confirmation: str
