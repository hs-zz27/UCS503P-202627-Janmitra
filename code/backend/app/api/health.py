"""Liveness and readiness.

Split deliberately: the load balancer must not pull a replica out because Postgres is
briefly busy, and the staging deploy must not go green before the database is reachable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Liveness: is the process up. No dependencies touched on purpose."""
    return {"status": "ok", "env": settings.env, "model_adapter": settings.model_adapter.value}


@router.get("/readyz")
async def readyz(
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Readiness: can this replica actually serve a request."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "error", "detail": str(exc)[:200]}
    return {"status": "ready", "database": "ok"}
