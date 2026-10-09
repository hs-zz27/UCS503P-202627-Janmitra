from pathlib import Path

import pytest

from app.adapters.model.base import IssueSummary, ModelOutputInvalid, ModelUnavailable
from app.adapters.model.factory import get_model_adapter
from app.seed.services import load_records, prepare_records


def reviewed_record(slug="apy"):
    record = next(r for r in load_records(Path(__file__).parents[1] / "data") if r.slug == slug)
    return prepare_records([record], actor="Test Reviewer", confirm_reviewed=True)[0]


async def create_call(client):
    response = await client.post("/v1/conversations", json={"channel": "harness"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def publish(client, slug="apy"):
    response = await client.post(
        "/v1/services",
        headers={"X-API-Key": "test-admin"},
        json={"record": reviewed_record(slug).model_dump(mode="json")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_failures_persist_and_trigger_handoff(api):
    client, _, _ = api
    cid = await create_call(client)
    for tool in ("check_eligibility", "get_documents"):
        result = await client.post(
            f"/v1/tools/{tool}", json={"conversation_id": cid, "slug": "missing-service"}
        )
        assert result.status_code == 404
    call = (await client.get(f"/v1/conversations/{cid}")).json()
    assert call["tool_failure_streak"] == 2
    response = await client.post(
        "/v1/tools/request_handoff",
        json={"conversation_id": cid, "issue_summary": "Could not retrieve service"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["handoff"]["trigger_reason"] == "tool_failure"
    assert (await client.get(f"/v1/conversations/{cid}")).json()["status"] == "handed_off"


@pytest.mark.parametrize("tool", ["check_eligibility", "get_documents"])
async def test_validation_failure_and_successful_reset(api, tool):
    client, _, _ = api
    await publish(client)
    cid = await create_call(client)
    response = await client.post(
        f"/v1/tools/{tool}",
        json={
            "conversation_id": cid,
            "slug": "apy",
            "answers": {"age": 40.9},
        },
    )
    assert response.status_code == 422
    assert (await client.get(f"/v1/conversations/{cid}")).json()["tool_failure_streak"] == 1
    response = await client.post(
        "/v1/tools/get_documents",
        json={
            "conversation_id": cid,
            "slug": "apy",
            "answers": {"age": 40},
        },
    )
    assert response.status_code == 200
    assert (await client.get(f"/v1/conversations/{cid}")).json()["tool_failure_streak"] == 0


async def test_terminal_status_and_closed_tools(api):
    client, _, _ = api
    cid = await create_call(client)
    for invalid_status in ("active", "handed_off"):
        response = await client.post(
            f"/v1/conversations/{cid}/end", json={"status": invalid_status}
        )
        assert response.status_code == 422
    assert (await client.post(f"/v1/conversations/{cid}/end", json={})).status_code == 200
    assert (await client.post(f"/v1/conversations/{cid}/end", json={})).status_code == 409
    assert (
        await client.post(f"/v1/conversations/{cid}/events", json={"kind": "test"})
    ).status_code == 409
    response = await client.post(
        "/v1/tools/find_service", json={"conversation_id": cid, "query": "loan"}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "failure", [ModelUnavailable("offline"), ModelOutputInvalid("bad JSON"), None]
)
async def test_handoff_degrades_from_invalid_summary(api, failure):
    client, app, _ = api

    class SummaryModel:
        async def summarize_issue(self, *args, **kwargs):
            if failure:
                raise failure
            return IssueSummary(summary="   ")

    app.dependency_overrides[get_model_adapter] = SummaryModel
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": cid,
            "citizen_asked_for_person": True,
            "transcript": "Please help with my pension",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["handoff"]["issue_summary"] == "Please help with my pension"


@pytest.mark.parametrize("query", ["crop insurance", "फसल बीमा", "ਫਸਲ ਬੀਮਾ", "fasal bima"])
async def test_published_search_is_multilingual(api, query):
    client, _, _ = api
    await publish(client, "pmfby")
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service", json={"conversation_id": cid, "query": query}
    )
    assert response.status_code == 200, response.text
    assert response.json()["matches"][0]["slug"] == "pmfby"
    assert response.json()["knowledge_fallback_allowed"] is False


async def test_auth_roles_publication_history_and_handoff_transitions(api):
    client, _, _ = api
    for key in ("", "wrong"):
        assert (await client.get("/v1/services", headers={"X-API-Key": key})).status_code == 401
    for key in ("test-voice", "test-operator"):
        assert (
            await client.post(
                "/v1/services",
                headers={"X-API-Key": key},
                json={
                    "record": reviewed_record().model_dump(mode="json"),
                },
            )
        ).status_code == 403
    assert (await client.get("/v1/handoffs")).status_code == 403
    assert (
        await client.get("/v1/audit-events", headers={"X-API-Key": "test-operator"})
    ).status_code == 403
    assert (await publish(client))["service_version"] == 1
    assert (await publish(client))["service_version"] == 2
    headers = {"X-API-Key": "test-admin"}
    versions = await client.get("/v1/services/apy/versions", headers=headers)
    assert [v["version"] for v in versions.json()] == [1, 2]
    assert (await client.get("/v1/services/apy/diff/1/2", headers=headers)).json()["changes"] == {}
    cid = await create_call(client)
    result = await client.post(
        "/v1/tools/request_handoff",
        json={
            "conversation_id": cid,
            "citizen_asked_for_person": True,
            "issue_summary": "Help",
        },
    )
    hid = result.json()["handoff"]["id"]
    headers = {"X-API-Key": "test-operator"}
    assert (await client.get(f"/v1/handoffs/{hid}", headers=headers)).status_code == 200
    for status in ("contacted", "resolved"):
        assert (
            await client.patch(f"/v1/handoffs/{hid}", headers=headers, json={"status": status})
        ).status_code == 200
    assert (
        await client.patch(f"/v1/handoffs/{hid}", headers=headers, json={"status": "contacted"})
    ).status_code == 409


async def test_request_id_and_pagination_bounds(api):
    client, _, _ = api
    response = await client.post("/v1/conversations", json={}, headers={"X-Request-ID": "x" * 1000})
    assert response.status_code == 201
    assert len(response.headers["X-Request-ID"]) <= 64
    for route in ("handoffs", "audit-events"):
        for query in ("limit=-1", "limit=201", "offset=-1"):
            response = await client.get(f"/v1/{route}?{query}", headers={"X-API-Key": "test-admin"})
            assert response.status_code == 422


async def test_guidance_timestamp_is_stable(api):
    client, _, _ = api
    await publish(client)
    cid = await create_call(client)
    for _ in range(2):
        response = await client.post(
            "/v1/tools/get_documents", json={"conversation_id": cid, "slug": "apy"}
        )
        assert response.status_code == 200
        call = (await client.get(f"/v1/conversations/{cid}")).json()
        if _ == 0:
            first = call["first_guidance_at"]
        assert call["first_guidance_at"] == first


async def test_unverified_publication_is_rejected_through_api(api):
    client, _, _ = api
    record = load_records(Path(__file__).parents[1] / "data")[0]
    response = await client.post(
        "/v1/services",
        headers={"X-API-Key": "test-admin"},
        json={
            "record": record.model_dump(mode="json"),
        },
    )
    assert response.status_code == 409


@pytest.mark.parametrize("query", ["crop insurance", "fasal bima"])
async def test_voice_retrieval_returns_context_without_second_model(api, query):
    client, app, _ = api

    class NoSecondModel:
        async def answer_scheme_question(self, *args, **kwargs):
            pytest.fail("Realtime retrieval must not wait for another language model")

    app.dependency_overrides[get_model_adapter] = NoSecondModel
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": cid, "query": query, "response_mode": "context", "limit": 1},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["matches"] == []
    assert result["answer_to_citizen"] is None
    assert result["answer_basis"] == "pending_catalogue"
    assert result["verification_state"] == "unverified"
    assert result["reference_slugs"] == ["pmfby"]
    assert len(result["reference_context"]) == 1
    reference = result["reference_context"][0]
    assert reference["citation"]["verification_state"] == "pending_review"
    assert reference["citation"]["source_url"].startswith("https://")
    assert reference["publication_state"] == "unpublished_reference"
    assert "Pending references are not human-verified" in result["response_guidance"]
    assert result["retrieval_elapsed_ms"] >= 0
    # Retrieval is not evidence that audio guidance was actually heard.
    assert (await client.get(f"/v1/conversations/{cid}")).json()["first_guidance_at"] is None


async def test_context_without_references_allows_qualified_trained_knowledge(api, monkeypatch):
    from app.modules.catalogue import references

    client, app, _ = api
    monkeypatch.setattr(references, "load_reference_records", lambda _: ())

    class NoSecondModel:
        async def answer_scheme_question(self, *args, **kwargs):
            pytest.fail("Missing references must not trigger a second model")

    app.dependency_overrides[get_model_adapter] = NoSecondModel
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={
            "conversation_id": cid,
            "query": "How does crop insurance help a farmer and how do I apply?",
            "response_mode": "context",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["reference_context"] == []
    assert result["answer_to_citizen"] is None
    assert result["verification_state"] == "unverified"
    assert result["answer_basis"] == "no_matching_reference"
    guidance = result["response_guidance"]
    assert "use your trained knowledge" in guidance
    assert "clearly qualify details not supported by the retrieved source" in guidance
    assert "Do not invent exact current amounts, deadlines, or requirements" in guidance
    assert result["knowledge_fallback_allowed"] is True


async def test_rich_context_supports_concrete_answer_without_website_deflection(api):
    client, _, _ = api
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={
            "conversation_id": cid,
            "query": "PMFBY",
            "response_mode": "context",
            "limit": 1,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    reference = result["reference_context"][0]
    assert reference["slug"] == "pmfby"
    assert all(rate in reference["benefit_summary"] for rate in ("2%", "1.5%", "5%"))
    assert "Enrolment is voluntary" in reference["eligibility_summary"]
    assert any("Bank passbook" in document for document in reference["document_names"])
    assert any("Common Service Centre" in step for step in reference["application_steps"])
    guidance = result["response_guidance"]
    assert "leading with useful facts" in guidance
    assert "four to six" in guidance
    assert "Do not stop at scheme names" in guidance
    assert "practical application steps" in guidance
    assert "without a repeated blanket disclaimer" in guidance
    # Rich pending data improves explanations but cannot authorize an official verdict.
    response = await client.post(
        "/v1/tools/check_eligibility", json={"conversation_id": cid, "slug": "pmfby"}
    )
    assert response.status_code == 404


async def test_prepared_answer_http_contract_remains_available(api):
    from app.adapters.model.base import KnowledgeAnswer

    client, app, _ = api
    calls = []

    class PreparedModel:
        async def answer_scheme_question(self, query, **kwargs):
            calls.append(query)
            return KnowledgeAnswer(answer="This is unverified general guidance.", language="en")

    app.dependency_overrides[get_model_adapter] = PreparedModel
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service", json={"conversation_id": cid, "query": "crop insurance"}
    )
    assert response.status_code == 200, response.text
    assert calls == ["crop insurance"]
    result = response.json()
    assert result["answer_to_citizen"] == "This is unverified general guidance."
    assert result["reference_context"] == []
    assert result["answer_basis"] == "pending_catalogue_and_trained_knowledge"


async def test_published_context_uses_only_verified_match(api):
    client, _, _ = api
    await publish(client, "pmfby")
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={"conversation_id": cid, "query": "crop insurance", "response_mode": "context"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["matches"][0]["slug"] == "pmfby"
    assert result["verification_state"] == "verified"
    assert result["reference_context"] == []
    assert result["knowledge_fallback_allowed"] is False


async def test_mixed_context_covers_published_housing_and_pending_food(api):
    client, app, _ = api

    class NoSecondModel:
        async def answer_scheme_question(self, *args, **kwargs):
            pytest.fail("Mixed retrieval must not invoke a second model")

    app.dependency_overrides[get_model_adapter] = NoSecondModel
    await publish(client, "pmay-g")
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={
            "conversation_id": cid,
            "query": "My roof leaks and we do not have enough food",
            "response_mode": "context",
            "limit": 3,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert "pmay-g" in [item["slug"] for item in result["matches"]]
    assert "pmgkay" in result["reference_slugs"]
    assert result["verification_state"] == "mixed"
    assert result["answer_basis"] == "published_and_pending_catalogue"
    assert result["answer_to_citizen"] is None
    assert result["knowledge_fallback_allowed"] is True
    assert len(result["matches"]) + len(result["reference_context"]) <= 3
    assert set(result["context_order"]) == {
        item["slug"] for item in result["matches"] + result["reference_context"]
    }
    assert "context_order" in result["response_guidance"]
    published = next(item for item in result["matches"] if item["slug"] == "pmay-g")
    assert published["service_version"] == 1
    assert published["citation"]["verification_state"] == "verified"
    food = next(item for item in result["reference_context"] if item["slug"] == "pmgkay")
    assert food["publication_state"] == "unpublished_reference"
    assert food["citation"]["verification_state"] == "pending_review"


async def test_context_never_returns_stale_pending_copy_of_published_slug(api):
    client, _, _ = api
    await publish(client, "pmay-g")
    await publish(client, "pmay-g")
    cid = await create_call(client)
    result = (
        await client.post(
            "/v1/tools/find_service",
            json={
                "conversation_id": cid,
                "query": "PMAY-G and food support",
                "response_mode": "context",
            },
        )
    ).json()
    assert "pmay-g" not in result["reference_slugs"]
    assert all(item["slug"] != "pmay-g" for item in result["reference_context"])
    housing = next(item for item in result["matches"] if item["slug"] == "pmay-g")
    assert housing["service_version"] == 2
    assert result["context_order"].count("pmay-g") == 1


async def test_published_context_preserves_shared_need_rank_order_and_versions(api, monkeypatch):
    from app.modules.catalogue import references

    client, _, sessions = api
    await publish(client, "pmay-g")
    await publish(client, "pm-jay")
    await publish(client, "pm-jay")
    monkeypatch.setattr(references, "load_reference_records", lambda _: ())
    cid = await create_call(client)
    query = "My roof leaks and I have hospital bills"
    response = await client.post(
        "/v1/tools/find_service",
        json={
            "conversation_id": cid,
            "query": query,
            "response_mode": "context",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    from app.modules.catalogue import service as catalogue

    async with sessions() as session:
        expected = await catalogue.search(session, query, limit=3)
    assert result["context_order"] == [item.slug for item in expected]
    assert [item["slug"] for item in result["matches"]] == result["context_order"]
    assert set(result["context_order"]) == {"pmay-g", "pm-jay"}
    assert {item["slug"]: item["service_version"] for item in result["matches"]} == {
        "pmay-g": 1,
        "pm-jay": 2,
    }
    assert result["reference_context"] == []
    assert result["verification_state"] == "verified"


@pytest.mark.parametrize("limit", [1, 2, 10])
async def test_context_caps_combined_pool_and_honors_requested_limit(api, limit):
    client, _, _ = api
    await publish(client, "pmay-g")
    cid = await create_call(client)
    response = await client.post(
        "/v1/tools/find_service",
        json={
            "conversation_id": cid,
            "query": "Need housing, food, hospital support and help with farming",
            "response_mode": "context",
            "limit": limit,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["context_order"]) == min(limit, 3)
    assert len(result["matches"]) + len(result["reference_context"]) == min(limit, 3)
