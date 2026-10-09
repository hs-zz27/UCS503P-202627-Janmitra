"""HTTP tests use an isolated database and never load developer credentials/providers."""

from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.model.factory import get_model_adapter
from app.adapters.model.mock import MockModelAdapter
from app.config import Settings, get_settings
from app.db import Base, get_session
from app.main import create_app


@pytest.fixture
async def api():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def session_dependency():
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    settings = Settings(
        _env_file=None,
        model_adapter="mock",
        admin_api_key="test-admin",
        operator_api_key="test-operator",
        voice_api_key="test-voice",
        catalogue_data_dir=Path(__file__).parents[1] / "data",
    )
    app = create_app()
    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_model_adapter] = lambda: MockModelAdapter()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": "test-voice"},
        ) as client:
            yield client, app, sessions
    finally:
        await engine.dispose()
