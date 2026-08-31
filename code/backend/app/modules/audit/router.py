"""Audit read routes — the evidence trail behind a demo claim (FR-10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditEvent
from app.schemas.api import AuditEventView
from app.security import Role, require

router = APIRouter(
    prefix="/v1/audit-events",
    tags=["audit"],
    dependencies=[Depends(require(Role.ADMIN))],
)


@router.get("", response_model=list[AuditEventView])
async def list_audit_events(
    conversation_id: uuid.UUID | None = None,
    request_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventView]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id)
    if conversation_id is not None:
        stmt = stmt.where(AuditEvent.conversation_id == conversation_id)
    if request_id is not None:
        stmt = stmt.where(AuditEvent.request_id == request_id)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars()
    return [AuditEventView.model_validate(row) for row in rows]
