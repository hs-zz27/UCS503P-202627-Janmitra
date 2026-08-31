"""Session routes.

The voice worker opens a conversation when a call connects and closes it when the call
ends. Everything in between — turns, tool calls, the TTG timestamps — is written here
rather than kept in the worker, which is what allows any replica to serve any request
(proposal §7).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.modules.audit import service as audit
from app.modules.conversation import service as conversations
from app.schemas.api import (
    AppendEventRequest,
    ConversationEventView,
    ConversationView,
    CreateConversationRequest,
    EndConversationRequest,
)
from app.security import Role, current_role, require

router = APIRouter(prefix="/v1/conversations", tags=["conversation"])


def _view(conversation) -> ConversationView:
    view = ConversationView.model_validate(conversation)
    view.time_to_guidance_seconds = conversations.time_to_guidance(conversation).seconds
    return view


@router.post("", response_model=ConversationView, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationRequest,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.VOICE, Role.ADMIN)),
) -> ConversationView:
    conversation = await conversations.create(
        session,
        channel=payload.channel.value,
        language=payload.language,
        livekit_room=payload.livekit_room,
        sip_call_id=payload.sip_call_id,
        connected_at=payload.connected_at,
        extra=payload.extra,
    )
    await audit.record(
        session,
        action="conversation.created",
        actor=role.value,
        conversation_id=conversation.id,
        entity_type="conversation",
        entity_id=str(conversation.id),
        payload={"channel": payload.channel.value},
    )
    return _view(conversation)


@router.get("/{conversation_id}", response_model=ConversationView)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(current_role),
) -> ConversationView:
    return _view(await conversations.get(session, conversation_id))


@router.get("/{conversation_id}/events", response_model=list[ConversationEventView])
async def list_events(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(current_role),
) -> list[ConversationEventView]:
    await conversations.get(session, conversation_id)
    return [
        ConversationEventView.model_validate(event)
        for event in await conversations.events(session, conversation_id)
    ]


@router.post(
    "/{conversation_id}/events",
    response_model=ConversationEventView,
    status_code=status.HTTP_201_CREATED,
)
async def append_event(
    conversation_id: uuid.UUID,
    payload: AppendEventRequest,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.VOICE, Role.ADMIN)),
) -> ConversationEventView:
    conversation = await conversations.get_active(session, conversation_id)
    event = await conversations.append_event(
        session, conversation, kind=payload.kind, payload=payload.payload
    )
    return ConversationEventView.model_validate(event)


@router.post("/{conversation_id}/end", response_model=ConversationView)
async def end_conversation(
    conversation_id: uuid.UUID,
    payload: EndConversationRequest,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.VOICE, Role.ADMIN)),
) -> ConversationView:
    conversation = await conversations.get(session, conversation_id)
    if conversation.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="conversation has already ended"
        )
    conversation = await conversations.end(session, conversation, status=payload.status.value)
    ttg = conversations.time_to_guidance(conversation)
    await audit.record(
        session,
        action="conversation.ended",
        actor=role.value,
        conversation_id=conversation.id,
        entity_type="conversation",
        entity_id=str(conversation.id),
        payload={"status": conversation.status, "time_to_guidance_seconds": ttg.seconds},
    )
    return _view(conversation)
