"""The `janmitra-seed` loader.

The catalogue is described as human-reviewed (context.md §3), so the loader's job is to
refuse anything that is not — before it touches the database, and with the offending slugs
named so the reviewer knows what to check.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.seed.services import load_records, seed
from tests.conftest import loan_record, pension_record, verified_citation


def _write(directory, record) -> None:
    (directory / f"{record.slug}.json").write_text(
        record.model_dump_json(), encoding="utf-8"
    )


def test_records_load_in_a_stable_order(tmp_path) -> None:
    _write(tmp_path, pension_record())
    _write(tmp_path, loan_record())
    assert [record.slug for record in load_records(tmp_path)] == [
        "mudra-loan",
        "old-age-pension",
    ]


def test_an_empty_directory_is_an_error_not_a_silent_no_op(tmp_path) -> None:
    with pytest.raises(ValueError, match="no service JSON files"):
        load_records(tmp_path)


def test_a_record_that_does_not_fit_the_schema_is_rejected_at_load_time(tmp_path) -> None:
    payload = loan_record().model_dump(mode="json")
    del payload["citation"]
    (tmp_path / "broken.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_records(tmp_path)


async def test_a_dry_run_validates_without_writing(tmp_path) -> None:
    _write(tmp_path, loan_record())
    assert await seed(tmp_path, dry_run=True, actor="reviewer") == 1


async def test_unverified_records_are_refused_by_name(tmp_path) -> None:
    _write(tmp_path, loan_record())
    _write(
        tmp_path,
        pension_record(
            citation=verified_citation(
                verification_state="pending_review", verified_by=None
            )
        ),
    )
    with pytest.raises(ValueError, match="old-age-pension"):
        await seed(tmp_path, dry_run=True, actor="reviewer")


async def test_seeding_publishes_every_record(tmp_path, sessionmaker_, monkeypatch) -> None:
    monkeypatch.setattr("app.seed.services.get_sessionmaker", lambda: sessionmaker_)
    _write(tmp_path, loan_record())
    _write(tmp_path, pension_record())

    assert await seed(tmp_path, dry_run=False, actor="reviewer-three") == 2

    from app.modules.catalogue import service as catalogue

    async with sessionmaker_() as session:
        published = await catalogue.list_published(session)
        assert [item.slug for item in published] == ["mudra-loan", "old-age-pension"]
        version = (await catalogue.list_versions(session, "mudra-loan"))[0]
        assert version.created_by == "reviewer-three"
        assert version.review_notes == "Seeded from reviewed JSON"
