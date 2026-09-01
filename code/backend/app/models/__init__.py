"""Persistence model — the entities named in context.md §9.

One note on a deliberate difference from the ER sketch: `eligibility_rule` is not its own
table. A scheme's rule set is stored *inside* the versioned service-record payload, so
changing a rule is necessarily a new `service_version` that goes through the same human
review gate as any other change. A side table would have let rules mutate underneath a
published version, which is precisely the thing the review gate exists to prevent.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JsonColumn


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Service(Base, TimestampMixin):
    """Scheme identity. The content of a scheme lives in its versions, never here."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("service_versions.id", ondelete="SET NULL", use_alter=True), nullable=True
    )

    versions: Mapped[list[ServiceVersion]] = relationship(
        back_populates="service",
        foreign_keys="ServiceVersion.service_id",
        order_by="ServiceVersion.version",
        cascade="all, delete-orphan",
    )
    current_version: Mapped[ServiceVersion | None] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )


class ServiceVersion(Base, TimestampMixin):
    """One immutable publication of a service record.

    Publishing writes a new row and repoints `services.current_version_id`; it never
    mutates an existing row (context.md §18.3). `payload` is a `ServiceRecord` dumped to
    JSON and is re-validated on every read.
    """

    __tablename__ = "service_versions"
    __table_args__ = (
        UniqueConstraint("service_id", "version", name="uq_service_version"),
        Index("ix_service_versions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False)
    source_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("source_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="seed")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    service: Mapped[Service] = relationship(back_populates="versions", foreign_keys=[service_id])


class SourceSnapshot(Base):
    """The official source exactly as it was at import time (context.md §11.2). Kept so a
    published claim can be traced back to the bytes it came from, and so the demo never
    depends on a government website being reachable."""

    __tablename__ = "source_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    imported_by: Mapped[str] = mapped_column(String(64), nullable=False, default="seed")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConversationChannel(StrEnum):
    PHONE = "phone"
    #: Development / automated-test / load-test harness only — never a citizen channel
    #: (context.md §8.1).
    HARNESS = "harness"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    HANDED_OFF = "handed_off"


class Conversation(Base, TimestampMixin):
    """One call. `connected_at` and `first_guidance_at` are the two timestamps that define
    Time-to-Guidance, the primary evaluation metric (proposal §6.1)."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConversationChannel.PHONE
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConversationStatus.ACTIVE
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    livekit_room: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sip_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: Set when the call is answered, not when the row is created.
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: First grounded, cited answer delivered to the citizen. Written once.
    first_guidance_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Consecutive tool failures — a deterministic handoff trigger (context.md §18.3).
    tool_failure_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False, default=dict)

    events: Mapped[list[ConversationEvent]] = relationship(
        back_populates="conversation",
        order_by="ConversationEvent.seq",
        cascade="all, delete-orphan",
    )


class ConversationEvent(Base):
    """Turn-level record of what the agent and the citizen did. Written by the voice worker
    and by every tool call, so the operator sees real context at handoff time."""

    __tablename__ = "conversation_events"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_conversation_event_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="events")


class HandoffStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    RESOLVED = "resolved"


class HandoffTrigger(StrEnum):
    """Deterministic triggers only — the model never creates a handoff record itself
    (context.md §8.3)."""

    CITIZEN_REQUEST = "citizen_request"
    LOW_CONFIDENCE = "low_confidence"
    NO_MATCH = "no_match"
    TOOL_FAILURE = "tool_failure"
    OUT_OF_SCOPE = "out_of_scope"


class HandoffRequest(Base, TimestampMixin):
    """Queued for a human operator. Contact details are optional and minimal by design
    (proposal §10 — data privacy)."""

    __tablename__ = "handoff_requests"
    __table_args__ = (Index("ix_handoff_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issue_summary: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=HandoffStatus.NEW)
    operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)


class AuditEvent(Base):
    """Structured, request-ID tagged record of every critical action (FR-10)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
