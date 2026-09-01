"""The typed tool endpoints the voice agent calls.

`find_service`, `check_eligibility`, `get_documents` and `request_handoff` are the only way
verified facts leave the system. The model chooses *which* tool to call and explains what
comes back; it never supplies the facts, the eligibility verdict, or the handoff record
(context.md §8.3).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.model.base import ModelAdapter, ModelUnavailable
from app.adapters.model.factory import get_model_adapter
from app.config import Settings, get_settings
from app.db import get_session
from app.models import ConversationStatus
from app.modules.audit import service as audit
from app.modules.catalogue import service as catalogue
from app.modules.conversation import service as conversations
from app.modules.eligibility import engine
from app.modules.handoff import service as handoffs
from app.schemas.service_record import ServiceRecord
from app.schemas.tools import (
    CheckEligibilityRequest,
    CheckEligibilityResponse,
    FindServiceRequest,
    FindServiceResponse,
    GetDocumentsRequest,
    GetDocumentsResponse,
    HandoffView,
    RequestHandoffRequest,
    RequestHandoffResponse,
    ServiceSummary,
)
from app.security import Role, require

logger = logging.getLogger("janmitra.tools")

router = APIRouter(
    prefix="/v1/tools",
    tags=["tools"],
    dependencies=[Depends(require(Role.VOICE, Role.ADMIN))],
)

DISCLAIMER = {
    "en": (
        "This is guidance based on the official source, not an official decision. "
        "The final decision rests with the department."
    ),
    "hi": (
        "Yah sarkari srot par aadharit maargdarshan hai, koi aadhikarik nirnay nahin. "
        "Antim nirnay vibhag ka hoga."
    ),
}


def _disclaimer(language: str) -> str:
    return DISCLAIMER.get(language, DISCLAIMER["en"])


def _summary(
    published: catalogue.PublishedService, language: str, *, score: float | None = None,
    matched_on: str | None = None,
) -> ServiceSummary:
    record: ServiceRecord = published.record
    return ServiceSummary(
        slug=record.slug,
        name=engine.localized(record.name, language),
        category=record.category,
        description=engine.localized(record.description, language),
        benefit_summary=(
            engine.localized(record.benefit_summary, language) if record.benefit_summary else None
        ),
        eligibility_summary=(
            engine.localized(record.eligibility_summary, language)
            if record.eligibility_summary
            else None
        ),
        is_rule_backed=record.is_rule_backed,
        service_version=published.version,
        citation=record.citation,
        score=score,
        matched_on=matched_on,
    )


@router.post("/find_service", response_model=FindServiceResponse)
async def find_service(
    payload: FindServiceRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FindServiceResponse:
    """Discover schemes in the published catalogue (FR-02, FR-03)."""
    conversation = await conversations.get_active(session, payload.conversation_id)
    await conversations.set_category(
        session, conversation, payload.category.value if payload.category else None
    )

    matches = await catalogue.search(
        session, payload.query, category=payload.category, limit=payload.limit
    )

    trigger = None
    if matches:
        await conversations.clear_tool_failures(session, conversation)
        # A cited scheme match is guidance, so this is where the TTG clock stops
        # (proposal §6.1).
        await conversations.mark_guidance_delivered(session, conversation)
    else:
        trigger = handoffs.decide_trigger(settings, match_count=0)

    await conversations.append_event(
        session,
        conversation,
        kind="tool.find_service",
        payload={
            "query": payload.query,
            "category": payload.category.value if payload.category else None,
            "match_slugs": [m.record.slug for m in matches],
        },
    )
    await audit.record(
        session,
        action="tool.find_service",
        actor="voice",
        conversation_id=conversation.id,
        entity_type="service",
        entity_id=matches[0].record.slug if matches else None,
        payload={"query": payload.query, "matches": len(matches)},
    )

    return FindServiceResponse(
        matches=[
            _summary(match, payload.language, score=match.score, matched_on=match.matched_on)
            for match in matches
        ],
        suggested_handoff_trigger=trigger,
        asked_category=payload.category,
    )


@router.post("/check_eligibility", response_model=CheckEligibilityResponse)
async def check_eligibility(
    payload: CheckEligibilityRequest,
    session: AsyncSession = Depends(get_session),
) -> CheckEligibilityResponse:
    """Run the deterministic rule engine for one scheme (FR-05)."""
    conversation = await conversations.get_active(session, payload.conversation_id)
    try:
        published = await catalogue.get_published(session, payload.slug)
    except catalogue.ServiceNotFound:
        await conversations.note_tool_failure(session, conversation)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no published service {payload.slug!r}",
        ) from None

    record = published.record
    if record.rule_set is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"service {payload.slug!r} has no eligibility rule set; "
                "offer the document checklist and citation instead"
            ),
        )

    try:
        result = engine.evaluate(record.rule_set, payload.answers, language=payload.language)
    except engine.AnswerValidationError as exc:
        # A bad extraction is a validation failure, never a wrong eligibility verdict.
        await conversations.note_tool_failure(session, conversation)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "answers did not validate", "errors": exc.errors},
        ) from exc

    documents = engine.build_document_checklist(record, payload.answers, language=payload.language)
    pending = engine.next_questions(record.rule_set, payload.answers, language=payload.language)

    await conversations.clear_tool_failures(session, conversation)
    await conversations.set_category(session, conversation, record.category.value)
    if result.outcome is not engine.Outcome.NEEDS_MORE_INFO:
        # Only a decided result is guidance; a follow-up question is not, so it must not
        # flatter the TTG number.
        await conversations.mark_guidance_delivered(session, conversation)

    await conversations.append_event(
        session,
        conversation,
        kind="tool.check_eligibility",
        payload={
            "slug": payload.slug,
            "service_version": published.version,
            "outcome": result.outcome.value,
            "answered": sorted(payload.answers),
        },
    )
    await audit.record(
        session,
        action="tool.check_eligibility",
        actor="voice",
        conversation_id=conversation.id,
        entity_type="service_version",
        entity_id=str(published.version_id),
        payload={
            "slug": payload.slug,
            "outcome": result.outcome.value,
            "failed_conditions": result.failed_conditions,
        },
    )

    return CheckEligibilityResponse(
        slug=payload.slug,
        outcome=result.outcome.value,
        conditions=[condition.__dict__ for condition in result.conditions],
        missing_answers=result.missing_answers,
        failed_conditions=result.failed_conditions,
        next_questions=pending,
        documents=documents,
        service_version=published.version,
        citation=record.citation,
        disclaimer=_disclaimer(payload.language),
    )


@router.post("/get_documents", response_model=GetDocumentsResponse)
async def get_documents(
    payload: GetDocumentsRequest,
    session: AsyncSession = Depends(get_session),
) -> GetDocumentsResponse:
    """Document checklist for any published scheme, rule-backed or not (FR-06)."""
    conversation = await conversations.get_active(session, payload.conversation_id)
    try:
        published = await catalogue.get_published(session, payload.slug)
    except catalogue.ServiceNotFound:
        await conversations.note_tool_failure(session, conversation)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no published service {payload.slug!r}",
        ) from None

    try:
        documents = engine.build_document_checklist(
            published.record, payload.answers, language=payload.language
        )
    except engine.AnswerValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "answers did not validate", "errors": exc.errors},
        ) from exc

    await conversations.clear_tool_failures(session, conversation)
    await conversations.mark_guidance_delivered(session, conversation)
    await conversations.append_event(
        session,
        conversation,
        kind="tool.get_documents",
        payload={"slug": payload.slug, "service_version": published.version},
    )
    await audit.record(
        session,
        action="tool.get_documents",
        actor="voice",
        conversation_id=conversation.id,
        entity_type="service_version",
        entity_id=str(published.version_id),
        payload={"slug": payload.slug, "documents": len(documents)},
    )

    return GetDocumentsResponse(
        slug=payload.slug,
        documents=documents,
        service_version=published.version,
        citation=published.record.citation,
    )


@router.post("/request_handoff", response_model=RequestHandoffResponse, status_code=201)
async def request_handoff(
    payload: RequestHandoffRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    model: ModelAdapter = Depends(get_model_adapter),
) -> RequestHandoffResponse:
    """Queue a human handoff (FR-07).

    The trigger is computed here from reported signals; if none fires, the tool refuses and
    the agent goes on helping. That refusal is the deterministic half of the handoff
    precision/recall measurement in context.md §14.
    """
    conversation = await conversations.get_active(session, payload.conversation_id)

    trigger = handoffs.decide_trigger(
        settings,
        citizen_asked_for_person=payload.citizen_asked_for_person,
        match_count=payload.match_count,
        agent_confidence=payload.agent_confidence,
        tool_failure_streak=conversation.tool_failure_streak,
        out_of_scope=payload.out_of_scope,
    )
    if trigger is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no handoff trigger fired; continue self-service",
        )

    summary = (payload.issue_summary or "").strip()
    if not summary and payload.transcript:
        try:
            drafted = await model.summarize_issue(payload.transcript, language=payload.language)
            summary = drafted.summary
        except ModelUnavailable:
            # Degrade, never drop the citizen: the raw transcript is worse prose but it is
            # still the context the operator needs (context.md §13).
            logger.warning("summary model unavailable; falling back to transcript")
            summary = " ".join(payload.transcript.split())[:1000]
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="issue_summary or transcript is required",
        )

    handoff = await handoffs.create(
        session,
        conversation,
        issue_summary=summary,
        trigger_reason=trigger,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
    )
    await conversations.append_event(
        session,
        conversation,
        kind="tool.request_handoff",
        payload={"handoff_id": str(handoff.id), "trigger_reason": trigger.value},
    )
    await audit.record(
        session,
        action="handoff.created",
        actor="voice",
        conversation_id=conversation.id,
        entity_type="handoff_request",
        entity_id=str(handoff.id),
        payload={"trigger_reason": trigger.value, "has_phone": bool(handoff.contact_phone)},
    )
    await conversations.end(session, conversation, status=ConversationStatus.HANDED_OFF.value)

    return RequestHandoffResponse(
        handoff=HandoffView.model_validate(handoff),
        spoken_confirmation=_spoken_confirmation(handoff, payload.language),
    )


def _spoken_confirmation(handoff, language: str) -> str:
    """Framed as a helpline transfer, not a ticket — no case ID is read out (context.md §5)."""
    name = handoff.contact_name
    if language == "hi":
        who = f"{name} ji, " if name else ""
        return f"{who}main aapko aise vyakti se jodta hoon jo madad kar sakein."
    who = f"{name}, " if name else ""
    return f"{who}I am passing this to someone who can help you directly."
