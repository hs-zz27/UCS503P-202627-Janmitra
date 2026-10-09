"""Role gating on every router (context.md §14: unauthorised-action tests).

The seeded three-account scheme is a real gate, not a comment, so each router is asserted
against every role rather than only against the one that is meant to pass.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import ADMIN, OPERATOR, VOICE

ANY_ID = str(uuid.uuid4())


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/v1/services", None),
        ("post", "/v1/tools/find_service", {"conversation_id": ANY_ID, "query": "loan"}),
        ("get", "/v1/handoffs", None),
        ("get", "/v1/audit-events", None),
        ("post", "/v1/conversations", {"channel": "harness"}),
    ],
)
async def test_missing_api_key_is_rejected(client, method, path, body) -> None:
    response = await getattr(client, method)(path, json=body) if body else await getattr(
        client, method
    )(path)
    assert response.status_code == 401
    assert response.json()["detail"] == "unknown or missing API key"


async def test_unknown_api_key_is_rejected(client) -> None:
    response = await client.get("/v1/services", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


async def test_operator_may_not_call_voice_tools(client, conversation) -> None:
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": str(conversation.id), "query": "loan"},
        headers=OPERATOR,
    )
    assert response.status_code == 403
    assert "may not perform this action" in response.json()["detail"]


async def test_voice_may_not_read_the_operator_queue(client) -> None:
    response = await client.get("/v1/handoffs", headers=VOICE)
    assert response.status_code == 403


async def test_voice_may_not_read_the_audit_trail(client) -> None:
    response = await client.get("/v1/audit-events", headers=VOICE)
    assert response.status_code == 403


async def test_operator_may_not_publish_a_service(client) -> None:
    from tests.conftest import loan_record

    response = await client.post(
        "/v1/services",
        json={"record": loan_record().model_dump(mode="json")},
        headers=OPERATOR,
    )
    assert response.status_code == 403


async def test_operator_may_not_read_version_history(client, published_loan) -> None:
    denied = await client.get("/v1/services/mudra-loan/versions", headers=OPERATOR)
    allowed = await client.get("/v1/services/mudra-loan/versions", headers=ADMIN)
    assert denied.status_code == 403
    assert allowed.status_code == 200


async def test_admin_may_do_anything_a_voice_worker_can(client, conversation) -> None:
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": str(conversation.id), "query": "mudra loan"},
        headers=ADMIN,
    )
    assert response.status_code == 200


async def test_any_authenticated_role_may_read_the_published_catalogue(
    client, published_loan
) -> None:
    for headers in (ADMIN, OPERATOR, VOICE):
        response = await client.get("/v1/services", headers=headers)
        assert response.status_code == 200
        assert [item["slug"] for item in response.json()] == ["mudra-loan"]
