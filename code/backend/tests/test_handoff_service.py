"""Deterministic handoff triggers and the operator queue lifecycle.

The trigger table is asserted directly because context.md §14 measures handoff precision and
recall against it: if the ordering changes, the measurement is no longer comparable.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import Settings
from app.models import HandoffStatus, HandoffTrigger
from app.modules.handoff import service as handoffs
from app.modules.handoff.service import HandoffNotFound, InvalidTransition


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None, handoff_confidence_threshold=0.55, handoff_tool_failure_streak=2
    )


# --------------------------------------------------------------------------------------
# decide_trigger
# --------------------------------------------------------------------------------------


def test_no_signal_means_no_handoff(settings) -> None:
    assert handoffs.decide_trigger(settings, match_count=3, agent_confidence=0.9) is None


def test_no_reported_signals_at_all_means_no_handoff(settings) -> None:
    assert handoffs.decide_trigger(settings) is None


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        ({"citizen_asked_for_person": True}, HandoffTrigger.CITIZEN_REQUEST),
        ({"tool_failure_streak": 2}, HandoffTrigger.TOOL_FAILURE),
        ({"out_of_scope": True}, HandoffTrigger.OUT_OF_SCOPE),
        ({"match_count": 0}, HandoffTrigger.NO_MATCH),
        ({"match_count": 2, "agent_confidence": 0.54}, HandoffTrigger.LOW_CONFIDENCE),
    ],
)
def test_each_signal_fires_its_own_trigger(settings, signals, expected) -> None:
    assert handoffs.decide_trigger(settings, **signals) is expected


def test_the_citizens_own_request_outranks_every_inference(settings) -> None:
    trigger = handoffs.decide_trigger(
        settings,
        citizen_asked_for_person=True,
        match_count=0,
        agent_confidence=0.0,
        tool_failure_streak=9,
        out_of_scope=True,
    )
    assert trigger is HandoffTrigger.CITIZEN_REQUEST


def test_repeated_tool_failure_outranks_a_missing_match(settings) -> None:
    trigger = handoffs.decide_trigger(
        settings, match_count=0, tool_failure_streak=2, out_of_scope=True
    )
    assert trigger is HandoffTrigger.TOOL_FAILURE


def test_the_failure_streak_threshold_is_inclusive(settings) -> None:
    assert handoffs.decide_trigger(settings, tool_failure_streak=1) is None
    assert handoffs.decide_trigger(settings, tool_failure_streak=2) is HandoffTrigger.TOOL_FAILURE


def test_confidence_exactly_at_the_threshold_does_not_trigger(settings) -> None:
    assert handoffs.decide_trigger(settings, match_count=1, agent_confidence=0.55) is None
    assert (
        handoffs.decide_trigger(settings, match_count=1, agent_confidence=0.549)
        is HandoffTrigger.LOW_CONFIDENCE
    )


def test_the_threshold_comes_from_configuration_not_a_constant() -> None:
    strict = Settings(_env_file=None, handoff_confidence_threshold=0.9)
    assert (
        handoffs.decide_trigger(strict, match_count=1, agent_confidence=0.8)
        is HandoffTrigger.LOW_CONFIDENCE
    )


def test_an_unreported_match_count_is_not_a_no_match(settings) -> None:
    """`None` means the agent never searched; only a real zero is evidence of a miss."""
    assert handoffs.decide_trigger(settings, match_count=None, agent_confidence=0.9) is None


# --------------------------------------------------------------------------------------
# Queue lifecycle
# --------------------------------------------------------------------------------------


async def test_a_handoff_inherits_the_calls_category_and_language(session, conversation) -> None:
    from app.modules.conversation import service as conversations

    await conversations.set_category(session, conversation, "loan")
    handoff = await handoffs.create(
        session,
        conversation,
        issue_summary="  needs help applying  ",
        trigger_reason=HandoffTrigger.CITIZEN_REQUEST,
    )
    assert handoff.category == "loan"
    assert handoff.language == "en"
    assert handoff.issue_summary == "needs help applying"
    assert handoff.status == HandoffStatus.NEW


async def test_contact_details_stay_optional(session, conversation) -> None:
    handoff = await handoffs.create(
        session,
        conversation,
        issue_summary="declined to give a number",
        trigger_reason=HandoffTrigger.NO_MATCH,
        contact_name="   ",
        contact_phone=None,
    )
    assert handoff.contact_name is None
    assert handoff.contact_phone is None


async def test_a_missing_handoff_raises(session) -> None:
    with pytest.raises(HandoffNotFound):
        await handoffs.get(session, uuid.uuid4())


async def test_the_queue_is_newest_first_and_filterable(session, conversation) -> None:
    first = await handoffs.create(
        session, conversation, issue_summary="one", trigger_reason=HandoffTrigger.NO_MATCH
    )
    second = await handoffs.create(
        session, conversation, issue_summary="two", trigger_reason=HandoffTrigger.NO_MATCH
    )
    await handoffs.update_status(session, second, HandoffStatus.CONTACTED)
    await session.commit()

    new_only = await handoffs.queue(session, status=HandoffStatus.NEW)
    assert [h.id for h in new_only] == [first.id]
    assert len(await handoffs.queue(session)) == 2
    assert len(await handoffs.queue(session, limit=1)) == 1


async def test_the_status_walk_is_new_to_contacted_to_resolved(session, conversation) -> None:
    handoff = await handoffs.create(
        session, conversation, issue_summary="one", trigger_reason=HandoffTrigger.NO_MATCH
    )
    await handoffs.update_status(
        session, handoff, HandoffStatus.CONTACTED, operator_notes="called back"
    )
    assert handoff.status == HandoffStatus.CONTACTED
    assert handoff.operator_notes == "called back"

    await handoffs.update_status(session, handoff, HandoffStatus.RESOLVED)
    assert handoff.status == HandoffStatus.RESOLVED


async def test_a_resolved_handoff_cannot_be_reopened(session, conversation) -> None:
    handoff = await handoffs.create(
        session, conversation, issue_summary="one", trigger_reason=HandoffTrigger.NO_MATCH
    )
    await handoffs.update_status(session, handoff, HandoffStatus.RESOLVED)
    with pytest.raises(InvalidTransition) as raised:
        await handoffs.update_status(session, handoff, HandoffStatus.CONTACTED)
    assert raised.value.current == "resolved"
    assert raised.value.requested == "contacted"


async def test_a_contacted_handoff_cannot_go_back_to_new(session, conversation) -> None:
    handoff = await handoffs.create(
        session, conversation, issue_summary="one", trigger_reason=HandoffTrigger.NO_MATCH
    )
    await handoffs.update_status(session, handoff, HandoffStatus.CONTACTED)
    with pytest.raises(InvalidTransition):
        await handoffs.update_status(session, handoff, HandoffStatus.NEW)


async def test_a_handoff_may_be_resolved_without_a_callback(session, conversation) -> None:
    handoff = await handoffs.create(
        session, conversation, issue_summary="one", trigger_reason=HandoffTrigger.NO_MATCH
    )
    await handoffs.update_status(session, handoff, HandoffStatus.RESOLVED)
    assert handoff.status == HandoffStatus.RESOLVED
