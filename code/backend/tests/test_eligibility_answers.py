"""Answer validation, decision combinators, checklists and language fallback.

The existing engine tests cover guards; these cover the other half of the contract — that a
bad extraction from the model surfaces as a validation failure rather than as a confident
wrong verdict, and that a missing translation never becomes a missing fact.
"""

from __future__ import annotations

import pytest

from app.modules.eligibility import engine
from app.modules.eligibility.engine import AnswerValidationError, Outcome
from app.schemas.service_record import (
    AnswerType,
    Comparison,
    Condition,
    Decision,
    EligibilityQuestion,
    LocalizedText,
    RuleSet,
)
from tests.conftest import loan_record, loan_rule_set

FULL_ANSWERS = {
    "age": 34,
    "state": "punjab",
    "occupation": "trader",
    "annual-income": 120000,
    "has-bank-account": True,
}


# --------------------------------------------------------------------------------------
# Answer coercion and validation
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("yes", True), ("NO", False), ("true", True), ("False", False), (True, True)],
)
def test_spoken_yes_and_no_become_booleans(raw, expected) -> None:
    question = EligibilityQuestion(
        id="has-bank-account", prompt=LocalizedText(en="Bank account?"), type=AnswerType.BOOLEAN
    )
    assert engine.validate_answers([question], {"has-bank-account": raw}) == {
        "has-bank-account": expected
    }


def test_a_numeric_string_is_coerced_but_a_word_is_rejected() -> None:
    question = EligibilityQuestion(
        id="age", prompt=LocalizedText(en="Age?"), type=AnswerType.INTEGER, min=0, max=120
    )
    assert engine.validate_answers([question], {"age": "34"}) == {"age": 34}
    with pytest.raises(AnswerValidationError, match="expected a number"):
        engine.validate_answers([question], {"age": "thirty four"})


def test_a_boolean_is_never_silently_read_as_a_number() -> None:
    question = EligibilityQuestion(
        id="age", prompt=LocalizedText(en="Age?"), type=AnswerType.INTEGER
    )
    with pytest.raises(AnswerValidationError, match="yes/no"):
        engine.validate_answers([question], {"age": True})


def test_a_number_outside_the_declared_range_is_rejected() -> None:
    question = EligibilityQuestion(
        id="age", prompt=LocalizedText(en="Age?"), type=AnswerType.INTEGER, min=18, max=60
    )
    with pytest.raises(AnswerValidationError, match="below the allowed minimum"):
        engine.validate_answers([question], {"age": 17})
    with pytest.raises(AnswerValidationError, match="above the allowed maximum"):
        engine.validate_answers([question], {"age": 61})


def test_an_enum_answer_must_be_one_of_the_declared_options() -> None:
    question = EligibilityQuestion(
        id="state",
        prompt=LocalizedText(en="State?"),
        type=AnswerType.ENUM,
        options=["punjab", "haryana"],
    )
    with pytest.raises(AnswerValidationError, match="is not one of"):
        engine.validate_answers([question], {"state": "kerala"})


def test_every_bad_answer_is_reported_at_once() -> None:
    """The agent should be able to re-ask for everything it got wrong in one turn."""
    with pytest.raises(AnswerValidationError) as raised:
        engine.validate_answers(
            loan_rule_set().questions, {"age": "old", "state": "kerala", "annual-income": -5}
        )
    assert len(raised.value.errors) == 3


def test_extra_detail_from_a_transcript_is_ignored_not_rejected() -> None:
    cleaned = engine.validate_answers(
        loan_rule_set().questions, {"age": 34, "favourite-colour": "blue"}
    )
    assert cleaned == {"age": 34}


def test_an_explicit_null_answer_is_treated_as_unasked() -> None:
    cleaned = engine.validate_answers(loan_rule_set().questions, {"age": 34, "state": None})
    assert cleaned == {"age": 34}


