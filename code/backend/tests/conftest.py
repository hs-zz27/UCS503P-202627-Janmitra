"""Shared test fixtures.

The suite runs against SQLite in memory rather than a Postgres container, which is what the
portable `JSON`/`JSONB` column variant in `app.db` was written for: `pytest` stays a
single command with no docker dependency, while production still gets JSONB.

Every test gets a fresh schema, a fresh `create_app()` and its own dependency overrides, so
no test can see another's rows, request IDs or role keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import ModelAdapterMode, Settings, get_settings
from app.db import Base, get_session
from app.main import create_app
from app.models import Conversation  # noqa: F401 — registers every table on Base.metadata
from app.schemas.service_record import (
    AnswerType,
    Citation,
    Comparison,
    Condition,
    Decision,
    EligibilityQuestion,
    LocalizedText,
    RequiredDocument,
    RuleSet,
    ServiceCategory,
    ServiceRecord,
    VerificationState,
)

ADMIN_KEY = "test-admin-key"
OPERATOR_KEY = "test-operator-key"
VOICE_KEY = "test-voice-key"

ADMIN = {"X-API-Key": ADMIN_KEY}
OPERATOR = {"X-API-Key": OPERATOR_KEY}
VOICE = {"X-API-Key": VOICE_KEY}


@pytest.fixture
def settings() -> Settings:
    """Test settings built explicitly, never from a developer's local `.env`."""
    return Settings(
        _env_file=None,
        env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        model_adapter=ModelAdapterMode.MOCK,
        admin_api_key=ADMIN_KEY,
        operator_api_key=OPERATOR_KEY,
        voice_api_key=VOICE_KEY,
    )


@pytest_asyncio.fixture
async def engine(tmp_path):
    # A file rather than `:memory:` so a fixture session and a request session are really
    # two connections to one database, the way they are against Postgres.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sessionmaker_(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(sessionmaker_) -> AsyncIterator[AsyncSession]:
    """A session for tests that drive the services directly, without HTTP."""
    async with sessionmaker_() as session:
        yield session


@pytest_asyncio.fixture
async def app(settings, sessionmaker_):
    application = create_app()

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with sessionmaker_() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_session] = _session_override
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


# --------------------------------------------------------------------------------------
# Record factories
# --------------------------------------------------------------------------------------


def verified_citation(**overrides) -> Citation:
    values = {
        "source_url": "https://example.gov.in/scheme",
        "source_title": "Official scheme page",
        "publisher": "Department of Example",
        "verified_on": "2026-01-15",
        "verification_state": VerificationState.VERIFIED,
        "verified_by": "reviewer-one",
    }
    values.update(overrides)
    return Citation(**values)


def loan_rule_set() -> RuleSet:
    """Age band, residency and an income ceiling that only applies to non-farmers."""
    return RuleSet(
        rule_set_id="mudra-rules",
        questions=[
            EligibilityQuestion(
                id="age", prompt=LocalizedText(en="How old are you?"), type=AnswerType.INTEGER,
                min=0, max=120,
            ),
            EligibilityQuestion(
                id="state",
                prompt=LocalizedText(en="Which state do you live in?", hi="Aap kis rajya mein"),
                type=AnswerType.ENUM,
                options=["punjab", "haryana", "other"],
            ),
            EligibilityQuestion(
                id="occupation",
                prompt=LocalizedText(en="What is your occupation?"),
                type=AnswerType.ENUM,
                options=["farmer", "trader", "other"],
            ),
            EligibilityQuestion(
                id="annual-income",
                prompt=LocalizedText(en="What is your annual income?"),
                type=AnswerType.NUMBER,
                unit="INR",
                min=0,
            ),
            EligibilityQuestion(
                id="has-bank-account",
                prompt=LocalizedText(en="Do you have a bank account?"),
                type=AnswerType.BOOLEAN,
            ),
        ],
        conditions=[
            Condition(
                id="adult",
                description=LocalizedText(en="Applicant is at least 18."),
                source_text="Applicants must be 18 years or older.",
                test=Comparison(var="age", op="gte", value=18),
            ),
            Condition(
                id="resident",
                description=LocalizedText(en="Applicant lives in a covered state."),
                test=Comparison(var="state", op="in", value=["punjab", "haryana"]),
            ),
            Condition(
                id="income-ceiling",
                description=LocalizedText(en="Non-farmers must earn under 300000."),
                applies_when=[Comparison(var="occupation", op="ne", value="farmer")],
                test=Comparison(var="annual-income", op="lte", value=300000),
            ),
            Condition(
                id="banked",
                description=LocalizedText(en="Applicant holds a bank account."),
                test=Comparison(var="has-bank-account", op="eq", value=True),
            ),
        ],
        decision=Decision(all_of=["adult", "resident", "income-ceiling", "banked"]),
    )


def loan_record(**overrides) -> ServiceRecord:
    values = {
        "slug": "mudra-loan",
        "name": LocalizedText(en="Mudra Loan", hi="Mudra Rin"),
        "aliases": ["micro credit", "small business loan"],
        "category": ServiceCategory.LOAN,
        "description": LocalizedText(
            en="Collateral-free working capital credit for micro enterprises."
        ),
        "benefit_summary": LocalizedText(en="Up to 10 lakh rupees of credit."),
        "eligibility_summary": LocalizedText(en="Adults running a micro enterprise."),
        "rule_set": loan_rule_set(),
        "documents": [
            RequiredDocument(id="aadhaar", name=LocalizedText(en="Aadhaar card", hi="Aadhaar")),
            RequiredDocument(
                id="land-record",
                name=LocalizedText(en="Land record"),
                notes=LocalizedText(en="Only for farmers."),
                required_when=Comparison(var="occupation", op="eq", value="farmer"),
            ),
        ],
        "citation": verified_citation(),
    }
    values.update(overrides)
    return ServiceRecord(**values)


def pension_record(**overrides) -> ServiceRecord:
    """A published scheme with no rule set — checklist and citation only."""
    values = {
        "slug": "old-age-pension",
        "name": LocalizedText(en="Old Age Pension"),
        "aliases": ["vridha pension"],
        "category": ServiceCategory.PENSION,
        "description": LocalizedText(en="Monthly pension support for senior citizens."),
        "documents": [
            RequiredDocument(id="age-proof", name=LocalizedText(en="Proof of age")),
        ],
        "citation": verified_citation(source_url="https://example.gov.in/pension"),
    }
    values.update(overrides)
    return ServiceRecord(**values)


@pytest_asyncio.fixture
async def published_loan(session):
    from app.modules.catalogue import service as catalogue

    published = await catalogue.publish(session, loan_record(), actor="admin")
    await session.commit()
    return published


@pytest_asyncio.fixture
async def published_pension(session):
    from app.modules.catalogue import service as catalogue

    published = await catalogue.publish(session, pension_record(), actor="admin")
    await session.commit()
    return published


@pytest_asyncio.fixture
async def conversation(session):
    from app.modules.conversation import service as conversations

    conversation = await conversations.create(
        session,
        channel="harness",
        language="en",
        connected_at=datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC),
    )
    await session.commit()
    return conversation
