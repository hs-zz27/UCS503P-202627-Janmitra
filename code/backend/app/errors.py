"""Domain exception → HTTP status mapping.

Kept in one place so the modules can raise meaningful exceptions without importing FastAPI,
and so an unhandled domain error can never leak as a 500 with a stack trace.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.adapters.model.base import ModelOutputInvalid, ModelUnavailable
from app.context import get_request_id
from app.modules.catalogue.service import ServiceNotFound
from app.modules.conversation.service import ConversationClosed, ConversationNotFound
from app.modules.eligibility.engine import AnswerValidationError
from app.modules.handoff.service import HandoffNotFound, InvalidTransition

logger = logging.getLogger("janmitra.errors")


def _problem(status_code: int, message: str, **extra) -> JSONResponse:
    body = {"detail": message, "request_id": get_request_id()}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConversationNotFound)
    async def _conversation_not_found(request: Request, exc: ConversationNotFound):
        return _problem(status.HTTP_404_NOT_FOUND, f"no conversation {exc.args[0]!r}")

    @app.exception_handler(ConversationClosed)
    async def _conversation_closed(request: Request, exc: ConversationClosed):
        return _problem(status.HTTP_409_CONFLICT, "conversation has already ended")

    @app.exception_handler(ServiceNotFound)
    async def _service_not_found(request: Request, exc: ServiceNotFound):
        return _problem(status.HTTP_404_NOT_FOUND, f"no published service {exc.args[0]!r}")

    @app.exception_handler(HandoffNotFound)
    async def _handoff_not_found(request: Request, exc: HandoffNotFound):
        return _problem(status.HTTP_404_NOT_FOUND, "no such handoff")

    @app.exception_handler(InvalidTransition)
    async def _invalid_transition(request: Request, exc: InvalidTransition):
        return _problem(status.HTTP_409_CONFLICT, str(exc))

    @app.exception_handler(AnswerValidationError)
    async def _answer_invalid(request: Request, exc: AnswerValidationError):
        return _problem(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "answers did not validate", errors=exc.errors
        )

    @app.exception_handler(ModelUnavailable)
    async def _model_unavailable(request: Request, exc: ModelUnavailable):
        # Recoverable by contract (context.md §13): the caller retries or degrades, and no
        # handoff or service record has been written.
        logger.warning("model unavailable", extra={"error": str(exc)})
        return _problem(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "the language model is unavailable; the request was not applied",
        )

    @app.exception_handler(ModelOutputInvalid)
    async def _model_invalid(request: Request, exc: ModelOutputInvalid):
        logger.warning("model output rejected by schema validation", extra={"error": str(exc)})
        return _problem(
            status.HTTP_502_BAD_GATEWAY, "model output failed schema validation and was discarded"
        )
