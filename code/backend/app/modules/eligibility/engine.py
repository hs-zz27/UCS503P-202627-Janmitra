"""The deterministic eligibility evaluator.

Pure functions over a `RuleSet` and a dict of citizen answers: no database, no network, no
model. That is the whole point — eligibility is explainable and testable (proposal §5.1),
and adding a scheme to the engine means adding JSON conditions, not code (context.md §11.5).

Three-valued by design. A missing answer is *unknown*, not false, so the agent can ask for
exactly the answer it still needs instead of telling a citizen they do not qualify when in
fact nobody asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.schemas.service_record import (
    AnswerType,
    Comparison,
    EligibilityQuestion,
    RequiredDocument,
    RuleSet,
    ServiceRecord,
)


class Outcome(StrEnum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_MORE_INFO = "needs_more_info"


class AnswerValidationError(ValueError):
    """An answer does not fit the question it answers. Raised before evaluation so a bad
    extraction from the model surfaces as a validation failure, never as a wrong result."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class ConditionResult:
    id: str
    description: str
    #: True / False / None, where None means an answer it depends on is missing.
    passed: bool | None
    depends_on: str
    source_text: str | None = None


@dataclass(frozen=True)
class EligibilityResult:
    outcome: Outcome
    conditions: list[ConditionResult]
    #: Question ids the engine still needs before it can decide.
    missing_answers: list[str] = field(default_factory=list)
    #: Condition ids that decided a NOT_ELIGIBLE outcome.
    failed_conditions: list[str] = field(default_factory=list)


_SENTINEL = object()


def validate_answers(
    questions: list[EligibilityQuestion], answers: dict[str, Any]
) -> dict[str, Any]:
    """Coerce and range-check answers. Unknown keys are ignored rather than rejected, since
    a voice transcript may carry extra detail the rule set does not use."""
    known = {q.id: q for q in questions}
    errors: list[str] = []
    cleaned: dict[str, Any] = {}

    for key, raw in answers.items():
        question = known.get(key)
        if question is None or raw is None:
            continue
        try:
            cleaned[key] = _coerce(question, raw)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise AnswerValidationError(errors)
    return cleaned


def _coerce(question: EligibilityQuestion, raw: Any) -> Any:
    match question.type:
        case AnswerType.BOOLEAN:
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str) and raw.strip().lower() in {"true", "false", "yes", "no"}:
                return raw.strip().lower() in {"true", "yes"}
            raise ValueError(f"{question.id}: expected a yes/no answer, got {raw!r}")
        case AnswerType.INTEGER | AnswerType.NUMBER:
            if isinstance(raw, bool):
                raise ValueError(f"{question.id}: expected a number, got a yes/no answer")
            try:
                value = int(raw) if question.type is AnswerType.INTEGER else float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{question.id}: expected a number, got {raw!r}") from exc
            if question.min is not None and value < question.min:
                raise ValueError(f"{question.id}: {value} is below the allowed minimum {question.min}")
            if question.max is not None and value > question.max:
                raise ValueError(f"{question.id}: {value} is above the allowed maximum {question.max}")
            return value
        case AnswerType.ENUM:
            value = str(raw)
            if value not in (question.options or []):
                raise ValueError(
                    f"{question.id}: {value!r} is not one of {question.options}"
                )
            return value
        case AnswerType.STRING:
            return str(raw)
    raise ValueError(f"{question.id}: unsupported answer type {question.type}")


def evaluate_comparison(test: Comparison, answers: dict[str, Any]) -> bool | None:
    """Evaluate one leaf comparison. Returns None when the answer it needs is missing."""
    value = answers.get(test.var, _SENTINEL)
    if value is _SENTINEL or value is None:
        return None

    match test.op:
        case "eq":
            return value == test.value
        case "ne":
            return value != test.value
        case "gt":
            return _as_number(value) > _as_number(test.value)
        case "gte":
            return _as_number(value) >= _as_number(test.value)
        case "lt":
            return _as_number(value) < _as_number(test.value)
        case "lte":
            return _as_number(value) <= _as_number(test.value)
        case "in":
            return value in test.value
        case "not_in":
            return value not in test.value
        case "between":
            low, high = test.value
            return _as_number(low) <= _as_number(value) <= _as_number(high)
    raise ValueError(f"unsupported operator {test.op!r}")


def _as_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"ordering comparison needs a number, got {value!r}")
    return float(value)


