"""The routes the dashboard and the operator use: sessions, catalogue, queue, audit.

The operator-facing assertions are about context: a callback without the call behind it is
exactly the experience the handoff exists to avoid (FR-08), so the queue detail view is
tested for the conversation and its events, not just the queue row.
"""

from __future__ import annotations

import uuid

from tests.conftest import ADMIN, OPERATOR, VOICE, loan_record

# --------------------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------------------


async def test_a_call_is_created_ended_and_timed(client, published_loan) -> None:
    created = await client.post(
        "/v1/conversations",
        json={
            "channel": "phone",
            "language": "hi",
            "livekit_room": "room-1",
            "sip_call_id": "sip-1",
            "connected_at": "2026-03-01T09:00:00Z",
        },
        headers=VOICE,
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert created.json()["status"] == "active"
    assert created.json()["time_to_guidance_seconds"] is None

    await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": conversation_id, "query": "mudra loan"},
        headers=VOICE,
    )

    ended = await client.post(
        f"/v1/conversations/{conversation_id}/end", json={"status": "ended"}, headers=VOICE
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    # The clock started at the reported answer time, so TTG is a real measured duration.
    assert ended.json()["time_to_guidance_seconds"] > 0


async def test_a_call_cannot_be_ended_twice(client, conversation) -> None:
    first = await client.post(
        f"/v1/conversations/{conversation.id}/end", json={}, headers=VOICE
    )
    second = await client.post(
        f"/v1/conversations/{conversation.id}/end", json={}, headers=VOICE
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "conversation has already ended"


async def test_reading_an_unknown_call_is_a_404(client) -> None:
    response = await client.get(f"/v1/conversations/{uuid.uuid4()}", headers=OPERATOR)
    assert response.status_code == 404
    assert "no conversation" in response.json()["detail"]


async def test_the_worker_can_append_and_read_turn_events(client, conversation) -> None:
    for kind in ("turn.citizen", "turn.agent"):
        created = await client.post(
            f"/v1/conversations/{conversation.id}/events",
            json={"kind": kind, "payload": {"text": kind}},
            headers=VOICE,
        )
        assert created.status_code == 201

    listed = await client.get(
        f"/v1/conversations/{conversation.id}/events", headers=OPERATOR
    )
    assert [event["seq"] for event in listed.json()] == [1, 2]
    assert [event["kind"] for event in listed.json()] == ["turn.citizen", "turn.agent"]


async def test_events_cannot_be_appended_to_a_closed_call(client, conversation) -> None:
    await client.post(f"/v1/conversations/{conversation.id}/end", json={}, headers=VOICE)
    response = await client.post(
        f"/v1/conversations/{conversation.id}/events",
        json={"kind": "turn.agent"},
        headers=VOICE,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------------------


async def test_publishing_over_http_creates_a_second_version(client, published_loan) -> None:
    updated = loan_record()
    updated.benefit_summary.en = "Up to 20 lakh rupees of credit."

    response = await client.post(
        "/v1/services",
        json={"record": updated.model_dump(mode="json"), "review_notes": "rechecked"},
        headers=ADMIN,
    )
    assert response.status_code == 201
    assert response.json()["service_version"] == 2

    versions = await client.get("/v1/services/mudra-loan/versions", headers=ADMIN)
    assert [v["version"] for v in versions.json()] == [1, 2]
    assert versions.json()[1]["review_notes"] == "rechecked"


async def test_an_unverified_record_is_refused_over_http(client) -> None:
    record = loan_record().model_dump(mode="json")
    record["citation"]["verification_state"] = "pending_review"
    record["citation"]["verified_by"] = None

    response = await client.post("/v1/services", json={"record": record}, headers=ADMIN)
    assert response.status_code == 409
    assert "human-verified" in response.json()["detail"]


async def test_a_malformed_record_is_rejected_by_the_schema(client) -> None:
    record = loan_record().model_dump(mode="json")
    # A condition that tests a question the rule set never asks.
    record["rule_set"]["conditions"][0]["test"]["var"] = "shoe-size"

    response = await client.post("/v1/services", json={"record": record}, headers=ADMIN)
    assert response.status_code == 422


async def test_the_reviewer_can_diff_two_versions(client, published_loan) -> None:
    updated = loan_record()
    updated.rule_set.conditions[0].test.value = 21
    await client.post(
        "/v1/services", json={"record": updated.model_dump(mode="json")}, headers=ADMIN
    )

    response = await client.get("/v1/services/mudra-loan/diff/1/2", headers=ADMIN)
    assert response.status_code == 200
    assert response.json()["changes"] == {
        "rule_set.conditions.0.test.value": {"before": 18, "after": 21}
    }


async def test_diffing_a_version_that_does_not_exist_is_a_404(client, published_loan) -> None:
    response = await client.get("/v1/services/mudra-loan/diff/1/7", headers=ADMIN)
    assert response.status_code == 404
    assert "[7]" in response.json()["detail"]


async def test_reading_an_unpublished_slug_is_a_404(client) -> None:
    response = await client.get("/v1/services/no-such-scheme", headers=OPERATOR)
    assert response.status_code == 404


# --------------------------------------------------------------------------------------
# Operator queue
# --------------------------------------------------------------------------------------


async def _queued_handoff(client) -> dict:
    created = await client.post(
        "/v1/conversations", json={"channel": "harness", "language": "en"}, headers=VOICE
    )
    conversation_id = created.json()["id"]
    await client.post(
        f"/v1/conversations/{conversation_id}/events",
        json={"kind": "turn.citizen", "payload": {"text": "my pension stopped"}},
        headers=VOICE,
    )
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": conversation_id,
            "issue_summary": "Pension has not arrived for three months.",
            "contact_name": "Asha",
            "citizen_asked_for_person": True,
        },
        headers=VOICE,
    )
    return response.json()["handoff"]


async def test_the_operator_sees_the_call_behind_the_queue_entry(client) -> None:
    handoff = await _queued_handoff(client)

    response = await client.get(f"/v1/handoffs/{handoff['id']}", headers=OPERATOR)
    assert response.status_code == 200
    body = response.json()
    assert body["handoff"]["issue_summary"] == "Pension has not arrived for three months."
    assert body["conversation"]["status"] == "handed_off"
    kinds = [event["kind"] for event in body["events"]]
    assert "turn.citizen" in kinds
    assert "tool.request_handoff" in kinds


async def test_the_queue_can_be_filtered_by_status(client) -> None:
    handoff = await _queued_handoff(client)
    await _queued_handoff(client)

    await client.patch(
        f"/v1/handoffs/{handoff['id']}",
        json={"status": "contacted", "operator_notes": "called back"},
        headers=OPERATOR,
    )

    new_only = await client.get("/v1/handoffs", params={"status_filter": "new"}, headers=OPERATOR)
    contacted = await client.get(
        "/v1/handoffs", params={"status_filter": "contacted"}, headers=OPERATOR
    )
    assert len(new_only.json()) == 1
    assert [h["id"] for h in contacted.json()] == [handoff["id"]]
    assert contacted.json()[0]["operator_notes"] == "called back"


async def test_an_illegal_status_move_is_refused(client) -> None:
    handoff = await _queued_handoff(client)
    await client.patch(
        f"/v1/handoffs/{handoff['id']}", json={"status": "resolved"}, headers=OPERATOR
    )
    response = await client.patch(
        f"/v1/handoffs/{handoff['id']}", json={"status": "contacted"}, headers=OPERATOR
    )
    assert response.status_code == 409
    assert "cannot move a handoff from 'resolved' to 'contacted'" in response.json()["detail"]


async def test_updating_an_unknown_handoff_is_a_404(client) -> None:
    response = await client.patch(
        f"/v1/handoffs/{uuid.uuid4()}", json={"status": "contacted"}, headers=OPERATOR
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------------------


async def test_the_audit_trail_records_who_did_what(client) -> None:
    handoff = await _queued_handoff(client)
    await client.patch(
        f"/v1/handoffs/{handoff['id']}", json={"status": "contacted"}, headers=OPERATOR
    )

    response = await client.get(
        "/v1/audit-events", params={"conversation_id": handoff["conversation_id"]}, headers=ADMIN
    )
    rows = {row["action"]: row for row in response.json()}
    assert rows["handoff.created"]["actor"] == "voice"
    assert rows["handoff.status_changed"]["actor"] == "operator"
    assert rows["handoff.status_changed"]["payload"] == {"from": "new", "to": "contacted"}


async def test_the_audit_trail_can_be_filtered_by_action(client, published_loan) -> None:
    await _queued_handoff(client)
    response = await client.get(
        "/v1/audit-events", params={"action": "handoff.created"}, headers=ADMIN
    )
    assert [row["action"] for row in response.json()] == ["handoff.created"]


async def test_a_published_version_is_traceable_from_its_audit_row(client) -> None:
    published = await client.post(
        "/v1/services", json={"record": loan_record().model_dump(mode="json")}, headers=ADMIN
    )
    assert published.status_code == 201

    response = await client.get(
        "/v1/audit-events", params={"action": "service.published"}, headers=ADMIN
    )
    row = response.json()[0]
    assert row["actor"] == "admin"
    assert row["entity_type"] == "service_version"
    assert row["payload"] == {"slug": "mudra-loan", "version": 1}
