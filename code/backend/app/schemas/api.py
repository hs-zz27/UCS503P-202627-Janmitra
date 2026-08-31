"""Request/response models for the non-tool routes: sessions, catalogue, queue, audit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ConversationChannel, ConversationStatus, HandoffStatus
from app.schemas.service_record import ServiceRecord


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: ConversationChannel = ConversationChannel.PHONE
    language: str | None = None
    livekit_room: str | None = Field(default=None, max_length=128)
    #: Provider call identifier from the SIP trunk, so a call can be traced end to end.
    sip_call_id: str | None = Field(default=None, max_length=128)
    #: When the call was actually answered. Supplied by the voice worker, which knows;
    #: defaults to now for the harness.
    connected_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ConversationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: str
    status: str
    language: str | None
    category: str | None
    livekit_room: str | None
    sip_call_id: str | None
    connected_at: datetime | None
    first_guidance_at: datetime | None
    ended_at: datetime | None
    tool_failure_streak: int
    created_at: datetime
    #: Seconds from call-connect to the first grounded, cited answer. Null until one lands.
    time_to_guidance_seconds: float | None = None


class ConversationEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    kind: str
    payload: dict[str, Any]
    request_id: str | None
    created_at: datetime


class AppendEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)


class EndConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ConversationStatus = ConversationStatus.ENDED


class ServiceVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    status: str
    created_by: str
    review_notes: str | None
    published_at: datetime | None
    created_at: datetime


class PublishServiceRequest(BaseModel):
    """Publish a reviewed record as the next version (FR-09)."""

    model_config = ConfigDict(extra="forbid")

    record: ServiceRecord
    review_notes: str | None = Field(default=None, max_length=2000)
    source_snapshot_id: uuid.UUID | None = None


class PublishedServiceView(BaseModel):
    slug: str
    service_version: int
    published_at: datetime | None
    record: ServiceRecord


class UpdateHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HandoffStatus
    operator_notes: str | None = Field(default=None, max_length=2000)


class HandoffContextView(BaseModel):
    """What the operator sees before calling back: the queue entry plus the call itself."""

    handoff: Any
    conversation: ConversationView
    events: list[ConversationEventView]


class AuditEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: str | None
    conversation_id: uuid.UUID | None
    actor: str
    action: str
    entity_type: str | None
    entity_id: str | None
    payload: dict[str, Any]
    created_at: datetime
