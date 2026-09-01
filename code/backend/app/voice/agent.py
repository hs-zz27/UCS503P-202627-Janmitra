from __future__ import annotations

from typing import Any

from livekit.agents import Agent, llm

from app.voice.client import BackendToolClient
from app.voice.prompt import SYSTEM_PROMPT


class JanmitraVoiceAgent(Agent):
    def __init__(self, client: BackendToolClient, conversation_id: str) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.client = client
        self.conversation_id = conversation_id

    @llm.function_tool
    async def find_service(
        self,
        query: str,
        category: str | None = None,
        language: str = "en",
        limit: int = 3,
    ) -> dict[str, Any]:
        """Find verified government services matching the citizen's stated need."""
        return await self.client.find_service(
            self.conversation_id,
            query=query,
            category=category,
            language=language,
            limit=limit,
        )

    @llm.function_tool
    async def check_eligibility(
        self,
        slug: str,
        answers: dict[str, str | int | float | bool],
        language: str = "en",
    ) -> dict[str, Any]:
        """Run the deterministic eligibility rules for a verified service."""
        return await self.client.check_eligibility(
            self.conversation_id,
            slug=slug,
            answers=answers,
            language=language,
        )

    @llm.function_tool
    async def get_documents(
        self,
        slug: str,
        answers: dict[str, str | int | float | bool],
        language: str = "en",
    ) -> dict[str, Any]:
        """Get the verified document checklist for a service."""
        return await self.client.get_documents(
            self.conversation_id,
            slug=slug,
            answers=answers,
            language=language,
        )

    @llm.function_tool
    async def request_handoff(
        self,
        language: str = "en",
        issue_summary: str | None = None,
        transcript: str | None = None,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        citizen_asked_for_person: bool = False,
        out_of_scope: bool = False,
        match_count: int | None = None,
        agent_confidence: float | None = None,
    ) -> dict[str, Any]:
        """Request a human handoff when a deterministic escalation signal is present."""
        return await self.client.request_handoff(
            self.conversation_id,
            language=language,
            issue_summary=issue_summary,
            transcript=transcript,
            contact_name=contact_name,
            contact_phone=contact_phone,
            citizen_asked_for_person=citizen_asked_for_person,
            out_of_scope=out_of_scope,
            match_count=match_count,
            agent_confidence=agent_confidence,
        )
