"""The three adapter modes (context.md §11.7).

The mock has to be *deterministic*, not merely fake: a capacity number from the load rig
means nothing if the same utterance can take a different branch on the next run. The failure
adapter exists so the "degrade, never corrupt" requirement in §13 has a runnable test.
"""

from __future__ import annotations

import pytest

from app.adapters.model.base import IntentAction, ModelUnavailable
from app.adapters.model.factory import build_adapter, get_model_adapter
from app.adapters.model.failure import FailureModelAdapter
from app.adapters.model.mock import MockModelAdapter
from app.config import ModelAdapterMode, Settings
from app.schemas.service_record import ServiceCategory


@pytest.fixture
def mock() -> MockModelAdapter:
    return MockModelAdapter()


# --------------------------------------------------------------------------------------
# Mock adapter
# --------------------------------------------------------------------------------------


async def test_the_same_utterance_always_takes_the_same_branch(mock) -> None:
    first = await mock.extract_intent("I need a loan for my shop")
    second = await mock.extract_intent("I need a loan for my shop")
    assert first == second


@pytest.mark.parametrize(
    ("utterance", "category"),
    [
        ("I need a loan for my shop", ServiceCategory.LOAN),
        ("mujhe karz chahiye", ServiceCategory.LOAN),
        ("I want to open a bank khata", ServiceCategory.BANKING),
        ("is there a subsidy for this", ServiceCategory.GRANT),
        ("I want bima cover", ServiceCategory.INSURANCE),
        ("old age pension please", ServiceCategory.PENSION),
    ],
)
async def test_category_hints_are_recognised_in_both_languages(mock, utterance, category) -> None:
    intent = await mock.extract_intent(utterance)
    assert intent.category is category


@pytest.mark.parametrize(
    "utterance",
    ["let me talk to a person", "I want a human", "kisi se baat karni hai", "get me an operator"],
)
async def test_asking_for_a_person_is_recognised_above_everything_else(mock, utterance) -> None:
    intent = await mock.extract_intent(utterance)
    assert intent.action is IntentAction.REQUEST_HANDOFF
    assert intent.wants_human is True


async def test_an_eligibility_question_routes_to_the_rule_engine(mock) -> None:
    intent = await mock.extract_intent("am I eligible for a loan")
    assert intent.action is IntentAction.CHECK_ELIGIBILITY


async def test_a_vague_request_asks_for_clarification_below_the_handoff_threshold(mock) -> None:
    intent = await mock.extract_intent("I need some help with a form")
    assert intent.action is IntentAction.CLARIFY
    assert intent.confidence < Settings(_env_file=None).handoff_confidence_threshold


async def test_a_recognised_request_stays_above_the_handoff_threshold(mock) -> None:
    intent = await mock.extract_intent("I need a loan")
    assert intent.confidence > Settings(_env_file=None).handoff_confidence_threshold


async def test_the_summary_collapses_whitespace_and_is_bounded(mock) -> None:
    summary = await mock.summarize_issue("  I have been\n\n waiting   for weeks.  ")
    assert summary.summary == "I have been waiting for weeks."

    long = await mock.summarize_issue("word " * 5000)
    assert len(long.summary) <= 1000


async def test_an_empty_transcript_still_produces_a_valid_summary(mock) -> None:
    """`IssueSummary.summary` has `min_length=1`; an empty call must not fail validation."""
    summary = await mock.summarize_issue("   ")
    assert summary.summary == "(no summary captured)"


async def test_a_drafted_record_is_evidence_for_review_not_a_published_fact(mock) -> None:
    draft = await mock.draft_service_record(
        "Mudra Loan\nCollateral-free credit for micro enterprises.",
        source_url="https://example.gov.in/mudra",
    )
    assert draft.fields["name"] == {"en": "Mudra Loan"}
    assert draft.fields["citation"] == {"source_url": "https://example.gov.in/mudra"}
    assert draft.evidence["name"] == "Mudra Loan"


async def test_an_injected_failure_rate_is_reproducible() -> None:
    always = MockModelAdapter(failure_rate=1.0)
    with pytest.raises(ModelUnavailable, match="injected failure"):
        await always.extract_intent("I need a loan")

    never = MockModelAdapter(failure_rate=0.0)
    assert await never.extract_intent("I need a loan")


async def test_a_partial_failure_rate_hits_the_same_utterances_every_run() -> None:
    adapter = MockModelAdapter(failure_rate=0.5)
    utterances = [f"I need a loan number {n}" for n in range(40)]

    async def failures() -> set[str]:
        seen = set()
        for utterance in utterances:
            try:
                await adapter.extract_intent(utterance)
            except ModelUnavailable:
                seen.add(utterance)
        return seen

    first, second = await failures(), await failures()
    assert first == second
    # A 50% rate should actually fail roughly half of them, not none and not all.
    assert 0 < len(first) < len(utterances)


# --------------------------------------------------------------------------------------
# Failure adapter
# --------------------------------------------------------------------------------------


async def test_every_failure_adapter_call_raises_a_recoverable_error() -> None:
    adapter = FailureModelAdapter()
    for call in (
        adapter.extract_intent("anything"),
        adapter.summarize_issue("anything"),
        adapter.draft_service_record("anything", source_url="https://example.gov.in"),
    ):
        with pytest.raises(ModelUnavailable):
            await call


# --------------------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------------------


def test_the_configured_mode_selects_the_adapter() -> None:
    mock = build_adapter(Settings(_env_file=None, model_adapter=ModelAdapterMode.MOCK))
    failure = build_adapter(Settings(_env_file=None, model_adapter=ModelAdapterMode.FAILURE))
    assert mock.mode == "mock"
    assert failure.mode == "failure"


def test_mock_tuning_is_passed_through() -> None:
    adapter = build_adapter(
        Settings(
            _env_file=None,
            model_adapter=ModelAdapterMode.MOCK,
            mock_latency_ms=5,
            mock_failure_rate=1.0,
        )
    )
    assert adapter._latency_ms == 5
    assert adapter._failure_rate == 1.0


def test_real_mode_without_a_key_fails_loudly_at_selection_time() -> None:
    settings = Settings(_env_file=None, model_adapter=ModelAdapterMode.REAL, gemini_api_key=None)
    with pytest.raises(ModelUnavailable, match="JANMITRA_GEMINI_API_KEY"):
        build_adapter(settings)


def test_one_adapter_is_shared_per_process() -> None:
    assert get_model_adapter() is get_model_adapter()
