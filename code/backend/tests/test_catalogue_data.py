from pathlib import Path

import pytest

from app.modules.catalogue.references import compact_records, deterministic_answer, ranked_records
from app.modules.catalogue.service import _score, _tokens
from app.modules.eligibility.engine import Outcome, build_document_checklist, evaluate
from app.schemas.service_record import ServiceCategory, ServiceRecord
from app.seed.services import load_records

DATA_DIRECTORY = Path(__file__).parents[1] / "data"


def records() -> list[ServiceRecord]:
    return load_records(DATA_DIRECTORY)


def record(slug: str) -> ServiceRecord:
    return next(item for item in records() if item.slug == slug)


def ranked(query: str, category: ServiceCategory | None = None) -> list[str]:
    query_tokens = _tokens(query)
    scored = [
        (_score(item, query, query_tokens)[0], item.slug)
        for item in records()
        if category is None or item.category is category
    ]
    return [slug for score, slug in sorted(scored, key=lambda item: (-item[0], item[1])) if score]


def test_generic_rural_loan_request_returns_multiple_programmes() -> None:
    matches = ranked(
        "tell me schemes about rural area maybe loan or anything",
        ServiceCategory.LOAN,
    )

    assert matches[:4] == ["pmmy", "pm-vishwakarma", "kcc", "pmegp"]


def test_common_needs_rank_the_specific_service_first() -> None:
    assert ranked("insurance for crop loss")[0] == "pmfby"
    assert ranked("pension for an unorganised worker")[0] == "pm-sym"
    assert ranked("free ration and food")[0] == "pmgkay"


def test_pending_reference_catalogue_is_available_to_knowledge_fallback() -> None:
    available = tuple(records())

    assert len(available) == 18
    assert ranked_records(available, "प्रधानमंत्री फसल बीमा योजना सरसों")[0].slug == "pmfby"
    assert ranked_records(available, "ਮੈਨੂੰ ਫਸਲ ਲਈ ਕਰਜ਼ ਚਾਹੀਦਾ ਹੈ")[0].slug == "kcc"
    assert ranked_records(available, "education scholarship for a rural college student") == []
    assert len(compact_records(available)) == 18


def test_specific_scheme_lookup_does_not_mix_in_other_insurance_products() -> None:
    available = tuple(records())
    assert [r.slug for r in ranked_records(available, "crop insurance documents")] == ["pmfby"]
    assert {r.slug for r in ranked_records(available, "PMJJBY and PMSBY premiums")} == {
        "pmjjby",
        "pmsby",
    }


@pytest.mark.parametrize(
    ("story", "expected"),
    [
        ("Our roof leaks and the landlord wants us evicted", {"pmay-g"}),
        (
            "We have no food, I lost my job, and my mother needs hospital treatment",
            {"pmgkay", "mgnrega", "pm-jay"},
        ),
        ("I need financial support and help to repair our house", {"pmay-g", "mgnrega"}),
        ("My little shop needs money to buy stock", {"pmmy", "pmegp"}),
        ("I am a farmer and borrowed money for cultivation; what loan can help?", {"kcc"}),
        ("PMFBY documents, and we also cannot pay rent", {"pmfby", "pmay-g"}),
        ("I need crop insurance and food for my children", {"pmfby", "pmgkay"}),
        (
            "My crop failed, I owe the bank, and our roof leaks. Is there one scheme for this?",
            {"pmfby", "kcc", "pmay-g"},
        ),
        ("मेरे पास मकान नहीं है और राशन चाहिए", {"pmay-g", "pmgkay"}),
        ("ਮੈਨੂੰ ਇਲਾਜ ਅਤੇ ਖਾਣਾ ਚਾਹੀਦਾ ਹੈ", {"pm-jay", "pmgkay"}),
        ("mujhe ghar aur rashan ke liye madad chahiye", {"pmay-g", "pmgkay"}),
    ],
)
def test_personal_stories_cover_distinct_needs(story, expected) -> None:
    matches = ranked_records(tuple(records()), story, limit=3)
    assert expected <= {r.slug for r in matches}
    assert len(matches) <= 3
    assert all(r.citation.verification_state.value == "pending_review" for r in matches)


@pytest.mark.parametrize(
    "query", ["financial support", "I need a loan", "I owe money and need credit"]
)
def test_broad_financial_needs_return_relevant_options(query) -> None:
    slugs = {r.slug for r in ranked_records(tuple(records()), query)}
    assert slugs
    assert slugs <= {"pmmy", "kcc", "pmegp", "pm-vishwakarma", "mgnrega", "pmjdy", "nsap"}


