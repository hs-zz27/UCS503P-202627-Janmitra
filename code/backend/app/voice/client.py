from __future__ import annotations

from typing import Any

import httpx


class BackendToolError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class BackendToolClient:
    """Async client for the same typed HTTP surface used by every voice integration."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=httpx.Timeout(20.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            raise BackendToolError(503, "Janmitra guidance service is unavailable") from exc
        if response.is_error:
            try:
                body = response.json()
                detail = body.get("detail", response.text)
            except ValueError:
                detail = response.text
            raise BackendToolError(response.status_code, str(detail))
        return response.json()

    async def create_conversation(
        self, *, room_name: str, channel: str = "harness", language: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/conversations",
            payload={
                "channel": channel,
                "language": language,
                "livekit_room": room_name,
                "extra": {"source": "livekit"},
            },
        )

    async def append_event(
        self, conversation_id: str, *, kind: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/conversations/{conversation_id}/events",
            payload={"kind": kind, "payload": payload},
        )

    async def end_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        try:
            return await self._request(
                "POST",
                f"/v1/conversations/{conversation_id}/end",
                payload={"status": "ended"},
            )
        except BackendToolError as exc:
            # A successful handoff already closes the conversation as `handed_off`.
            if exc.status_code == 409:
                return None
            raise

    async def find_service(
        self,
        conversation_id: str,
        *,
        query: str,
        category: str | None,
        language: str,
        limit: int = 3,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/tools/find_service",
            payload={
                "conversation_id": conversation_id,
                "query": query,
                "category": category,
                "language": language,
                "limit": limit,
            },
        )

    async def check_eligibility(
        self,
        conversation_id: str,
        *,
        slug: str,
        answers: dict[str, Any],
        language: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/tools/check_eligibility",
            payload={
                "conversation_id": conversation_id,
                "slug": slug,
                "answers": answers,
                "language": language,
            },
        )

    async def get_documents(
        self,
        conversation_id: str,
        *,
        slug: str,
        answers: dict[str, Any],
        language: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/tools/get_documents",
            payload={
                "conversation_id": conversation_id,
                "slug": slug,
                "answers": answers,
                "language": language,
            },
        )

    async def request_handoff(
        self, conversation_id: str, **signals: Any
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/tools/request_handoff",
            payload={"conversation_id": conversation_id, **signals},
        )
