"""Conversation state, the TTG clock and the event log.

Time-to-Guidance is the primary evaluation metric (proposal §6.1), so the tests are about
the two timestamps that define it: they are written by the system that owns them, written
once, and never back-filled.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.context import set_request_id
from app.models import ConversationStatus
from app.modules.conversation import service as conversations
from app.modules.conversation.service import ConversationClosed, ConversationNotFound


async def test_a_new_conversation_is_active_with_the_clock_started(session) -> None:
    conversation = await conversations.create(session, channel="phone", language="hi")
    assert conversation.status == ConversationStatus.ACTIVE
    assert conversation.connected_at is not None
    assert conversation.first_guidance_at is None
    assert conversation.tool_failure_streak == 0


async def test_connected_at_is_the_answer_time_the_worker_reports(session) -> None:
    answered = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    conversation = await conversations.create(
        session, channel="phone", connected_at=answered
    )
    assert conversation.connected_at == answered


async def test_time_to_guidance_is_null_until_guidance_lands(session, conversation) -> None:
    assert conversations.time_to_guidance(conversation).seconds is None

    await conversations.mark_guidance_delivered(
        session, conversation, at=conversation.connected_at + timedelta(seconds=42)
    )
    assert conversations.time_to_guidance(conversation).seconds == 42.0


async def test_the_guidance_clock_is_written_once(session, conversation) -> None:
    first = conversation.connected_at + timedelta(seconds=10)
    await conversations.mark_guidance_delivered(session, conversation, at=first)
    await conversations.mark_guidance_delivered(
        session, conversation, at=conversation.connected_at + timedelta(seconds=99)
    )
    assert conversation.first_guidance_at == first


async def test_a_missing_conversation_raises(session) -> None:
    with pytest.raises(ConversationNotFound):
        await conversations.get(session, uuid.uuid4())


async def test_an_ended_conversation_is_not_active(session, conversation) -> None:
    await conversations.end(session, conversation)
    assert conversation.status == ConversationStatus.ENDED
    assert conversation.ended_at is not None
    with pytest.raises(ConversationClosed):
        await conversations.get_active(session, conversation.id)


async def test_events_are_numbered_in_order_and_carry_the_request_id(
    session, conversation
) -> None:
    set_request_id("req-abc")
    for kind in ("turn.citizen", "tool.find_service", "turn.agent"):
        await conversations.append_event(session, conversation, kind=kind, payload={"k": kind})

    events = await conversations.events(session, conversation.id)
    assert [event.seq for event in events] == [1, 2, 3]
    assert [event.kind for event in events] == [
        "turn.citizen",
        "tool.find_service",
        "turn.agent",
    ]
    assert {event.request_id for event in events} == {"req-abc"}


async def test_events_of_one_call_are_not_visible_on_another(session, conversation) -> None:
    other = await conversations.create(session, channel="harness")
    await conversations.append_event(session, conversation, kind="turn.citizen")
    await conversations.append_event(session, other, kind="turn.citizen")

    assert len(await conversations.events(session, conversation.id)) == 1
    # Numbering restarts per call rather than being global.
    assert (await conversations.events(session, other.id))[0].seq == 1


async def test_the_failure_streak_counts_up_and_is_cleared_by_a_success(
    session, conversation
) -> None:
    assert await conversations.note_tool_failure(session, conversation) == 1
    assert await conversations.note_tool_failure(session, conversation) == 2
    await conversations.clear_tool_failures(session, conversation)
    assert conversation.tool_failure_streak == 0


async def test_set_category_only_writes_a_real_change(session, conversation) -> None:
    await conversations.set_category(session, conversation, "loan")
    assert conversation.category == "loan"
    # A null from a category-less query must not wipe what the citizen already told us.
    await conversations.set_category(session, conversation, None)
    assert conversation.category == "loan"
