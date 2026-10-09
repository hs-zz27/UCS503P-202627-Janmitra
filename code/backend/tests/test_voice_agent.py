from app.voice.agent import JanmitraVoiceAgent


class FakeToolClient:
    async def find_service(self, conversation_id: str, **payload):
        return {
            "matches": [],
            "suggested_handoff_trigger": "no_match",
            "answer_to_citizen": "A concrete prepared scheme answer.",
        }


async def test_prepared_fallback_hides_empty_match_signal_from_realtime_model() -> None:
    agent = JanmitraVoiceAgent(FakeToolClient(), "conversation-1")  # type: ignore[arg-type]

    result = await agent.find_service(query="crop loan")

    assert result["status"] == "answer_available"
    assert result["answer_to_citizen"] == "A concrete prepared scheme answer."
    assert "matches" not in result
    assert "suggested_handoff_trigger" not in result
    assert "Do not say that no information was found" in result["instruction"]


async def test_retrieved_context_is_returned_intact_to_native_audio_model() -> None:
    expected = {
        "matches": [],
        "reference_context": [{"slug": "crop-insurance", "verification_state": "pending_review"}],
        "knowledge_fallback_allowed": True,
        "verification_state": "unverified",
        "response_guidance": "Speak directly from references with an unverified warning.",
    }

    class ContextClient:
        async def find_service(self, *args, **kwargs):
            return expected

    agent = JanmitraVoiceAgent(ContextClient(), "conversation-1")  # type: ignore[arg-type]
    assert await agent.find_service(query="crop insurance") == expected


async def test_colloquial_category_does_not_block_ordinary_language_retrieval() -> None:
    captured = {}

    class RecordingClient:
        async def find_service(self, conversation_id, **payload):
            captured.update(payload)
            return {"reference_context": []}

    agent = JanmitraVoiceAgent(RecordingClient(), "conversation-1")  # type: ignore[arg-type]
    await agent.find_service(query="I need help finding a place to live", category="housing")  # type: ignore[arg-type]
    assert captured["category"] is None
    assert "housing" in captured["query"]
    assert "place to live" in captured["query"]
