"""Per-request context.

The request ID is generated once per HTTP request and then rides along into logs and
audit events. context.md §18.2: request IDs and timestamps exist from the very first
endpoint, because Time-to-Guidance cannot be reconstructed later if it was never logged.
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()
