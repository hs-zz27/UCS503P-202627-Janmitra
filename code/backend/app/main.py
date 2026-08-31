"""Janmitra backend — a modular monolith, not microservices (context.md §9).

Six modules in one FastAPI application: conversation, catalogue, eligibility, ingestion,
handoff and audit. It stays horizontally replicable because no required state lives in
process memory — conversations, records and audit rows are all in Postgres.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, tools
from app.config import get_settings
from app.db import dispose_engine
from app.errors import register_exception_handlers
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.modules.audit.router import router as audit_router
from app.modules.catalogue.router import router as catalogue_router
from app.modules.conversation.router import router as conversation_router
from app.modules.handoff.router import router as handoff_router

logger = logging.getLogger("janmitra")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "starting janmitra backend",
        extra={"env": settings.env, "model_adapter": settings.model_adapter.value},
    )
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Janmitra backend",
        version="0.1.0",
        summary="Voice-first civic scheme guidance — orchestrator API",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(conversation_router)
    app.include_router(tools.router)
    app.include_router(catalogue_router)
    app.include_router(handoff_router)
    app.include_router(audit_router)

    configure_logging(settings.log_level)
    return app


app = create_app()
