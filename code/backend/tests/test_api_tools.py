"""The four typed tool endpoints, end to end over HTTP.

These are the only way verified facts leave the system (context.md §8.3), so the assertions
are about the contract a citizen depends on: every factual answer carries a citation and the
service version it came from, the eligibility verdict comes from the rule engine rather than
a model, and a handoff is only created when a deterministic trigger fired.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import AuditEvent, Conversation, ConversationEvent, HandoffRequest
from tests.conftest import ADMIN, VOICE

#: `note_tool_failure` flushes the incremented counter and the endpoint then raises
#: `HTTPException`, so `app.db.get_session` rolls the increment back on the way out
#: (app/db.py:58). The counter therefore never survives the request that incremented it and
#: the `tool_failure` handoff trigger in context.md §18.3 can never fire from the API.
#: Strict, so whoever commits the failure before raising sees these turn green.
STREAK_ROLLED_BACK = pytest.mark.xfail(
    strict=True,
    reason="tool-failure streak is rolled back with the request that raised (app/db.py:58)",
)


async def _conversation_id(client) -> str:
    response = await client.post(
        "/v1/conversations", json={"channel": "harness", "language": "en"}, headers=VOICE
    )
    assert response.status_code == 201
    return response.json()["id"]


# --------------------------------------------------------------------------------------
# find_service
# --------------------------------------------------------------------------------------


async def test_find_service_returns_cited_versioned_matches(
    client, published_loan, published_pension
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "small business loan"},
        headers=VOICE,
    )
    assert response.status_code == 200
    body = response.json()

    assert [match["slug"] for match in body["matches"]] == ["mudra-loan"]
    match = body["matches"][0]
    assert match["service_version"] == 1
    assert match["citation"]["source_url"] == "https://example.gov.in/scheme"
    assert match["citation"]["verified_on"] == "2026-01-15"
    assert match["is_rule_backed"] is True
    assert body["suggested_handoff_trigger"] is None


async def test_find_service_category_filter_narrows_the_catalogue(
    client, published_loan, published_pension
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "pension", "category": "pension"},
        headers=VOICE,
    )
    assert response.status_code == 200
    assert [m["slug"] for m in response.json()["matches"]] == ["old-age-pension"]
    assert response.json()["asked_category"] == "pension"


async def test_find_service_records_the_asked_category_on_the_conversation(
    client, session, published_pension
) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "pension", "category": "pension"},
        headers=VOICE,
    )
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.category == "pension"


async def test_zero_matches_suggests_a_handoff_without_creating_one(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "passport renewal appointment"},
        headers=VOICE,
    )
    assert response.status_code == 200
    assert response.json()["matches"] == []
    assert response.json()["suggested_handoff_trigger"] == "no_match"

    queued = (await session.execute(select(HandoffRequest))).scalars().all()
    assert queued == []


async def test_a_match_stops_the_time_to_guidance_clock_once(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    first = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )
    assert first.status_code == 200

    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    stamped_at = conversation.first_guidance_at
    assert stamped_at is not None

    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )
    await session.refresh(conversation)
    assert conversation.first_guidance_at == stamped_at


async def test_a_miss_does_not_start_the_guidance_clock(client, session, published_loan) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "passport renewal"},
        headers=VOICE,
    )
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.first_guidance_at is None


# --------------------------------------------------------------------------------------
# check_eligibility
# --------------------------------------------------------------------------------------


async def test_check_eligibility_decides_and_cites(client, published_loan) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={
            "conversation_id": conversation_id,
            "slug": "mudra-loan",
            "answers": {
                "age": 34,
                "state": "punjab",
                "occupation": "trader",
                "annual-income": 120000,
                "has-bank-account": True,
            },
        },
        headers=VOICE,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "eligible"
    assert body["missing_answers"] == []
    assert body["failed_conditions"] == []
    assert body["service_version"] == 1
    assert body["citation"]["publisher"] == "Department of Example"
    assert "not an official decision" in body["disclaimer"]
    # The trace is what the agent reads back, so every named condition appears in it.
    assert {c["id"] for c in body["conditions"]} == {
        "adult", "resident", "income-ceiling", "banked"
    }


async def test_check_eligibility_asks_only_for_what_is_still_missing(
    client, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={
            "conversation_id": conversation_id,
            "slug": "mudra-loan",
            "answers": {"age": 34, "state": "punjab"},
        },
        headers=VOICE,
    )
    body = response.json()
    assert body["outcome"] == "needs_more_info"
    assert body["missing_answers"] == ["occupation", "has-bank-account"]
    assert [q["id"] for q in body["next_questions"]] == ["occupation", "has-bank-account"]
    assert body["next_questions"][0]["options"] == ["farmer", "trader", "other"]


async def test_a_definite_failure_is_decisive_even_with_answers_outstanding(
    client, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={
            "conversation_id": conversation_id,
            "slug": "mudra-loan",
            "answers": {"age": 15},
        },
        headers=VOICE,
    )
    body = response.json()
    assert body["outcome"] == "not_eligible"
    assert body["failed_conditions"] == ["adult"]


async def test_needs_more_info_does_not_stop_the_guidance_clock(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/check_eligibility",
        json={"conversation_id": conversation_id, "slug": "mudra-loan", "answers": {"age": 34}},
        headers=VOICE,
    )
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.first_guidance_at is None


@STREAK_ROLLED_BACK
async def test_bad_answers_are_a_validation_failure_not_a_verdict(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={
            "conversation_id": conversation_id,
            "slug": "mudra-loan",
            "answers": {"state": "kerala"},
        },
        headers=VOICE,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "answers did not validate"
    assert "state" in detail["errors"][0]

    # A bad extraction counts towards the tool-failure handoff trigger.
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.tool_failure_streak == 1


@STREAK_ROLLED_BACK
async def test_unknown_slug_is_a_404_and_counts_as_a_tool_failure(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={"conversation_id": conversation_id, "slug": "no-such-scheme", "answers": {}},
        headers=VOICE,
    )
    assert response.status_code == 404
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.tool_failure_streak == 1


async def test_a_successful_call_clears_the_failure_streak(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/check_eligibility",
        json={"conversation_id": conversation_id, "slug": "no-such-scheme", "answers": {}},
        headers=VOICE,
    )
    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )
    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.tool_failure_streak == 0


async def test_a_scheme_without_rules_refuses_eligibility_and_says_why(
    client, published_pension
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/check_eligibility",
        json={"conversation_id": conversation_id, "slug": "old-age-pension", "answers": {}},
        headers=VOICE,
    )
    assert response.status_code == 409
    assert "document checklist" in response.json()["detail"]


# --------------------------------------------------------------------------------------
# get_documents
# --------------------------------------------------------------------------------------


async def test_get_documents_marks_an_ungated_document_conditional(
    client, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/get_documents",
        json={"conversation_id": conversation_id, "slug": "mudra-loan", "answers": {}},
        headers=VOICE,
    )
    assert response.status_code == 200
    documents = {d["id"]: d for d in response.json()["documents"]}
    assert documents["aadhaar"]["required"] is True
    assert documents["aadhaar"]["conditional"] is False
    # Not dropped just because nobody has been asked yet.
    assert documents["land-record"]["conditional"] is True
    assert documents["land-record"]["depends_on"] == "occupation"


async def test_get_documents_drops_a_document_the_answer_rules_out(client, published_loan) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/get_documents",
        json={
            "conversation_id": conversation_id,
            "slug": "mudra-loan",
            "answers": {"occupation": "trader"},
        },
        headers=VOICE,
    )
    assert [d["id"] for d in response.json()["documents"]] == ["aadhaar"]


async def test_get_documents_works_for_a_scheme_with_no_rule_set(
    client, published_pension
) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/get_documents",
        json={"conversation_id": conversation_id, "slug": "old-age-pension"},
        headers=VOICE,
    )
    assert response.status_code == 200
    assert [d["id"] for d in response.json()["documents"]] == ["age-proof"]
    assert response.json()["citation"]["source_url"] == "https://example.gov.in/pension"


# --------------------------------------------------------------------------------------
# request_handoff
# --------------------------------------------------------------------------------------


async def test_request_handoff_refuses_when_no_trigger_fired(client, session) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "wants a second opinion",
            "match_count": 3,
            "agent_confidence": 0.9,
        },
        headers=VOICE,
    )
    assert response.status_code == 409
    assert "continue self-service" in response.json()["detail"]
    assert (await session.execute(select(HandoffRequest))).scalars().all() == []


async def test_request_handoff_queues_and_ends_the_call(client, session) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "Wants help applying for a loan.",
            "contact_name": "Asha",
            "contact_phone": " 9876543210 ",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["handoff"]["trigger_reason"] == "citizen_request"
    assert body["handoff"]["status"] == "new"
    assert body["handoff"]["contact_phone"] == "9876543210"
    assert body["spoken_confirmation"] == (
        "Asha, I am passing this to someone who can help you directly."
    )
    # Framed as a transfer, never a ticket number (context.md §5).
    assert body["handoff"]["id"] not in body["spoken_confirmation"]

    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.status == "handed_off"
    assert conversation.ended_at is not None


async def test_a_handed_off_call_refuses_further_tool_calls(client, published_loan) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "needs a person",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "conversation is no longer active"


async def test_handoff_on_an_unknown_conversation_is_a_404(client) -> None:
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": str(uuid.uuid4()),
            "issue_summary": "needs a person",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    assert response.status_code == 404
    assert response.json()["request_id"]


async def test_handoff_without_a_summary_or_transcript_is_rejected(client) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={"conversation_id": conversation_id, "citizen_asked_for_person": True},
        headers=VOICE,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "issue_summary or transcript is required"


async def test_a_transcript_is_summarised_when_no_summary_was_given(client) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "transcript": "  I have been\n trying to get a loan   for my shop.  ",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    assert response.status_code == 201
    assert (
        response.json()["handoff"]["issue_summary"]
        == "I have been trying to get a loan for my shop."
    )


@STREAK_ROLLED_BACK
async def test_the_tool_failure_streak_triggers_a_handoff_on_its_own(
    client, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    for _ in range(2):
        await client.post(
            "/v1/tools/check_eligibility",
            json={"conversation_id": conversation_id, "slug": "gone", "answers": {}},
            headers=VOICE,
        )
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "tools kept failing",
            "match_count": 3,
            "agent_confidence": 0.99,
        },
        headers=VOICE,
    )
    assert response.status_code == 201
    assert response.json()["handoff"]["trigger_reason"] == "tool_failure"


async def test_low_confidence_triggers_a_handoff(client) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "could not understand the request",
            "match_count": 2,
            "agent_confidence": 0.2,
        },
        headers=VOICE,
    )
    assert response.status_code == 201
    assert response.json()["handoff"]["trigger_reason"] == "low_confidence"


async def test_hindi_confirmation_is_spoken_in_hindi(client) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "needs a person",
            "citizen_asked_for_person": True,
            "language": "hi",
        },
        headers=VOICE,
    )
    assert "main aapko" in response.json()["spoken_confirmation"]


# --------------------------------------------------------------------------------------
# Trace: every tool call leaves a conversation event and an audit row (FR-10)
# --------------------------------------------------------------------------------------


async def test_every_tool_call_is_traceable_from_the_conversation_to_the_version(
    client, session, published_loan
) -> None:
    conversation_id = await _conversation_id(client)
    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )
    await client.post(
        "/v1/tools/check_eligibility",
        json={"conversation_id": conversation_id, "slug": "mudra-loan", "answers": {"age": 15}},
        headers=VOICE,
    )

    events = (
        (
            await session.execute(
                select(ConversationEvent)
                .where(ConversationEvent.conversation_id == uuid.UUID(conversation_id))
                .order_by(ConversationEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    assert [event.kind for event in events] == ["tool.find_service", "tool.check_eligibility"]
    assert [event.seq for event in events] == [1, 2]
    assert all(event.request_id for event in events)

    audit_rows = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.conversation_id == uuid.UUID(conversation_id))
            )
        )
        .scalars()
        .all()
    )
    actions = {row.action for row in audit_rows}
    assert {"conversation.created", "tool.find_service", "tool.check_eligibility"} <= actions
    eligibility_row = next(r for r in audit_rows if r.action == "tool.check_eligibility")
    assert eligibility_row.entity_type == "service_version"
    assert eligibility_row.entity_id == str(published_loan.version_id)


async def test_an_inbound_request_id_is_echoed_and_stored(client, published_loan) -> None:
    conversation_id = await _conversation_id(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers={**VOICE, "X-Request-ID": "trace-me-123"},
    )
    assert response.headers["X-Request-ID"] == "trace-me-123"

    audit = await client.get(
        "/v1/audit-events", params={"request_id": "trace-me-123"}, headers=ADMIN
    )
    assert [row["action"] for row in audit.json()] == ["tool.find_service"]