# --------------------------------------------------------------------------------------
# Comparison operators
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "value", "answer", "expected"),
    [
        ("eq", 5, 5, True),
        ("ne", 5, 6, True),
        ("gt", 5, 6, True),
        ("gte", 5, 5, True),
        ("lt", 5, 4, True),
        ("lte", 5, 5, True),
        ("in", [1, 2], 2, True),
        ("not_in", [1, 2], 3, True),
        ("between", [1, 10], 5, True),
        ("between", [1, 10], 11, False),
    ],
)
def test_every_operator_evaluates(op, value, answer, expected) -> None:
    comparison = Comparison(var="ans", op=op, value=value)
    assert engine.evaluate_comparison(comparison, {"ans": answer}) is expected


def test_a_missing_answer_is_unknown_rather_than_false() -> None:
    comparison = Comparison(var="ans", op="gte", value=18)
    assert engine.evaluate_comparison(comparison, {}) is None
    assert engine.evaluate_comparison(comparison, {"ans": None}) is None


def test_ordering_a_non_number_is_an_error_not_a_verdict() -> None:
    comparison = Comparison(var="ans", op="gt", value=18)
    with pytest.raises(ValueError, match="needs a number"):
        engine.evaluate_comparison(comparison, {"ans": "eighteen"})


# --------------------------------------------------------------------------------------
# Decision combinators
# --------------------------------------------------------------------------------------


def _combinator_rule_set(decision: Decision) -> RuleSet:
    return RuleSet(
        rule_set_id="combinator",
        questions=[
            EligibilityQuestion(id="ans-a", prompt=LocalizedText(en="A?"), type=AnswerType.BOOLEAN),
            EligibilityQuestion(id="ans-b", prompt=LocalizedText(en="B?"), type=AnswerType.BOOLEAN),
        ],
        conditions=[
            Condition(
                id="cond-a",
                description=LocalizedText(en="A holds"),
                test=Comparison(var="ans-a", op="eq", value=True),
            ),
            Condition(
                id="cond-b",
                description=LocalizedText(en="B holds"),
                test=Comparison(var="ans-b", op="eq", value=True),
            ),
        ],
        decision=decision,
    )


def test_any_of_is_satisfied_by_one_branch_without_asking_the_rest() -> None:
    rule_set = _combinator_rule_set(Decision(any_of=["cond-a", "cond-b"]))
    result = engine.evaluate(rule_set, {"ans-a": True})
    assert result.outcome is Outcome.ELIGIBLE
    assert result.missing_answers == []


def test_any_of_keeps_asking_while_a_branch_is_still_open() -> None:
    rule_set = _combinator_rule_set(Decision(any_of=["cond-a", "cond-b"]))
    result = engine.evaluate(rule_set, {"ans-a": False})
    assert result.outcome is Outcome.NEEDS_MORE_INFO
    assert result.missing_answers == ["ans-b"]


def test_any_of_fails_only_once_every_branch_is_known() -> None:
    rule_set = _combinator_rule_set(Decision(any_of=["cond-a", "cond-b"]))
    result = engine.evaluate(rule_set, {"ans-a": False, "ans-b": False})
    assert result.outcome is Outcome.NOT_ELIGIBLE
    assert result.failed_conditions == ["cond-a", "cond-b"]


def test_none_of_rejects_a_condition_that_holds() -> None:
    rule_set = _combinator_rule_set(Decision(none_of=["cond-a"]))
    assert engine.evaluate(rule_set, {"ans-a": False}).outcome is Outcome.ELIGIBLE

    result = engine.evaluate(rule_set, {"ans-a": True})
    assert result.outcome is Outcome.NOT_ELIGIBLE
    assert result.failed_conditions == ["cond-a"]


def test_a_failure_outranks_an_outstanding_question() -> None:
    rule_set = _combinator_rule_set(Decision(all_of=["cond-a", "cond-b"]))
    result = engine.evaluate(rule_set, {"ans-a": False})
    assert result.outcome is Outcome.NOT_ELIGIBLE
    assert result.failed_conditions == ["cond-a"]


