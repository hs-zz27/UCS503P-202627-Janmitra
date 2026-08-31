"""Audit trail (FR-10).

Every critical action writes one row here, tagged with the request ID that produced it, so
a claim made to a citizen can be traced from the call, through the tool call, to the exact
service version that supplied the fact.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.context import get_request_id
from app.models import AuditEvent

logger = logging.getLogger("janmitra.audit")


async def record(
    session: AsyncSession,
    *,
    action: str,
    actor: str,
    conversation_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        request_id=get_request_id(),
        conversation_id=conversation_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    session.add(event)
    await session.flush()
    logger.info(
        "audit",
        extra={
            "action": action,
            "actor": actor,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
        },
    )
    return event
