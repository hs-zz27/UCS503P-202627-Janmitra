import pytest
from pydantic import ValidationError

from app.modules.eligibility.engine import Outcome, evaluate
from app.schemas.service_record import (
    AnswerType,
    Comparison,
    Condition,
    Decision,
    EligibilityQuestion,
    LocalizedText,
    RuleSet,
)


def text(value: str) -> LocalizedText:
    return LocalizedText(en=value)


def guarded_rule_set() -> RuleSet:
    return RuleSet(
        rule_set_id="guarded-rule",
        questions=[
            EligibilityQuestion(
                id="sector",
                prompt=text("Sector?"),
                type=AnswerType.ENUM,
                options=["service", "agriculture"],
            ),
            EligibilityQuestion(
                id="project-cost",
                prompt=text("Project cost?"),
                type=AnswerType.NUMBER,
                min=0,
            ),
            EligibilityQuestion(
                id="has-qualification",
                prompt=text("Qualification?"),
                type=AnswerType.BOOLEAN,
            ),
        ],
        conditions=[
            Condition(
                id="qualification-required",
                description=text("Qualification is required for larger service projects."),
                applies_when=[
                    Comparison(var="sector", op="eq", value="service"),
                    Comparison(var="project-cost", op="gt", value=5),
                ],
                test=Comparison(var="has-qualification", op="eq", value=True),
            )
        ],
        decision=Decision(all_of=["qualification-required"]),
    )


def test_inapplicable_guard_is_neutral() -> None:
    result = evaluate(guarded_rule_set(), {"sector": "agriculture"})
    assert result.outcome is Outcome.ELIGIBLE
    assert result.conditions[0].applicable is False
    assert result.missing_answers == []


def test_unknown_guard_asks_for_guard_answer_first() -> None:
    result = evaluate(guarded_rule_set(), {"sector": "service"})
    assert result.outcome is Outcome.NEEDS_MORE_INFO
    assert result.conditions[0].applicable is None
    assert result.missing_answers == ["project-cost"]


def test_applicable_guard_enforces_condition() -> None:
    result = evaluate(
        guarded_rule_set(),
        {"sector": "service", "project-cost": 6, "has-qualification": False},
    )
    assert result.outcome is Outcome.NOT_ELIGIBLE
    assert result.conditions[0].applicable is True
    assert result.failed_conditions == ["qualification-required"]


def test_duplicate_question_ids_are_rejected() -> None:
    question = EligibilityQuestion(id="age", prompt=text("Age?"), type=AnswerType.INTEGER)
    with pytest.raises(ValidationError, match="duplicate question ids"):
        RuleSet(
            rule_set_id="bad-rule",
            questions=[question, question],
            conditions=[
                Condition(
                    id="adult",
                    description=text("Adult"),
                    test=Comparison(var="age", op="gte", value=18),
                )
            ],
            decision=Decision(all_of=["adult"]),
        )
