"""Catalogue reads and versioned publication.

Reads always go through the *published* version of a service; a draft is never visible to a
citizen (non-functional requirement in context.md §13). Publication writes a new
`service_version` row and repoints the service at it — the previous version is never
mutated or deleted (context.md §18.3).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Service, ServiceVersion
from app.schemas.service_record import PublicationStatus, ServiceCategory, ServiceRecord


class ServiceNotFound(LookupError):
    pass


@dataclass(frozen=True)
class PublishedService:
    """A published service record plus the version metadata every citation needs."""

    service_id: uuid.UUID
    version_id: uuid.UUID
    version: int
    published_at: datetime | None
    record: ServiceRecord

    @property
    def slug(self) -> str:
        return self.record.slug


@dataclass(frozen=True)
class Match(PublishedService):
    score: float
    matched_on: str


async def get_published(session: AsyncSession, slug: str) -> PublishedService:
    row = (
        await session.execute(
            select(Service, ServiceVersion)
            .join(ServiceVersion, Service.current_version_id == ServiceVersion.id)
            .where(Service.slug == slug, ServiceVersion.status == PublicationStatus.PUBLISHED)
        )
    ).first()
    if row is None:
        raise ServiceNotFound(slug)
    service, version = row
    return _to_published(service, version)


async def list_published(
    session: AsyncSession, category: ServiceCategory | None = None
) -> list[PublishedService]:
    stmt = (
        select(Service, ServiceVersion)
        .join(ServiceVersion, Service.current_version_id == ServiceVersion.id)
        .where(ServiceVersion.status == PublicationStatus.PUBLISHED)
        .order_by(Service.slug)
    )
    if category is not None:
        stmt = stmt.where(Service.category == category.value)
    rows = (await session.execute(stmt)).all()
    return [_to_published(service, version) for service, version in rows]


async def list_versions(session: AsyncSession, slug: str) -> list[ServiceVersion]:
    service = (
        await session.execute(select(Service).where(Service.slug == slug))
    ).scalar_one_or_none()
    if service is None:
        raise ServiceNotFound(slug)
    return list(
        (
            await session.execute(
                select(ServiceVersion)
                .where(ServiceVersion.service_id == service.id)
                .order_by(ServiceVersion.version)
            )
        ).scalars()
    )


_TOKEN_RE = re.compile(r"[a-z0-9]+")
#: Words that carry no discriminating signal in a spoken civic request.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "for", "get", "how", "i", "in", "is", "me", "my", "need",
        "of", "on", "or", "scheme", "the", "to", "want", "what", "which", "with",
    }
)


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


async def search(
    session: AsyncSession,
    query: str,
    *,
    category: ServiceCategory | None = None,
    limit: int = 5,
) -> list[Match]:
    """Deterministic keyword match over the published catalogue.

    Structured lookup rather than a vector database (context.md §10): the catalogue is
    curated and asked about category-first, so token overlap against name, aliases and
    description is enough and is reproducible test-to-test. If catalogue growth ever makes
    this the wrong tool, the replacement is a retrieval layer behind this same function.
    """
    candidates = await list_published(session, category)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    matches: list[Match] = []
    for candidate in candidates:
        score, matched_on = _score(candidate.record, query, query_tokens)
        if score > 0:
            matches.append(
                Match(
                    service_id=candidate.service_id,
                    version_id=candidate.version_id,
                    version=candidate.version,
                    published_at=candidate.published_at,
                    record=candidate.record,
                    score=round(score, 4),
                    matched_on=matched_on,
                )
            )

    # Slug breaks ties so results are stable across runs — load tests and the AI evaluation
    # set both depend on the same query returning the same order every time.
    matches.sort(key=lambda m: (-m.score, m.record.slug))
    return matches[:limit]


def _score(record: ServiceRecord, query: str, query_tokens: set[str]) -> tuple[float, str]:
    lowered = query.lower()

    for alias in [record.name.en, *record.aliases]:
        if alias.lower() in lowered:
            return 1.0, "alias"

    name_tokens = _tokens(record.name.en) | {t for a in record.aliases for t in _tokens(a)}
    if name_tokens:
        overlap = len(query_tokens & name_tokens) / len(name_tokens)
        if overlap:
            return 0.5 + 0.4 * overlap, "name"

    body = " ".join(
        part
        for part in (
            record.description.en,
            record.benefit_summary.en if record.benefit_summary else "",
            record.eligibility_summary.en if record.eligibility_summary else "",
        )
        if part
    )
    body_tokens = _tokens(body)
    hits = len(query_tokens & body_tokens)
    if hits:
        return min(0.45, 0.15 * hits), "description"
    return 0.0, ""


async def publish(
    session: AsyncSession,
    record: ServiceRecord,
    *,
    actor: str,
    source_snapshot_id: uuid.UUID | None = None,
    review_notes: str | None = None,
) -> PublishedService:
    """Publish `record` as the next version of its service.

    Creates the service on first publication. Existing versions are left exactly as they
    are — publication is append-plus-repoint, never an update.
    """
    service = (
        await session.execute(select(Service).where(Service.slug == record.slug))
    ).scalar_one_or_none()

    if service is None:
        service = Service(slug=record.slug, category=record.category.value)
        session.add(service)
        await session.flush()
        next_version = 1
    else:
        service.category = record.category.value
        highest = (
            await session.execute(
                select(ServiceVersion.version)
                .where(ServiceVersion.service_id == service.id)
                .order_by(ServiceVersion.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        next_version = (highest or 0) + 1

    version = ServiceVersion(
        service_id=service.id,
        version=next_version,
        status=PublicationStatus.PUBLISHED,
        payload=record.model_dump(mode="json"),
        source_snapshot_id=source_snapshot_id,
        created_by=actor,
        review_notes=review_notes,
        published_at=datetime.now(UTC),
    )
    session.add(version)
    await session.flush()

    service.current_version_id = version.id
    await session.flush()
    return _to_published(service, version)


def diff_records(previous: dict[str, Any], proposed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Field-level diff for the admin review screen (context.md §8.2).

    Flattens nested structures to dotted paths so a reviewer sees "rule_set.conditions.0.
    test.value changed from 18 to 21" rather than two walls of JSON.
    """
    flat_previous = _flatten(previous)
    flat_proposed = _flatten(proposed)
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(flat_previous) | set(flat_proposed)):
        before = flat_previous.get(key)
        after = flat_proposed.get(key)
        if before != after:
            changes[key] = {"before": before, "after": after}
    return changes


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flat: dict[str, Any] = {}
        for key, item in value.items():
            flat |= _flatten(item, f"{prefix}.{key}" if prefix else str(key))
        return flat
    if isinstance(value, list):
        flat = {}
        for index, item in enumerate(value):
            flat |= _flatten(item, f"{prefix}.{index}")
        return flat
    return {prefix: value}


def _to_published(service: Service, version: ServiceVersion) -> PublishedService:
    return PublishedService(
        service_id=service.id,
        version_id=version.id,
        version=version.version,
        published_at=version.published_at,
        record=ServiceRecord.model_validate(version.payload),
    )
