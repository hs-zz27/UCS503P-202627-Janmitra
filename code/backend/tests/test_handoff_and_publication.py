from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import ConversationStatus, HandoffTrigger
from app.modules.catalogue.service import RecordNotVerified, publish
from app.modules.conversation.service import ConversationClosed, get_active
from app.modules.handoff.service import decide_trigger
from app.schemas.service_record import Citation, LocalizedText, ServiceCategory, ServiceRecord


class FakeSession:
    def __init__(self, value) -> None:
        self.value = value

    async def get(self, model, identifier):
        return self.value


def record() -> ServiceRecord:
    return ServiceRecord(
        slug="test-service",
        name=LocalizedText(en="Test service"),
        category=ServiceCategory.GRANT,
        description=LocalizedText(en="Test description"),
        citation=Citation(
            source_url="https://example.gov.in/service",
            source_title="Official source",
            publisher="Example department",
            verified_on="2026-01-01",
        ),
    )


@pytest.mark.asyncio
async def test_unverified_record_cannot_be_published() -> None:
    with pytest.raises(RecordNotVerified):
        await publish(FakeSession(None), record(), actor="admin")


@pytest.mark.asyncio
async def test_handed_off_conversation_is_not_active() -> None:
    conversation = SimpleNamespace(status=ConversationStatus.HANDED_OFF)
    with pytest.raises(ConversationClosed):
        await get_active(FakeSession(conversation), "conversation-id")


def test_explicit_human_request_wins_trigger_order() -> None:
    trigger = decide_trigger(
        Settings(),
        citizen_asked_for_person=True,
        match_count=0,
        agent_confidence=0.1,
        tool_failure_streak=5,
        out_of_scope=True,
    )
    assert trigger is HandoffTrigger.CITIZEN_REQUEST
