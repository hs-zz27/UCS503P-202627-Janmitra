from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

from app.db import get_sessionmaker
from app.modules.catalogue.service import publish
from app.schemas.service_record import ServiceRecord, VerificationState


def load_records(directory: Path) -> list[ServiceRecord]:
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError(f"no service JSON files found in {directory}")
    return [
        ServiceRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    ]


def prepare_records(
    records: list[ServiceRecord], *, actor: str, confirm_reviewed: bool
) -> list[ServiceRecord]:
    unverified = [
        record.slug
        for record in records
        if record.citation.verification_state is not VerificationState.VERIFIED
    ]
    if not unverified:
        return records
    if not confirm_reviewed:
        raise ValueError(
            "refusing to seed unverified services: "
            f"{', '.join(unverified)}; review their official sources, then pass "
            "--confirm-reviewed with a named --actor"
        )

    reviewer = actor.strip()
    if not reviewer or reviewer.casefold() == "seed":
        raise ValueError("--confirm-reviewed requires a named human reviewer in --actor")

    reviewed_on = date.today()
    return [
        record.model_copy(
            update={
                "citation": record.citation.model_copy(
                    update={
                        "verification_state": VerificationState.VERIFIED,
                        "verified_by": reviewer,
                        "verified_on": reviewed_on,
                    }
                )
            }
        )
        if record.citation.verification_state is not VerificationState.VERIFIED
        else record
        for record in records
    ]


async def seed(
    directory: Path, *, dry_run: bool, actor: str, confirm_reviewed: bool = False
) -> int:
    records = prepare_records(
        load_records(directory), actor=actor, confirm_reviewed=confirm_reviewed
    )
    if dry_run:
        return len(records)

    async with get_sessionmaker()() as session:
        for record in records:
            await publish(
                session,
                record,
                actor=actor,
                review_notes="Published from reviewed catalogue JSON",
            )
        await session.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and seed reviewed service records")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--actor", default="seed")
    parser.add_argument(
        "--confirm-reviewed",
        action="store_true",
        help="attest that --actor checked every pending record against its official source",
    )
    args = parser.parse_args()
    try:
        count = asyncio.run(
            seed(
                args.directory,
                dry_run=args.dry_run,
                actor=args.actor,
                confirm_reviewed=args.confirm_reviewed,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    verb = "Validated and published" if not args.dry_run else "Validated"
    print(f"{verb}: {count} service record(s)")
