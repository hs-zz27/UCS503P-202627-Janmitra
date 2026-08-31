"""Catalogue routes.

Public reads (used by the dashboard and by tests) return only published versions. Version
history and publication are admin-only, and publishing is the one write that creates a new
version rather than editing one (FR-09).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.modules.audit import service as audit
from app.modules.catalogue import service as catalogue
from app.schemas.api import (
    PublishedServiceView,
    PublishServiceRequest,
    ServiceVersionView,
)
from app.schemas.service_record import ServiceCategory
from app.security import Role, current_role, require

router = APIRouter(prefix="/v1/services", tags=["catalogue"])


def _view(published: catalogue.PublishedService) -> PublishedServiceView:
    return PublishedServiceView(
        slug=published.record.slug,
        service_version=published.version,
        published_at=published.published_at,
        record=published.record,
    )


@router.get("", response_model=list[PublishedServiceView])
async def list_services(
    category: ServiceCategory | None = None,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(current_role),
) -> list[PublishedServiceView]:
    return [_view(item) for item in await catalogue.list_published(session, category)]


@router.get("/{slug}", response_model=PublishedServiceView)
async def get_service(
    slug: str,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(current_role),
) -> PublishedServiceView:
    try:
        return _view(await catalogue.get_published(session, slug))
    except catalogue.ServiceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no published service {slug!r}"
        ) from None


@router.get("/{slug}/versions", response_model=list[ServiceVersionView])
async def list_versions(
    slug: str,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.ADMIN)),
) -> list[ServiceVersionView]:
    try:
        versions = await catalogue.list_versions(session, slug)
    except catalogue.ServiceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no service {slug!r}"
        ) from None
    return [ServiceVersionView.model_validate(version) for version in versions]


@router.get("/{slug}/diff/{left}/{right}")
async def diff_versions(
    slug: str,
    left: int,
    right: int,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.ADMIN)),
) -> dict:
    """Field-level diff between two versions — what the reviewer approves against."""
    try:
        versions = {v.version: v for v in await catalogue.list_versions(session, slug)}
    except catalogue.ServiceNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no service {slug!r}"
        ) from None
    missing = [n for n in (left, right) if n not in versions]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{slug!r} has no version(s) {missing}",
        )
    return {
        "slug": slug,
        "left": left,
        "right": right,
        "changes": catalogue.diff_records(versions[left].payload, versions[right].payload),
    }


@router.post("", response_model=PublishedServiceView, status_code=status.HTTP_201_CREATED)
async def publish_service(
    payload: PublishServiceRequest,
    session: AsyncSession = Depends(get_session),
    role: Role = Depends(require(Role.ADMIN)),
) -> PublishedServiceView:
    published = await catalogue.publish(
        session,
        payload.record,
        actor=role.value,
        source_snapshot_id=payload.source_snapshot_id,
        review_notes=payload.review_notes,
    )
    await audit.record(
        session,
        action="service.published",
        actor=role.value,
        entity_type="service_version",
        entity_id=str(published.version_id),
        payload={"slug": published.record.slug, "version": published.version},
    )
    return _view(published)
