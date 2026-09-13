"""Degrade, never corrupt (context.md §13).

A failed model call must return a recoverable message and must leave no half-written handoff
or service record behind. The failure adapter is wired in through the same dependency the
real one uses, so these tests exercise the production code path rather than a stub of it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.adapters.model.base import ModelUnavailable
from app.adapters.model.factory import get_model_adapter
from app.adapters.model.failure import FailureModelAdapter
from app.models import Conversation, HandoffRequest
from tests.conftest import ADMIN, VOICE


async def _conversation_id(client) -> str:
    response = await client.post(
        "/v1/conversations", json={"channel": "harness", "language": "en"}, headers=VOICE
    )
    return response.json()["id"]


async def test_an_unavailable_model_still_queues_the_handoff(client, app, session) -> None:
    app.dependency_overrides[get_model_adapter] = FailureModelAdapter
    conversation_id = await _conversation_id(client)

    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "transcript": "  My   pension has not arrived for three months.  ",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )

    assert response.status_code == 201
    # Worse prose than a drafted summary, but it is still the context the operator needs.
    assert (
        response.json()["handoff"]["issue_summary"]
        == "My pension has not arrived for three months."
    )
    queued = (await session.execute(select(HandoffRequest))).scalars().all()
    assert len(queued) == 1


async def test_a_model_failure_never_leaves_a_half_written_call(client, app, session) -> None:
    app.dependency_overrides[get_model_adapter] = FailureModelAdapter
    conversation_id = await _conversation_id(client)

    # No trigger fires, so the tool refuses before the model is ever consulted.
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "transcript": "just browsing",
            "match_count": 3,
            "agent_confidence": 0.95,
        },
        headers=VOICE,
    )
    assert response.status_code == 409

    conversation = await session.get(Conversation, uuid.UUID(conversation_id))
    await session.refresh(conversation)
    assert conversation.status == "active"
    assert conversation.ended_at is None
    assert (await session.execute(select(HandoffRequest))).scalars().all() == []


async def test_a_model_error_from_a_dependency_maps_to_503_not_500(client, app) -> None:
    """`ModelUnavailable` is recoverable by contract, so it must never surface as a 500."""

    def _explode() -> None:
        raise ModelUnavailable("provider is down")

    app.dependency_overrides[get_model_adapter] = _explode
    conversation_id = await _conversation_id(client)

    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "needs a person",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "the language model is unavailable; the request was not applied"
    )
    assert response.json()["request_id"]


async def test_every_error_body_carries_the_request_id_that_produced_it(client) -> None:
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": "00000000-0000-0000-0000-000000000000", "query": "loan"},
        headers={**VOICE, "X-Request-ID": "trace-404"},
    )
    assert response.status_code == 404
    assert response.json()["request_id"] == "trace-404"
    assert response.headers["X-Request-ID"] == "trace-404"


async def test_a_generated_request_id_is_returned_when_the_caller_sends_none(client) -> None:
    response = await client.get("/healthz", headers=ADMIN)
    assert response.headers["X-Request-ID"]


async def test_liveness_touches_no_dependency(client) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["env"] == "test"


async def test_readiness_reports_the_database(client) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