def test_missing_answers_are_listed_once_and_in_rule_order() -> None:
    result = engine.evaluate(loan_rule_set(), {"state": "punjab"})
    assert result.outcome is Outcome.NEEDS_MORE_INFO
    assert result.missing_answers == ["age", "occupation", "has-bank-account"]


def test_a_full_answer_set_decides() -> None:
    result = engine.evaluate(loan_rule_set(), FULL_ANSWERS)
    assert result.outcome is Outcome.ELIGIBLE
    assert result.failed_conditions == []


def test_a_farmer_skips_the_income_ceiling_entirely() -> None:
    answers = {**FULL_ANSWERS, "occupation": "farmer", "annual-income": 900000}
    result = engine.evaluate(loan_rule_set(), answers)
    assert result.outcome is Outcome.ELIGIBLE
    ceiling = next(c for c in result.conditions if c.id == "income-ceiling")
    assert ceiling.applicable is False


def test_the_trace_carries_the_sentence_the_rule_came_from() -> None:
    result = engine.evaluate(loan_rule_set(), FULL_ANSWERS)
    adult = next(c for c in result.conditions if c.id == "adult")
    assert adult.source_text == "Applicants must be 18 years or older."
    assert adult.depends_on == "age"


# --------------------------------------------------------------------------------------
# next_questions and the document checklist
# --------------------------------------------------------------------------------------


def test_next_questions_returns_nothing_once_the_result_is_decided() -> None:
    assert engine.next_questions(loan_rule_set(), FULL_ANSWERS) == []


def test_next_questions_carries_what_the_agent_needs_to_speak() -> None:
    questions = engine.next_questions(loan_rule_set(), {"age": 34, "occupation": "trader"})
    by_id = {q["id"]: q for q in questions}
    assert by_id["annual-income"]["unit"] == "INR"
    assert by_id["state"]["options"] == ["punjab", "haryana", "other"]
    assert by_id["state"]["type"] == "enum"


def test_a_document_gated_on_an_unanswered_question_is_kept_and_flagged() -> None:
    checklist = engine.build_document_checklist(loan_record(), {})
    land = next(item for item in checklist if item["id"] == "land-record")
    assert land["conditional"] is True
    assert land["required"] is False
    assert land["depends_on"] == "occupation"


def test_a_gated_document_becomes_required_when_the_answer_matches() -> None:
    checklist = engine.build_document_checklist(loan_record(), {"occupation": "farmer"})
    land = next(item for item in checklist if item["id"] == "land-record")
    assert land["required"] is True
    assert land["conditional"] is False


def test_the_checklist_validates_its_answers_too() -> None:
    with pytest.raises(AnswerValidationError):
        engine.build_document_checklist(loan_record(), {"occupation": "astronaut"})


# --------------------------------------------------------------------------------------
# Language
# --------------------------------------------------------------------------------------


def test_a_translated_string_is_spoken_in_that_language() -> None:
    questions = engine.next_questions(loan_rule_set(), {}, language="hi")
    state = next(q for q in questions if q["id"] == "state")
    assert state["prompt"] == "Aap kis rajya mein"


def test_a_missing_translation_falls_back_to_english_never_to_nothing() -> None:
    questions = engine.next_questions(loan_rule_set(), {}, language="hi")
    age = next(q for q in questions if q["id"] == "age")
    assert age["prompt"] == "How old are you?"


def test_an_empty_translation_falls_back_too() -> None:
    text = LocalizedText(en="Aadhaar card", hi="   ")
    assert engine.localized(text, "hi") == "Aadhaar card"


def test_an_unknown_language_falls_back_to_english() -> None:
    text = LocalizedText(en="Aadhaar card", hi="Aadhaar")
    assert engine.localized(text, "ta") == "Aadhaar card"
