"""Align PostgreSQL JSON storage with the ORM without rewriting deployed migrations."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002_jsonb_columns"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None

COLUMNS = (
    ("service_versions", "payload"),
    ("conversations", "extra"),
    ("conversation_events", "payload"),
    ("audit_events", "payload"),
)


def upgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table, column, existing_type=sa.JSON(), type_=postgresql.JSONB(),
            postgresql_using=f"{column}::jsonb", existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table, column, existing_type=postgresql.JSONB(), type_=sa.JSON(),
            postgresql_using=f"{column}::json", existing_nullable=False,
        )
