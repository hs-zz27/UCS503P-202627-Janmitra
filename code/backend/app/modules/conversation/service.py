"""Conversation state and the Time-to-Guidance clock.

Conversational state lives here — in Postgres, not in a worker's memory — which is what
lets the API run as N identical replicas behind a load balancer (proposal §7).

TTG is the primary evaluation metric, so its two timestamps are written by the system that
owns them: `connected_at` when the call is answered, `first_guidance_at` the first time a
tool returns a grounded, cited answer. Neither is ever back-filled.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import get_request_id
from app.models import Conversation, ConversationEvent, ConversationStatus


class ConversationNotFound(LookupError):
    pass


class ConversationClosed(RuntimeError):
    """A tool was called on a call that has already ended."""


@dataclass(frozen=True)
class TimeToGuidance:
    connected_at: datetime | None
    first_guidance_at: datetime | None

    @property
    def seconds(self) -> float | None:
        if self.connected_at is None or self.first_guidance_at is None:
            return None
        return (self.first_guidance_at - self.connected_at).total_seconds()


async def create(
    session: AsyncSession,
    *,
    channel: str,
    language: str | None = None,
    livekit_room: str | None = None,
    sip_call_id: str | None = None,
    connected_at: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> Conversation:
    conversation = Conversation(
        channel=channel,
        language=language,
        livekit_room=livekit_room,
        sip_call_id=sip_call_id,
        connected_at=connected_at or datetime.now(UTC),
        extra=extra or {},
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get(
    session: AsyncSession, conversation_id: uuid.UUID, *, for_update: bool = False
) -> Conversation:
    conversation = await session.get(
        Conversation, conversation_id, with_for_update=for_update, populate_existing=for_update
    )
    if conversation is None:
        raise ConversationNotFound(str(conversation_id))
    return conversation


async def get_active(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    # Serialize the complete tool/state transition, not just event sequence allocation.
    conversation = await get(session, conversation_id, for_update=True)
    if conversation.status != ConversationStatus.ACTIVE or conversation.ended_at is not None:
        raise ConversationClosed(str(conversation_id))
    return conversation


async def append_event(
    session: AsyncSession,
    conversation: Conversation,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> ConversationEvent:
    """Append one turn-level event.

    Locking the parent conversation serializes sequence allocation for this call across
    transcript callbacks, tool requests, and API replicas. The unique constraint remains
    the final integrity guard, but normal concurrent writes no longer race on `MAX(seq)`.
    """
    locked_status = (
        await session.execute(_event_lock_statement(conversation.id))
    ).scalar_one_or_none()
    if locked_status is None:
        raise ConversationNotFound(str(conversation.id))
    if locked_status != ConversationStatus.ACTIVE:
        raise ConversationClosed(str(conversation.id))

    highest = (
        await session.execute(
            select(func.max(ConversationEvent.seq)).where(
                ConversationEvent.conversation_id == conversation.id
            )
        )
    ).scalar_one_or_none()
    event = ConversationEvent(
        conversation_id=conversation.id,
        seq=(highest or 0) + 1,
        kind=kind,
        payload=payload or {},
        request_id=get_request_id(),
    )
    session.add(event)
    await session.flush()
    return event


async def mark_guidance_delivered(
    session: AsyncSession, conversation: Conversation, *, at: datetime | None = None
) -> None:
    """Stop the TTG clock. Written once — later grounded answers do not move it."""
    if conversation.first_guidance_at is None:
        conversation.first_guidance_at = at or datetime.now(UTC)
        await session.flush()


async def note_tool_failure(session: AsyncSession, conversation: Conversation) -> int:
    conversation.tool_failure_streak += 1
    await session.flush()
    return conversation.tool_failure_streak


async def clear_tool_failures(session: AsyncSession, conversation: Conversation) -> None:
    if conversation.tool_failure_streak:
        conversation.tool_failure_streak = 0
        await session.flush()


async def set_category(
    session: AsyncSession, conversation: Conversation, category: str | None
) -> None:
    if category and conversation.category != category:
        conversation.category = category
        await session.flush()


async def end(
    session: AsyncSession, conversation: Conversation, *, status: str = ConversationStatus.ENDED
) -> Conversation:
    if status not in {ConversationStatus.ENDED, ConversationStatus.HANDED_OFF}:
        raise ValueError("a conversation can only end in a terminal status")
    conversation = await get_active(session, conversation.id)
    conversation.status = status
    conversation.ended_at = datetime.now(UTC)
    await session.flush()
    return conversation


def time_to_guidance(conversation: Conversation) -> TimeToGuidance:
    return TimeToGuidance(
        connected_at=conversation.connected_at,
        first_guidance_at=conversation.first_guidance_at,
    )


def _event_lock_statement(conversation_id: uuid.UUID):
    return (
        select(Conversation.status)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )


async def events(session: AsyncSession, conversation_id: uuid.UUID) -> list[ConversationEvent]:
    return list(
        (
            await session.execute(
                select(ConversationEvent)
                .where(ConversationEvent.conversation_id == conversation_id)
                .order_by(ConversationEvent.seq)
            )
        ).scalars()
    )