@pytest.mark.parametrize("query", ["crop failed", "crop failure", "crop damage", "fasal kharab"])
def test_ordinary_crop_loss_descriptions_find_crop_insurance(query) -> None:
    assert [r.slug for r in ranked_records(tuple(records()), query)] == ["pmfby"]


@pytest.mark.parametrize(
    "query",
    [
        "education scholarship for a rural college student",
        "I need legal help with a divorce",
        "Is there support for a train ticket?",
        "zzzzqwwx",
        "Can I get speech therapy?",
    ],
)
def test_uncovered_needs_do_not_return_incidental_schemes(query) -> None:
    assert ranked_records(tuple(records()), query) == []


def test_future_catalogue_domains_work_without_taxonomy_changes() -> None:
    future = record("pmay-g").model_copy(deep=True)
    future.slug = "solar-support"
    future.name.en = "Residential Solar Installation Support"
    future.aliases = ["rooftop solar", "solar panels"]
    available = (*records(), future)
    assert ranked_records(available, "Can I get solar panels?")[0].slug == "solar-support"
    mixed = ranked_records(available, "I need housing and solar panels", limit=2)
    assert {r.slug for r in mixed} == {"pmay-g", "solar-support"}


def test_exact_scheme_followup_is_focused_and_respects_category_and_limit() -> None:
    available = tuple(records())
    assert [r.slug for r in ranked_records(available, "PMFBY premiums")] == ["pmfby"]
    assert len(ranked_records(available, "housing food medical job", limit=2)) == 2
    assert all(
        r.category is ServiceCategory.LOAN
        for r in ranked_records(available, "loan", category=ServiceCategory.LOAN)
    )


def test_specific_insurance_and_pension_needs_replace_generic_parent() -> None:
    available = tuple(records())
    assert {r.slug for r in ranked_records(available, "insurance")} <= {
        "pmjjby",
        "pmsby",
        "pmfby",
        "pm-jay",
    }
    assert [r.slug for r in ranked_records(available, "insurance for my crops")] == ["pmfby"]
    assert [r.slug for r in ranked_records(available, "pension for an unorganised worker")] == [
        "pm-sym"
    ]


def test_explicitly_rejected_loan_is_not_treated_as_a_credit_need() -> None:
    matches = ranked_records(tuple(records()), "I don't want a loan, I need housing and food")
    assert {record.slug for record in matches} == {"pmay-g", "pmgkay"}


@pytest.mark.parametrize(
    "story",
    [
        "A loan collector is outside my house threatening me",
        "My landlord lent me money and wants repayment",
        "I have no money at home",
        "कर्ज देने वाला मेरे घर पर धमकी दे रहा है",
        "loan wala mere ghar ke bahar hai",
    ],
)
def test_house_as_story_setting_does_not_imply_housing_need(story) -> None:
    assert "pmay-g" not in {r.slug for r in ranked_records(tuple(records()), story)}


def test_provider_outage_answer_still_has_benefits_requirements_and_application_steps() -> None:
    answer = deterministic_answer(tuple(records()), "PMJJBY")
    assert "Rs 436" in answer
    assert "18 through 50" in answer
    assert "enrolment and consent form" in answer
    assert "auto-debit" in answer
    assert "not an official eligibility decision" in answer


def test_atal_pension_age_boundary_is_deterministic() -> None:
    rule_set = record("apy").rule_set
    assert rule_set is not None
    base_answers = {
        "indian-citizen": True,
        "has-savings-account": True,
        "income-tax-payer": False,
    }

    assert evaluate(rule_set, {**base_answers, "age": 40}).outcome is Outcome.ELIGIBLE
    assert evaluate(rule_set, {**base_answers, "age": 41}).outcome is Outcome.NOT_ELIGIBLE


def test_ujjwala_address_proof_stays_conditional() -> None:
    service = record("pmuy")
    assert service.rule_set is not None
    answers = {
        "age": 18,
        "applicant-is-woman": True,
        "poor-household": True,
        "existing-lpg": False,
    }

    assert evaluate(service.rule_set, answers).outcome is Outcome.ELIGIBLE
    checklist = build_document_checklist(service, answers)
    address_proof = next(item for item in checklist if item["id"] == "address-proof")
    assert address_proof["conditional"] is True
    assert address_proof["required"] is False


def test_worker_pension_income_boundary_is_deterministic() -> None:
    rule_set = record("pm-sym").rule_set
    assert rule_set is not None
    base_answers = {
        "age": 30,
        "unorganised-worker": True,
        "income-tax-payer": False,
        "statutory-cover": False,
    }

    assert evaluate(rule_set, {**base_answers, "monthly-income": 15000}).outcome is Outcome.ELIGIBLE
    assert (
        evaluate(rule_set, {**base_answers, "monthly-income": 15001}).outcome
        is Outcome.NOT_ELIGIBLE
    )
