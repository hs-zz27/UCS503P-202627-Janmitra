"""Human handoff.

Triggers are deterministic and live here, not in a prompt: the citizen asked for a person,
no scheme matched, the agent's confidence was below the configured threshold, or tools
failed repeatedly (context.md §18.3). The model can *report* a signal; it cannot decide a
handoff and it cannot write the record.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Conversation, HandoffRequest, HandoffStatus, HandoffTrigger

#: NEW → CONTACTED → RESOLVED, and nothing else (context.md §9).
_ALLOWED_TRANSITIONS: dict[HandoffStatus, set[HandoffStatus]] = {
    HandoffStatus.NEW: {HandoffStatus.CONTACTED, HandoffStatus.RESOLVED},
    HandoffStatus.CONTACTED: {HandoffStatus.RESOLVED},
    HandoffStatus.RESOLVED: set(),
}


class HandoffNotFound(LookupError):
    pass


class InvalidTransition(ValueError):
    def __init__(self, current: str, requested: str) -> None:
        super().__init__(f"cannot move a handoff from {current!r} to {requested!r}")
        self.current = current
        self.requested = requested


def decide_trigger(
    settings: Settings,
    *,
    citizen_asked_for_person: bool = False,
    match_count: int | None = None,
    agent_confidence: float | None = None,
    tool_failure_streak: int = 0,
    out_of_scope: bool = False,
) -> HandoffTrigger | None:
    """The single place that decides whether a call should go to a human.

    Ordered by how directly it reflects the citizen's own intent: an explicit request wins
    over any inference the system makes about them.
    """
    if citizen_asked_for_person:
        return HandoffTrigger.CITIZEN_REQUEST
    if tool_failure_streak >= settings.handoff_tool_failure_streak:
        return HandoffTrigger.TOOL_FAILURE
    if out_of_scope:
        return HandoffTrigger.OUT_OF_SCOPE
    if match_count == 0:
        return HandoffTrigger.NO_MATCH
    if agent_confidence is not None and agent_confidence < settings.handoff_confidence_threshold:
        return HandoffTrigger.LOW_CONFIDENCE
    return None


async def create(
    session: AsyncSession,
    conversation: Conversation,
    *,
    issue_summary: str,
    trigger_reason: HandoffTrigger,
    contact_name: str | None = None,
    contact_phone: str | None = None,
) -> HandoffRequest:
    """Queue a handoff.

    Contact details stay optional: a citizen who does not want to give a number still gets
    queued, and the operator still sees the conversation context and the category of need
    (context.md §5).
    """
    handoff = HandoffRequest(
        conversation_id=conversation.id,
        category=conversation.category,
        contact_name=_clean(contact_name),
        contact_phone=_clean(contact_phone),
        issue_summary=issue_summary.strip(),
        trigger_reason=trigger_reason.value,
        status=HandoffStatus.NEW,
        language=conversation.language,
    )
    session.add(handoff)
    await session.flush()
    return handoff


async def get(session: AsyncSession, handoff_id: uuid.UUID) -> HandoffRequest:
    handoff = await session.get(HandoffRequest, handoff_id)
    if handoff is None:
        raise HandoffNotFound(str(handoff_id))
    return handoff


async def queue(
    session: AsyncSession,
    *,
    status: HandoffStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[HandoffRequest]:
    stmt = select(HandoffRequest).order_by(HandoffRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(HandoffRequest.status == status.value)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars())


async def update_status(
    session: AsyncSession,
    handoff: HandoffRequest,
    new_status: HandoffStatus,
    *,
    operator_notes: str | None = None,
) -> HandoffRequest:
    current = HandoffStatus(handoff.status)
    if new_status not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(current.value, new_status.value)
    handoff.status = new_status.value
    if operator_notes is not None:
        handoff.operator_notes = operator_notes
    handoff.updated_at = datetime.now(UTC)
    await session.flush()
    return handoff


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
