"""Structural prompt checks; spoken quality is evaluated with native-audio scenarios."""

from app.voice.prompt import SYSTEM_PROMPT


def test_prompt_preserves_janmitra_companion_identity_and_dialects() -> None:
    assert "voice companion for rural" in SYSTEM_PROMPT
    assert "not a government officer" in SYSTEM_PROMPT
    for language in ("Hindi", "Awadhi", "Bundeli", "Telugu"):
        assert language in SYSTEM_PROMPT


def test_prompt_keeps_retrieval_and_prepared_answer_contracts() -> None:
    for field in (
        "find_service",
        "reference_context",
        "first_action",
        "document_names",
        "application_steps",
        "status: answer_available",
        "answer_to_citizen",
    ):
        assert field in SYSTEM_PROMPT


def test_prompt_preserves_published_only_rule_tools() -> None:
    assert "`check_eligibility` and `get_documents` require a published service" in SYSTEM_PROMPT
    assert "needs_more_info" in SYSTEM_PROMPT
    assert "eligibility disclaimer" in SYSTEM_PROMPT


def test_prompt_distinguishes_reference_review_and_general_knowledge() -> None:
    assert "pending Janmitra review" in SYSTEM_PROMPT
    assert "without claiming they are verified" in SYSTEM_PROMPT
    assert "do not\npresent it as checked current policy" in SYSTEM_PROMPT


def test_prompt_preserves_material_benefit_limits() -> None:
    assert "maximum benefit is not guaranteed" in SYSTEM_PROMPT
    assert "not automatically\na roof-repair grant" in SYSTEM_PROMPT
    assert "credit does not erase debt" in SYSTEM_PROMPT
    assert "Establish existing coverage" in SYSTEM_PROMPT


def test_prompt_keeps_confirmed_handoff_and_privacy_rules() -> None:
    assert "request_handoff" in SYSTEM_PROMPT
    assert "queues\na human-help request" in SYSTEM_PROMPT
    assert "Explain only what its result confirms" in SYSTEM_PROMPT
    for sensitive in ("OTP", "PIN", "password", "CVV", "Aadhaar"):
        assert sensitive in SYSTEM_PROMPT


def test_prompt_keeps_safety_routes_with_conditions() -> None:
    assert "112 for emergency" in SYSTEM_PROMPT
    assert "helpline 15100" in SYSTEM_PROMPT
    assert "District Legal Services Authority" in SYSTEM_PROMPT
    assert "eligibility for free legal aid is assessed, not automatic" in SYSTEM_PROMPT
    assert "difficulty alone is not an emergency" in SYSTEM_PROMPT
