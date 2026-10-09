from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import ssl
from functools import lru_cache
from time import perf_counter

import certifi
from google.genai import types
from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, llm
from livekit.plugins import google

from app.config import get_settings
from app.voice.agent import JanmitraVoiceAgent
from app.voice.client import BackendToolClient, BackendToolError

logger = logging.getLogger("janmitra.voice")


@lru_cache(maxsize=1)
def _tls_context() -> ssl.SSLContext:
    """Share verified TLS setup across SDK transports within a worker process."""
    return ssl.create_default_context(
        cafile=os.environ.get("SSL_CERT_FILE", certifi.where()),
        capath=os.environ.get("SSL_CERT_DIR"),
    )


def _message_text(message: llm.ChatMessage) -> str:
    text = getattr(message, "text_content", None)
    if text:
        return str(text).strip()
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(item for item in content if isinstance(item, str)).strip()
    return ""


def _role_value(role: object) -> str:
    return str(getattr(role, "value", role)).lower()


def _public_voice_error(error: object) -> dict:
    """Classify provider failures without forwarding provider details or credentials."""
    detail = f"{error} {getattr(error, 'message', '')}".casefold()
    if any(
        marker in detail
        for marker in ("resource_exhausted", "resource has been exhausted", "quota", "usage limit")
    ):
        return {
            "type": "error",
            "code": "usage_limit",
            "recoverable": False,
            "message": (
                "Gemini 3.1 Live is currently at its usage limit. "
                "Please try again later or check the Gemini project's quota and billing."
            ),
        }
    recoverable = bool(getattr(error, "recoverable", False))
    return {
        "type": "error",
        "code": "connection_error",
        "recoverable": recoverable,
        "message": (
            "The voice connection was interrupted. Reconnecting. "
            "Please wait a moment, then repeat your last request."
            if recoverable
            else "The voice connection failed. Please end this call and try again."
        ),
    }


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("JANMITRA_GEMINI_API_KEY is required by the voice worker")

    try:
        metadata = json.loads(getattr(ctx.job, "metadata", None) or "{}")
    except (json.JSONDecodeError, TypeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    channel = metadata.get("channel")
    if channel not in {"phone", "harness"}:
        channel = "harness"

    # Loading Windows' certificate store can block for over a second. Keep it
    # off the audio event loop so media setup and room events remain responsive.
    client = await asyncio.to_thread(
        BackendToolClient,
        base_url=settings.backend_base_url,
        api_key=settings.voice_api_key,
    )
    conversation_id: str | None = None
    pending: set[asyncio.Task] = set()
    cleanup_task: asyncio.Task | None = None
    citizen_finished_at: float | None = None
    startup_at = perf_counter()
    failures_without_response = 0

    def schedule(coro) -> None:
        task = asyncio.create_task(coro)
        pending.add(task)
        task.add_done_callback(pending.discard)

    async def record_message(role: str, text: str) -> None:
        if conversation_id is None:
            return
        try:
            await client.append_event(
                conversation_id,
                kind=f"transcript.{role}",
                payload={"text": text},
            )
        except BackendToolError:
            logger.exception("failed to persist transcript event")

    async def record_metric(kind: str, payload: dict) -> None:
        if conversation_id is None:
            return
        try:
            await client.append_event(conversation_id, kind=kind, payload=payload)
        except BackendToolError:
            logger.warning("failed to persist voice timing")

    async def notify(payload: dict) -> None:
        try:
            await ctx.room.local_participant.publish_data(
                json.dumps(payload).encode("utf-8"),
                reliable=True,
                topic="janmitra.voice",
            )
        except Exception:
            logger.debug("voice status could not be delivered", exc_info=True)

    async def cleanup() -> None:
        try:
            if pending:
                await asyncio.gather(*tuple(pending), return_exceptions=True)
            if conversation_id is not None:
                await client.end_conversation(conversation_id)
        except BackendToolError:
            logger.exception("failed to close backend conversation")
        finally:
            await client.close()

    def begin_cleanup() -> asyncio.Task:
        nonlocal cleanup_task
        if cleanup_task is None:
            cleanup_task = asyncio.create_task(cleanup())
        return cleanup_task

    async def finalize() -> None:
        await asyncio.shield(begin_cleanup())

    ctx.add_shutdown_callback(finalize)
    try:
        language = metadata.get("language")
        conversation = await client.create_conversation(
            room_name=ctx.room.name,
            channel=channel,
            language=language if isinstance(language, str) and len(language) <= 16 else None,
        )
        conversation_id = str(conversation["id"])
        assistant = JanmitraVoiceAgent(client, conversation_id)
        tls = await asyncio.to_thread(_tls_context)
        realtime_model = google.realtime.RealtimeModel(
            model=settings.gemini_live_model,
            api_key=settings.gemini_api_key,
            voice=settings.gemini_live_voice,
            temperature=0.2,
            http_options=types.HttpOptions(
                timeout=10000,
                client_args={"verify": tls},
                async_client_args={"verify": tls, "ssl": tls},
            ),
            thinking_config=types.ThinkingConfig(
                thinking_level=settings.gemini_live_thinking_level
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=100,
                    silence_duration_ms=500,
                ),
            ),
        )
        session = AgentSession(llm=realtime_model)

        @session.on("conversation_item_added")
        def capture(event) -> None:
            if cleanup_task is not None:
                return
            message = event.item
            if not isinstance(message, llm.ChatMessage):
                return
            role = _role_value(message.role)
            text = _message_text(message)
            if role in {"user", "assistant"} and text:
                schedule(record_message(role, text))
            # SDK 1.8+ attaches turn metrics to chat messages. Avoid the deprecated
            # metrics_collected hook, which also emits connection-only TTFT=-1.
            if role == "assistant":
                report = getattr(message, "metrics", {}) or {}
                payload = {"metric_type": "assistant_turn"}
                for source, target in (
                    ("llm_node_ttft", "ttft_seconds"),
                    ("e2e_latency", "e2e_latency_seconds"),
                    ("playback_latency", "playback_latency_seconds"),
                ):
                    value = report.get(source)
                    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
                        payload[target] = value
                if len(payload) > 1:
                    logger.info("voice turn timing %s", payload)
                    schedule(record_metric("voice.metrics", payload))

        @session.on("close")
        def on_close(event) -> None:
            begin_cleanup()

        @session.on("user_state_changed")
        def user_state(event) -> None:
            nonlocal citizen_finished_at
            if event.old_state == "speaking" and event.new_state != "speaking":
                citizen_finished_at = perf_counter()
            elif event.new_state == "speaking":
                citizen_finished_at = None

        @session.on("agent_state_changed")
        def agent_state(event) -> None:
            nonlocal citizen_finished_at, failures_without_response
            if cleanup_task is not None:
                return
            schedule(notify({"type": "status", "state": event.new_state}))
            if event.new_state == "speaking" and failures_without_response:
                failures_without_response = 0
                schedule(notify({"type": "ready", "state": "speaking"}))
            if event.new_state == "speaking" and citizen_finished_at is not None:
                latency = round((perf_counter() - citizen_finished_at) * 1000)
                citizen_finished_at = None
                logger.info("voice response_latency_ms=%s", latency)
                schedule(record_metric("voice.turn_latency", {"response_latency_ms": latency}))

        @session.on("error")
        def session_error(event) -> None:
            nonlocal failures_without_response
            if cleanup_task is not None:
                return
            payload = _public_voice_error(event.error)
            stop_session = payload["code"] == "usage_limit"
            if payload["recoverable"]:
                failures_without_response += 1
                # The SDK resets its retry count on any server packet, including
                # setup-only responses. Bound retries until actual speech resumes.
                if failures_without_response >= 3:
                    payload.update(
                        code="recovery_failed",
                        recoverable=False,
                        message=(
                            "Gemini 3.1 Live could not restore this call. "
                            "Please end the call and try again later."
                        ),
                    )
                    stop_session = True
            schedule(notify(payload))
            if stop_session:
                session.shutdown(drain=False)

        await session.start(room=ctx.room, agent=assistant)
        schedule(notify({"type": "ready", "state": "listening"}))
        schedule(
            record_metric(
                "voice.startup", {"duration_ms": round((perf_counter() - startup_at) * 1000)}
            )
        )
        # Use citizen-initiated native audio for Gemini 3.1. The prompt includes
        # greeting/disclosure in the first spoken response.
        if (
            realtime_model.capabilities.mutable_chat_context
            and "gemini-3.1" not in settings.gemini_live_model
        ):
            await session.generate_reply(
                instructions=(
                    "Greet the citizen briefly, disclose that you are Janmitra AI, "
                    "and ask how you can help."
                )
            )
        else:
            logger.info(
                "waiting for citizen speech to initiate the native-audio conversation",
                extra={"model": settings.gemini_live_model},
            )
    except BaseException:
        logger.exception("voice session failed")
        await finalize()
        raise


def run() -> None:
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("JANMITRA_LIVEKIT_URL", settings.livekit_url),
            ("JANMITRA_LIVEKIT_API_KEY", settings.livekit_api_key),
            ("JANMITRA_LIVEKIT_API_SECRET", settings.livekit_api_secret),
            ("JANMITRA_GEMINI_API_KEY", settings.gemini_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"voice worker is missing configuration: {', '.join(missing)}")
    os.environ["LIVEKIT_URL"] = settings.livekit_url
    os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret
    agents.cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint, agent_name=settings.livekit_agent_name)
    )