def evaluate(rule_set: RuleSet, answers: dict[str, Any], *, language: str = "en") -> EligibilityResult:
    """Run a rule set against a citizen's answers.

    Answers are validated first; a validation failure raises rather than guessing. The
    returned trace lists every condition, including the ones that could not be decided, so
    the agent can explain the result and the team can test boundary cases against it.
    """
    cleaned = validate_answers(rule_set.questions, answers)

    results: list[ConditionResult] = []
    by_id: dict[str, bool | None] = {}
    for condition in rule_set.conditions:
        passed = evaluate_comparison(condition.test, cleaned)
        by_id[condition.id] = passed
        results.append(
            ConditionResult(
                id=condition.id,
                description=localized(condition.description, language),
                passed=passed,
                depends_on=condition.test.var,
                source_text=condition.source_text,
            )
        )

    decision = rule_set.decision
    failed: list[str] = []
    undecided: list[str] = []

    # all_of: every condition must hold.
    for cid in decision.all_of:
        if by_id[cid] is False:
            failed.append(cid)
        elif by_id[cid] is None:
            undecided.append(cid)

    # none_of: every condition must be false.
    for cid in decision.none_of:
        if by_id[cid] is True:
            failed.append(cid)
        elif by_id[cid] is None:
            undecided.append(cid)

    # any_of: at least one must hold. Only decisive once every branch is known.
    if decision.any_of:
        states = [by_id[cid] for cid in decision.any_of]
        if not any(state is True for state in states):
            if any(state is None for state in states):
                undecided.extend(cid for cid in decision.any_of if by_id[cid] is None)
            else:
                failed.extend(decision.any_of)

    # A definite failure is decisive even if other conditions are still unknown: no further
    # question can rescue a mandatory condition that has already failed.
    if failed:
        outcome = Outcome.NOT_ELIGIBLE
    elif undecided:
        outcome = Outcome.NEEDS_MORE_INFO
    else:
        outcome = Outcome.ELIGIBLE

    missing = _ordered_unique(
        condition.test.var
        for condition in rule_set.conditions
        if condition.id in undecided
    )
    return EligibilityResult(
        outcome=outcome,
        conditions=results,
        missing_answers=missing,
        failed_conditions=_ordered_unique(failed),
    )


def next_questions(
    rule_set: RuleSet, answers: dict[str, Any], *, language: str = "en"
) -> list[dict[str, Any]]:
    """The questions still worth asking, in rule-set order — what the agent reads out next."""
    result = evaluate(rule_set, answers)
    wanted = set(result.missing_answers)
    return [
        {
            "id": question.id,
            "prompt": localized(question.prompt, language),
            "type": question.type.value,
            "options": question.options,
            "unit": question.unit,
        }
        for question in rule_set.questions
        if question.id in wanted
    ]


def build_document_checklist(
    record: ServiceRecord, answers: dict[str, Any] | None = None, *, language: str = "en"
) -> list[dict[str, Any]]:
    """Select the document checklist deterministically (FR-06).

    A document gated on an answer the citizen has not given yet is kept in the list and
    marked `conditional`, because telling someone they might need a paper is more useful on
    a phone call than silently dropping it.
    """
    cleaned: dict[str, Any] = {}
    if answers and record.rule_set:
        cleaned = validate_answers(record.rule_set.questions, answers)

    checklist: list[dict[str, Any]] = []
    for document in record.documents:
        entry = _document_entry(document, cleaned, language)
        if entry is not None:
            checklist.append(entry)
    return checklist


def _document_entry(
    document: RequiredDocument, answers: dict[str, Any], language: str
) -> dict[str, Any] | None:
    required = True
    conditional = False
    if document.required_when is not None:
        state = evaluate_comparison(document.required_when, answers)
        if state is False:
            return None
        if state is None:
            conditional = True
            required = False
    return {
        "id": document.id,
        "name": localized(document.name, language),
        "notes": localized(document.notes, language) if document.notes else None,
        "required": required,
        "conditional": conditional,
        "depends_on": document.required_when.var if document.required_when else None,
    }


def localized(text: Any, language: str) -> str:
    """Pick a language off a LocalizedText, falling back to English.

    Falling back is correct rather than lazy: the record is the *verified* text, and the
    model translates it for the citizen at speaking time (context.md §8.3). A missing
    translation must never become a missing fact.
    """
    value = getattr(text, language, None)
    if isinstance(value, str) and value.strip():
        return value
    return text.en


def _ordered_unique(items) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)
