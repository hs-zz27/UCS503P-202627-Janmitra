"""Create the initial Janmitra schema."""

import sqlalchemy as sa

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("imported_by", sa.String(64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_source_snapshots_content_sha256", "source_snapshots", ["content_sha256"]
    )

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_services_category", "services", ["category"])

    op.create_table(
        "service_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Uuid(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "source_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("source_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("review_notes", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("service_id", "version", name="uq_service_version"),
    )
    op.create_index("ix_service_versions_service_id", "service_versions", ["service_id"])
    op.create_index("ix_service_versions_status", "service_versions", ["status"])
    op.create_foreign_key(
        "fk_services_current_version_id_service_versions",
        "services",
        "service_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("category", sa.String(32)),
        sa.Column("livekit_room", sa.String(128)),
        sa.Column("sip_call_id", sa.String(128)),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("first_guidance_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("tool_failure_streak", sa.Integer(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "conversation_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_conversation_event_seq"),
    )
    op.create_index(
        "ix_conversation_events_conversation_id",
        "conversation_events",
        ["conversation_id"],
    )

    op.create_table(
        "handoff_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32)),
        sa.Column("contact_name", sa.String(128)),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("issue_summary", sa.Text(), nullable=False),
        sa.Column("trigger_reason", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("operator_notes", sa.Text()),
        sa.Column("language", sa.String(16)),
        *_timestamps(),
    )
    op.create_index(
        "ix_handoff_requests_conversation_id",
        "handoff_requests",
        ["conversation_id"],
    )
    op.create_index(
        "ix_handoff_status_created", "handoff_requests", ["status", "created_at"]
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.String(64)),
        sa.Column("conversation_id", sa.Uuid()),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index(
        "ix_audit_events_conversation_id", "audit_events", ["conversation_id"]
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("handoff_requests")
    op.drop_table("conversation_events")
    op.drop_table("conversations")
    op.drop_constraint(
        "fk_services_current_version_id_service_versions",
        "services",
        type_="foreignkey",
    )
    op.drop_table("service_versions")
    op.drop_table("services")
    op.drop_table("source_snapshots")
