"""Operator queue routes (FR-08).

The operator sees the queue entry *and* the conversation that produced it, because a
callback without context is exactly the experience the handoff exists to avoid.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import HandoffStatus
from app.modules.audit import service as audit
from app.modules.conversation import service as conversations
from app.modules.handoff import service as handoffs
from app.schemas.api import (
    ConversationEventView,
    ConversationView,
    HandoffContextView,
    UpdateHandoffRequest,
)
from app.schemas.tools import HandoffView
from app.security import Role, require

router = APIRouter(
    prefix="/v1/handoffs",
    tags=["handoff"],
    dependencies=[Depends(require(Role.OPERATOR, Role.ADMIN))],
)


@router.get("", response_model=list[HandoffView])
async def list_queue(
    status_filter: HandoffStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[HandoffView]:
    rows = await handoffs.queue(session, status=status_filter, limit=limit, offset=offset)
    return [HandoffView.model_validate(row) for row in rows]


@router.get("/{handoff_id}", response_model=HandoffContextView)
async def get_handoff(
    handoff_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> HandoffContextView:
    try:
        handoff = await handoffs.get(session, handoff_id)
    except handoffs.HandoffNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such handoff") from None

    conversation = await conversations.get(session, handoff.conversation_id)
    view = ConversationView.model_validate(conversation)
    view.time_to_guidance_seconds = conversations.time_to_guidance(conversation).seconds
    events = await conversations.events(session, conversation.id)
    return HandoffContextView(
        handoff=HandoffView.model_validate(handoff),
        conversation=view,
        events=[ConversationEventView.model_validate(event) for event in events],
    )


@router.patch("/{handoff_id}", response_model=HandoffView)
async def update_handoff(
    handoff_id: uuid.UUID,
    payload: UpdateHandoffRequest,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.OPERATOR, Role.ADMIN)),
) -> HandoffView:
    try:
        handoff = await handoffs.get(session, handoff_id)
    except handoffs.HandoffNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such handoff") from None

    previous = handoff.status
    try:
        handoff = await handoffs.update_status(
            session, handoff, payload.status, operator_notes=payload.operator_notes
        )
    except handoffs.InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit.record(
        session,
        action="handoff.status_changed",
        actor=role.value,
        conversation_id=handoff.conversation_id,
        entity_type="handoff_request",
        entity_id=str(handoff.id),
        payload={"from": previous, "to": handoff.status},
    )
    return HandoffView.model_validate(handoff)
