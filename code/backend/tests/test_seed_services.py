from pathlib import Path

import pytest

from app.schemas.service_record import VerificationState
from app.seed.services import load_records, prepare_records, seed

DATA_DIRECTORY = Path(__file__).parents[1] / "data"


def test_catalogue_files_are_valid_pending_records() -> None:
    records = load_records(DATA_DIRECTORY)

    assert len(records) >= 18
    assert len({record.slug for record in records}) == len(records)
    assert all(
        record.citation.verification_state is VerificationState.PENDING_REVIEW
        for record in records
    )


def test_pending_records_require_explicit_review_confirmation() -> None:
    records = load_records(DATA_DIRECTORY)

    with pytest.raises(ValueError, match="--confirm-reviewed"):
        prepare_records(records, actor="reviewer", confirm_reviewed=False)


def test_review_confirmation_requires_named_human_and_marks_records() -> None:
    records = load_records(DATA_DIRECTORY)

    with pytest.raises(ValueError, match="named human reviewer"):
        prepare_records(records, actor="seed", confirm_reviewed=True)

    reviewed = prepare_records(records, actor="Dhruv", confirm_reviewed=True)
    assert all(
        record.citation.verification_state is VerificationState.VERIFIED
        for record in reviewed
    )
    assert all(record.citation.verified_by == "Dhruv" for record in reviewed)


@pytest.mark.asyncio
async def test_reviewed_catalogue_can_be_dry_run_without_database() -> None:
    count = await seed(
        DATA_DIRECTORY,
        dry_run=True,
        actor="Dhruv",
        confirm_reviewed=True,
    )

    assert count >= 18
