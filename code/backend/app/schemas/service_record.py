"""The canonical service record — one validated schema per government scheme.

context.md §9 / §11.1: discovery, the document checklist, the eligibility engine, the
citation shown to the citizen and the admin review screen all read *this* record. It is
frozen before any screen exists, because changing it later changes five surfaces at once.

The eligibility rule set embedded here is data, not code: a new scheme becomes rule-backed
by adding conditions to `eligibility.rule_set`, never by writing a new evaluator
(context.md §11.5).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")]


class ServiceCategory(StrEnum):
    """Categories are open-ended by design — the catalogue grows through the semester
    (proposal §4.1) — but discovery asks a coarse category question first, so the set is
    enumerated rather than free text (context.md §11.4)."""

    LOAN = "loan"
    BANKING = "banking"
    GRANT = "grant"
    INSURANCE = "insurance"
    PENSION = "pension"
    OTHER = "other"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class AnswerType(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    ENUM = "enum"
    STRING = "string"


class LocalizedText(BaseModel):
    """Short strings the agent may read aloud. `en` is mandatory as the pivot; other
    languages are added as they are validated (context.md §18.1 language sweep)."""

    model_config = ConfigDict(extra="allow")

    en: str
    hi: str | None = None


class EligibilityQuestion(BaseModel):
    """One question the agent asks the citizen before the rule engine can decide."""

    model_config = ConfigDict(extra="forbid")

    id: Slug
    prompt: LocalizedText
    type: AnswerType
    options: list[str] | None = None
    unit: str | None = None
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _check_enum_options(self) -> EligibilityQuestion:
        if self.type is AnswerType.ENUM and not self.options:
            raise ValueError(f"question {self.id!r} is an enum but declares no options")
        if self.type is not AnswerType.ENUM and self.options:
            raise ValueError(f"question {self.id!r} declares options but is not an enum")
        return self


ComparisonOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "between"]


class Comparison(BaseModel):
    """A leaf condition: compare one answer against a constant from the official source."""

    model_config = ConfigDict(extra="forbid")

    var: Slug
    op: ComparisonOp
    value: Any

    @model_validator(mode="after")
    def _check_value_shape(self) -> Comparison:
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"op {self.op!r} on {self.var!r} needs a list value")
        if self.op == "between" and (
            not isinstance(self.value, list) or len(self.value) != 2
        ):
            raise ValueError(f"op 'between' on {self.var!r} needs a [low, high] value")
        return self


class Condition(BaseModel):
    """A named, citable condition. `source_text` is the sentence from the official source
    that justifies it — it is what makes an eligibility result explainable and reviewable."""

    model_config = ConfigDict(extra="forbid")

    id: Slug
    description: LocalizedText
    source_text: str | None = None
    #: Guards make a condition conditional without turning the rule set into an opaque
    #: expression tree. Every guard must pass before `test` applies.
    applies_when: list[Comparison] = Field(default_factory=list)
    test: Comparison


class Decision(BaseModel):
    """How the named conditions combine. Nesting is deliberate but shallow: official rules
    are usually 'all of these, and any one of those'."""

    model_config = ConfigDict(extra="forbid")

    all_of: list[str] = Field(default_factory=list)
    any_of: list[str] = Field(default_factory=list)
    none_of: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _non_empty(self) -> Decision:
        if not (self.all_of or self.any_of or self.none_of):
            raise ValueError("decision must reference at least one condition")
        return self


class RuleSet(BaseModel):
    """A scheme's deterministic eligibility rules. Absent for schemes that are published
    with a checklist and citation only (context.md §7: rule sets arrive scheme by scheme)."""

    model_config = ConfigDict(extra="forbid")

    rule_set_id: Slug
    questions: list[EligibilityQuestion] = Field(min_length=1)
    conditions: list[Condition] = Field(min_length=1)
    decision: Decision

    @model_validator(mode="after")
    def _check_references(self) -> RuleSet:
        question_id_list = [q.id for q in self.questions]
        if len(question_id_list) != len(set(question_id_list)):
            raise ValueError("duplicate question ids in rule set")
        question_ids = set(question_id_list)
        condition_ids = [c.id for c in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("duplicate condition ids in rule set")

        for condition in self.conditions:
            comparisons = [*condition.applies_when, condition.test]
            for comparison in comparisons:
                if comparison.var not in question_ids:
                    raise ValueError(
                        f"condition {condition.id!r} tests {comparison.var!r}, "
                        "which is not a declared question"
                    )

        known = set(condition_ids)
        referenced = set(self.decision.all_of) | set(self.decision.any_of) | set(
            self.decision.none_of
        )
        unknown = referenced - known
        if unknown:
            raise ValueError(f"decision references unknown conditions: {sorted(unknown)}")
        return self


class RequiredDocument(BaseModel):
    """Checklist entries are selected deterministically, never drafted by the model
    (context.md §8.3). `required_when` gates a document on an eligibility answer."""

    model_config = ConfigDict(extra="forbid")

    id: Slug
    name: LocalizedText
    notes: LocalizedText | None = None
    required_when: Comparison | None = None


class ApplicationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1)
    instruction: LocalizedText


class VerificationState(StrEnum):
    """Whether a human has actually checked this record against its official source.

    Seeded and freshly imported records start `pending_review`. Only a named person moves
    one to `verified` — the catalogue is described as human-reviewed (context.md §3), so
    the record has to be able to say when it is not yet.
    """

    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"


class Citation(BaseModel):
    """Every factual answer carries this (FR-04). `verified_on` is the date the record was
    last checked against the official page — not the date it was imported."""

    model_config = ConfigDict(extra="forbid")

    source_url: HttpUrl
    source_title: str
    publisher: str
    verified_on: date
    verification_state: VerificationState = VerificationState.PENDING_REVIEW
    #: The team member who checked it. Required once the state is `verified`.
    verified_by: str | None = None
    snapshot_id: str | None = None

    @model_validator(mode="after")
    def _verified_needs_a_name(self) -> Citation:
        if self.verification_state is VerificationState.VERIFIED and not self.verified_by:
            raise ValueError("a verified citation must record who verified it")
        return self


class ServiceRecord(BaseModel):
    """The frozen canonical record. Persisted verbatim as the JSON payload of a
    `service_version`; every read path validates back into this model."""

    model_config = ConfigDict(extra="forbid")

    slug: Slug
    name: LocalizedText
    aliases: list[str] = Field(default_factory=list)
    category: ServiceCategory
    description: LocalizedText
    benefit_summary: LocalizedText | None = None
    eligibility_summary: LocalizedText | None = None
    rule_set: RuleSet | None = None
    documents: list[RequiredDocument] = Field(default_factory=list)
    steps: list[ApplicationStep] = Field(default_factory=list)
    citation: Citation

    @model_validator(mode="after")
    def _documents_reference_questions(self) -> ServiceRecord:
        """A conditional document can only depend on a question the rule set actually asks."""
        question_ids = {q.id for q in self.rule_set.questions} if self.rule_set else set()
        for document in self.documents:
            if document.required_when and document.required_when.var not in question_ids:
                raise ValueError(
                    f"document {document.id!r} is conditional on {document.required_when.var!r}, "
                    "which no eligibility question asks"
                )
        return self

    @property
    def is_rule_backed(self) -> bool:
        return self.rule_set is not None
