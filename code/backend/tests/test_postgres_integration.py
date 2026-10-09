"""Opt-in real PostgreSQL tests; every test owns and removes a unique schema."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.models import (
    Conversation,
    HandoffRequest,
    HandoffStatus,
    HandoffTrigger,
)
from app.modules.catalogue import service as catalogue
from app.modules.conversation import service as conversations
from app.modules.handoff import service as handoffs
from tests.test_api_integration import reviewed_record

DATABASE_URL = os.environ.get("JANMITRA_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="JANMITRA_TEST_DATABASE_URL is not set")


@pytest.fixture
async def postgres():
    schema = "janmitra_test_" + uuid.uuid4().hex
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"server_settings": {"search_path": schema}},
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    def migrate(connection, operation, *args):
        config.attributes["connection"] = connection
        operation(config, *args)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate, command.upgrade, "head")
        yield engine, async_sessionmaker(engine, expire_on_commit=False), migrate
    finally:
        # Only the UUID-named schema created by this test is removed; public data is untouched.
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


async def test_migration_roundtrip_and_schema_matches_models(postgres):
    engine, _, migrate = postgres
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO audit_events (id, actor, action, payload) "
                "VALUES (:id, 'test', 'migration', CAST(:payload AS jsonb))"
            ),
            {"id": uuid.uuid4(), "payload": '{"retained": true}'},
        )
        await connection.run_sync(migrate, command.downgrade, "001_initial_schema")
        assert (
            await connection.execute(text("SELECT pg_typeof(payload)::text FROM audit_events"))
        ).scalar_one() == "json"
        await connection.run_sync(migrate, command.upgrade, "head")
        value = (await connection.execute(text("SELECT payload FROM audit_events"))).scalar_one()
        assert value == {"retained": True}
        await connection.run_sync(migrate, command.check)


async def test_concurrent_first_and_later_publications(postgres):
    _, sessions, _ = postgres

    async def publish():
        async with sessions.begin() as session:
            result = await catalogue.publish(session, reviewed_record(), actor="test")
            return result.version

    versions = await asyncio.gather(*(publish() for _ in range(8)))
    assert sorted(versions) == list(range(1, 9))
    async with sessions() as session:
        assert (await catalogue.get_published(session, "apy")).version == 8
        assert len(await catalogue.list_versions(session, "apy")) == 8


async def test_concurrent_events_counters_and_write_once_guidance(postgres):
    _, sessions, _ = postgres
    async with sessions.begin() as session:
        conversation = await conversations.create(session, channel="harness")
        cid = conversation.id

    async def append(index):
        at = datetime(2026, 10, 9, 12, 0, index, tzinfo=UTC)
        async with sessions.begin() as session:
            conversation = await conversations.get_active(session, cid)
            await conversations.note_tool_failure(session, conversation)
            await conversations.mark_guidance_delivered(session, conversation, at=at)
            await conversations.append_event(
                session, conversation, kind="test", payload={"i": index}
            )

    await asyncio.gather(*(append(i) for i in range(12)))
    async with sessions() as session:
        conversation = await conversations.get(session, cid)
        assert conversation.tool_failure_streak == 12
        assert [e.seq for e in await conversations.events(session, cid)] == list(range(1, 13))
        first = conversation.first_guidance_at
    async with sessions.begin() as session:
        conversation = await conversations.get_active(session, cid)
        await conversations.mark_guidance_delivered(session, conversation)
        assert conversation.first_guidance_at == first


async def test_end_and_handoff_cannot_both_win(postgres):
    _, sessions, _ = postgres
    async with sessions.begin() as session:
        cid = (await conversations.create(session, channel="harness")).id

    async def end(handoff):
        try:
            async with sessions.begin() as session:
                conversation = await conversations.get_active(session, cid)
                if handoff:
                    await handoffs.create(
                        session,
                        conversation,
                        issue_summary="Help",
                        trigger_reason=HandoffTrigger.CITIZEN_REQUEST,
                    )
                await conversations.end(
                    session, conversation, status="handed_off" if handoff else "ended"
                )
                return True
        except conversations.ConversationClosed:
            return False

    assert sum(await asyncio.gather(end(False), end(True))) == 1
    async with sessions() as session:
        conversation = await session.get(Conversation, cid)
        count = (
            await session.execute(select(func.count()).select_from(HandoffRequest))
        ).scalar_one()
        assert count == (1 if conversation.status == "handed_off" else 0)
        assert conversation.ended_at is not None


async def test_concurrent_operator_transition_cannot_reopen_resolved_handoff(postgres):
    _, sessions, _ = postgres
    async with sessions.begin() as session:
        conversation = await conversations.create(session, channel="harness")
        handoff = await handoffs.create(
            session,
            conversation,
            issue_summary="Help",
            trigger_reason=HandoffTrigger.CITIZEN_REQUEST,
        )
        hid = handoff.id

    async def transition(status):
        try:
            async with sessions.begin() as session:
                handoff = await handoffs.get(session, hid)
                await handoffs.update_status(session, handoff, status)
        except handoffs.InvalidTransition:
            pass

    await asyncio.gather(transition(HandoffStatus.RESOLVED), transition(HandoffStatus.CONTACTED))
    async with sessions() as session:
        assert (await session.get(HandoffRequest, hid)).status == "resolved"
