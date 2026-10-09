from __future__ import annotations

from typing import Any, Literal

from livekit.agents import Agent, llm

from app.voice.client import BackendToolClient
from app.voice.prompt import SYSTEM_PROMPT

SearchCategory = Literal["loan", "banking", "grant", "insurance", "pension", "other"]


class JanmitraVoiceAgent(Agent):
    def __init__(self, client: BackendToolClient, conversation_id: str) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.client = client
        self.conversation_id = conversation_id

    @llm.function_tool
    async def find_service(
        self,
        query: str,
        category: SearchCategory | None = None,
        language: str = "en",
        limit: int = 3,
    ) -> dict[str, Any]:
        """Call before answering public-support requests, including vague or multiple needs.

        Retrieve scheme benefits, eligibility guidance, documents and application steps.
        Accept the citizen's ordinary words and full situation; no scheme name is needed.
        Preserve multiple needs in query. Do not ask the citizen to choose a category.
        Leave category unset for broad, mixed, housing, financial-help, or uncertain needs.
        For a follow-up, include the already discussed scheme or need in query so the
        citizen does not have to repeat it. Search support relevant to their situation;
        a loan product is not a remedy for threats or existing informal debt.
        """
        # Older callers may still pass colloquial categories. They are search needs,
        # not valid API enum values; retain them in the query instead of returning 422.
        allowed_categories = {"loan", "banking", "grant", "insurance", "pension", "other"}
        if category is not None and category not in allowed_categories:
            query = f"{query} {category}".strip()
            category = None
        result = await self.client.find_service(
            self.conversation_id,
            query=query,
            category=category,
            language=language,
            limit=limit,
        )
        prepared_answer = result.get("answer_to_citizen")
        if prepared_answer:
            return {
                "status": "answer_available",
                "answer_to_citizen": prepared_answer,
                "verification_state": "unverified",
                "instruction": (
                    "Speak answer_to_citizen now. Do not say that no information was found "
                    "and do not ask another question before giving the answer. Explain its "
                    "concrete facts; qualify only uncertain details. Do not claim it was verified "
                    "or repeat a blanket disclaimer already given during this call."
                ),
            }
        return result

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
