from __future__ import annotations

import argparse
import asyncio
import json
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


async def seed(directory: Path, *, dry_run: bool, actor: str) -> int:
    records = load_records(directory)
    unverified = [
        record.slug
        for record in records
        if record.citation.verification_state is not VerificationState.VERIFIED
    ]
    if unverified:
        raise ValueError(f"refusing to seed unverified services: {', '.join(unverified)}")
    if dry_run:
        return len(records)

    async with get_sessionmaker()() as session:
        for record in records:
            await publish(
                session,
                record,
                actor=actor,
                review_notes="Seeded from reviewed JSON",
            )
        await session.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and seed reviewed service records")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--actor", default="seed")
    args = parser.parse_args()
    try:
        count = asyncio.run(seed(args.directory, dry_run=args.dry_run, actor=args.actor))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    verb = "Validated and published" if not args.dry_run else "Validated"
    print(f"{verb}: {count} service record(s)")
