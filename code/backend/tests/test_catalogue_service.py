"""Catalogue search, versioned publication and the reviewer's diff.

Publication is append-plus-repoint (context.md §18.3): the tests below assert that an older
version is still readable and byte-identical after a newer one is published, because that is
what makes a citation checkable months later.
"""

from __future__ import annotations

import pytest

from app.modules.catalogue import service as catalogue
from app.modules.catalogue.service import RecordNotVerified, ServiceNotFound
from app.schemas.service_record import LocalizedText, ServiceCategory, VerificationState
from tests.conftest import loan_record, pension_record, verified_citation

# --------------------------------------------------------------------------------------
# Publication and versioning
# --------------------------------------------------------------------------------------


async def test_first_publication_creates_version_one(session) -> None:
    published = await catalogue.publish(session, loan_record(), actor="admin")
    assert published.version == 1
    assert published.published_at is not None
    assert published.slug == "mudra-loan"


async def test_publishing_again_appends_a_version_and_repoints(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    updated = loan_record(benefit_summary=LocalizedText(en="Up to 20 lakh rupees of credit."))
    second = await catalogue.publish(session, updated, actor="admin")

    assert second.version == 2
    current = await catalogue.get_published(session, "mudra-loan")
    assert current.version == 2
    assert current.record.benefit_summary.en == "Up to 20 lakh rupees of credit."

    versions = await catalogue.list_versions(session, "mudra-loan")
    assert [v.version for v in versions] == [1, 2]
    # The superseded version keeps its own text — publication never mutates history.
    assert versions[0].payload["benefit_summary"]["en"] == "Up to 10 lakh rupees of credit."


async def test_publication_records_actor_and_review_notes(session) -> None:
    await catalogue.publish(
        session, loan_record(), actor="reviewer-two", review_notes="checked against the PDF"
    )
    version = (await catalogue.list_versions(session, "mudra-loan"))[0]
    assert version.created_by == "reviewer-two"
    assert version.review_notes == "checked against the PDF"
    assert version.status == "published"


async def test_a_recategorised_scheme_moves_with_its_new_version(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    await catalogue.publish(
        session, loan_record(category=ServiceCategory.GRANT), actor="admin"
    )
    assert await catalogue.list_published(session, ServiceCategory.LOAN) == []
    assert len(await catalogue.list_published(session, ServiceCategory.GRANT)) == 1


async def test_an_unverified_record_is_refused(session) -> None:
    pending = loan_record(
        citation=verified_citation(
            verification_state=VerificationState.PENDING_REVIEW, verified_by=None
        )
    )
    with pytest.raises(RecordNotVerified, match="human-verified"):
        await catalogue.publish(session, pending, actor="admin")


async def test_reading_an_unknown_slug_raises(session) -> None:
    with pytest.raises(ServiceNotFound):
        await catalogue.get_published(session, "no-such-scheme")
    with pytest.raises(ServiceNotFound):
        await catalogue.list_versions(session, "no-such-scheme")


async def test_list_published_is_ordered_by_slug(session) -> None:
    await catalogue.publish(session, pension_record(), actor="admin")
    await catalogue.publish(session, loan_record(), actor="admin")
    assert [p.slug for p in await catalogue.list_published(session)] == [
        "mudra-loan",
        "old-age-pension",
    ]


# --------------------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------------------


async def test_an_alias_beats_a_description_hit(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    await catalogue.publish(
        session,
        pension_record(
            description=LocalizedText(
                en="Support for retired people who once ran a small business."
            )
        ),
        actor="admin",
    )
    matches = await catalogue.search(session, "I need a small business loan")
    assert [m.record.slug for m in matches] == ["mudra-loan", "old-age-pension"]
    assert matches[0].matched_on == "alias"
    assert matches[0].score == 1.0
    assert matches[1].matched_on == "description"


async def test_a_name_hit_scores_above_a_description_hit(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    matches = await catalogue.search(session, "mudra")
    assert matches[0].matched_on == "name"
    assert 0.5 < matches[0].score < 1.0


async def test_a_stopword_only_query_matches_nothing(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    assert await catalogue.search(session, "how do I get the scheme") == []


async def test_search_never_returns_an_unrelated_scheme(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    await catalogue.publish(session, pension_record(), actor="admin")
    assert await catalogue.search(session, "passport renewal appointment") == []


async def test_search_honours_the_category_filter_and_limit(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    await catalogue.publish(session, pension_record(), actor="admin")

    filtered = await catalogue.search(session, "pension loan", category=ServiceCategory.PENSION)
    assert [m.record.slug for m in filtered] == ["old-age-pension"]

    capped = await catalogue.search(session, "pension loan", limit=1)
    assert len(capped) == 1


async def test_search_is_stable_across_runs(session) -> None:
    """Load tests and the AI evaluation set both assume one query, one order."""
    await catalogue.publish(session, loan_record(), actor="admin")
    await catalogue.publish(session, pension_record(), actor="admin")
    first = [m.record.slug for m in await catalogue.search(session, "credit pension support")]
    second = [m.record.slug for m in await catalogue.search(session, "credit pension support")]
    assert first == second


async def test_search_reads_the_current_version_not_a_superseded_one(session) -> None:
    await catalogue.publish(session, loan_record(), actor="admin")
    stale = await catalogue.search(session, "micro credit")
    assert stale[0].matched_on == "alias"

    await catalogue.publish(session, loan_record(aliases=["kisan credit"]), actor="admin")
    fresh = await catalogue.search(session, "micro credit")
    assert fresh[0].version == 2
    # The v1 alias is gone, so this can only be a weaker name-token hit now.
    assert fresh[0].matched_on == "name"
    assert fresh[0].score < stale[0].score

    renamed = await catalogue.search(session, "kisan credit")
    assert [m.matched_on for m in renamed] == ["alias"]


# --------------------------------------------------------------------------------------
# Reviewer diff
# --------------------------------------------------------------------------------------


def test_diff_reports_a_changed_leaf_by_dotted_path() -> None:
    previous = loan_record().model_dump(mode="json")
    proposed = loan_record().model_dump(mode="json")
    proposed["rule_set"]["conditions"][0]["test"]["value"] = 21

    changes = catalogue.diff_records(previous, proposed)
    assert changes == {
        "rule_set.conditions.0.test.value": {"before": 18, "after": 21}
    }


def test_diff_reports_added_and_removed_fields() -> None:
    previous = pension_record().model_dump(mode="json")
    proposed = pension_record(
        benefit_summary=LocalizedText(en="1000 rupees a month."), aliases=[]
    ).model_dump(mode="json")

    changes = catalogue.diff_records(previous, proposed)
    assert changes["benefit_summary.en"] == {"before": None, "after": "1000 rupees a month."}
    assert changes["aliases.0"] == {"before": "vridha pension", "after": None}


def test_an_unchanged_record_diffs_to_nothing() -> None:
    payload = loan_record().model_dump(mode="json")
    assert catalogue.diff_records(payload, payload) == {}
