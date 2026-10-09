import pytest
from pydantic import ValidationError

from app.modules.eligibility.engine import AnswerValidationError, validate_answers
from app.schemas.service_record import (
    AnswerType,
    Comparison,
    Condition,
    Decision,
    EligibilityQuestion,
    LocalizedText,
    RuleSet,
)


def question(kind=AnswerType.INTEGER):
    return EligibilityQuestion(id="age", prompt=LocalizedText(en="Age?"), type=kind, min=0, max=100)


@pytest.mark.parametrize("raw", [40.9, "40.9", "NaN", "Infinity", float("nan"), float("inf"), True])
def test_invalid_integer_answers_are_rejected(raw):
    with pytest.raises(AnswerValidationError):
        validate_answers([question()], {"age": raw})


@pytest.mark.parametrize("raw", ["NaN", "-Infinity", float("nan"), float("inf"), -1, 101, True])
def test_invalid_number_answers_are_rejected(raw):
    with pytest.raises(AnswerValidationError):
        validate_answers([question(AnswerType.NUMBER)], {"age": raw})


@pytest.mark.parametrize("raw,expected", [(40, 40), (40.0, 40), ("40", 40), (0, 0), (100, 100)])
def test_valid_integer_answers_preserve_value(raw, expected):
    assert validate_answers([question()], {"age": raw}) == {"age": expected}


@pytest.mark.parametrize(
    "op,value", [("gte", "18"), ("eq", True), ("between", [40, 18]), ("lt", float("nan"))]
)
def test_bad_rule_constants_are_rejected(op, value):
    with pytest.raises(ValidationError):
        RuleSet(
            rule_set_id="test-rule",
            questions=[question()],
            conditions=[
                Condition(
                    id="adult",
                    description=LocalizedText(en="Adult"),
                    test=Comparison(var="age", op=op, value=value),
                )
            ],
            decision=Decision(all_of=["adult"]),
        )


def test_ordering_boolean_question_is_rejected():
    with pytest.raises(ValidationError, match="nonnumeric"):
        RuleSet(
            rule_set_id="test-rule",
            questions=[
                EligibilityQuestion(id="adult", prompt=LocalizedText(en="Adult?"), type="boolean")
            ],
            conditions=[
                Condition(
                    id="age-check",
                    description=LocalizedText(en="Adult"),
                    test=Comparison(var="adult", op="gte", value=1),
                )
            ],
            decision=Decision(all_of=["age-check"]),
        )
