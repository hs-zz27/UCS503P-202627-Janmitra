import httpx
import pytest

from app.voice.client import BackendToolClient, BackendToolError


@pytest.mark.asyncio
async def test_voice_client_sends_api_key_and_typed_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "voice-secret"
        assert request.url.path == "/v1/tools/find_service"
        payload = __import__("json").loads(request.content)
        assert payload["conversation_id"] == "conversation-1"
        assert payload["category"] == "loan"
        return httpx.Response(200, json={"matches": []})

    client = BackendToolClient(
        base_url="http://backend.test",
        api_key="voice-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.find_service(
            "conversation-1",
            query="small business loan",
            category="loan",
            language="en",
        )
    finally:
        await client.close()
    assert result == {"matches": []}


@pytest.mark.asyncio
async def test_voice_client_surfaces_backend_problem() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "answers did not validate"})

    client = BackendToolClient(
        base_url="http://backend.test",
        api_key="voice-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(BackendToolError, match="answers did not validate") as raised:
            await client.get_documents(
                "conversation-1", slug="scheme", answers={}, language="en"
            )
    finally:
        await client.close()
    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_end_is_idempotent_after_handoff() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "conversation is no longer active"})

    client = BackendToolClient(
        base_url="http://backend.test",
        api_key="voice-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await client.end_conversation("conversation-1") is None
    finally:
        await client.close()
