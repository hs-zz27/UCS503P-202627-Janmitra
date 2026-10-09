import uuid

from sqlalchemy.dialects import postgresql

from app.modules.conversation.service import _event_lock_statement


def test_postgres_conversation_lock_uses_for_update() -> None:
    statement = _event_lock_statement(uuid.uuid4())

    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
