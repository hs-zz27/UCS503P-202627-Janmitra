from app.voice.prompt import SYSTEM_PROMPT


def test_prompt_requires_grounding_and_protects_sensitive_data() -> None:
    normalized = " ".join(SYSTEM_PROMPT.split())
    assert "Call a Janmitra tool" in normalized
    assert "Never supplement missing scheme facts" in normalized
    assert "request_handoff" in normalized
    assert "OTP" in normalized
    assert "not a government officer" in normalized
