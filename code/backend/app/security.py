"""Role check for the dashboard and voice-worker routes.

Three seeded demo accounts behind a shared header, deliberately: the course project is not
buying anything by building registration, OAuth, password reset and org management
(context.md §11.6). The unauthorised-action tests in §14 test *this*, so it stays a real
gate rather than a comment.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    #: The LiveKit voice worker calling tools on a citizen's behalf.
    VOICE = "voice"


def _resolve(api_key: str | None, settings: Settings) -> Role | None:
    if not api_key:
        return None
    # Compared in a fixed order; keys are distinct per role by construction.
    for role, expected in (
        (Role.ADMIN, settings.admin_api_key),
        (Role.OPERATOR, settings.operator_api_key),
        (Role.VOICE, settings.voice_api_key),
    ):
        if expected and api_key == expected:
            return role
    return None


async def current_role(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> Role:
    role = _resolve(x_api_key, settings)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown or missing API key"
        )
    return role


def require(*allowed: Role):
    """Dependency factory: 403 unless the caller holds one of `allowed`."""

    async def _dependency(role: Role = Depends(current_role)) -> Role:
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {role.value!r} may not perform this action",
            )
        return role

    return _dependency
