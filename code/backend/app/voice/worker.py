from __future__ import annotations

import asyncio
import json
import logging
import os

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, llm
from livekit.plugins import google

from app.config import get_settings
from app.voice.agent import JanmitraVoiceAgent
from app.voice.client import BackendToolClient, BackendToolError

logger = logging.getLogger("janmitra.voice")


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


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("JANMITRA_GEMINI_API_KEY is required by the voice worker")

    try:
        metadata = json.loads(getattr(ctx.job, "metadata", None) or "{}")
    except json.JSONDecodeError:
        metadata = {}
    channel = metadata.get("channel")
    if channel not in {"phone", "harness"}:
        channel = "harness"

    client = BackendToolClient(
        base_url=settings.backend_base_url,
        api_key=settings.voice_api_key,
    )
    conversation = await client.create_conversation(
        room_name=ctx.room.name,
        channel=channel,
        language=metadata.get("language"),
    )
    conversation_id = str(conversation["id"])
    assistant = JanmitraVoiceAgent(client, conversation_id)
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=settings.gemini_live_model,
            api_key=settings.gemini_api_key,
            voice=settings.gemini_live_voice,
            temperature=0.2,
        )
    )
    pending: set[asyncio.Task] = set()
    finalized = False

    def schedule(coro) -> None:
        task = asyncio.create_task(coro)
        pending.add(task)
        task.add_done_callback(pending.discard)

    async def record_message(role: str, text: str) -> None:
        try:
            await client.append_event(
                conversation_id,
                kind=f"transcript.{role}",
                payload={"text": text},
            )
        except BackendToolError:
            logger.exception("failed to persist transcript event")

    async def finalize() -> None:
        nonlocal finalized
        if finalized:
            return
        finalized = True
        if pending:
            await asyncio.gather(*tuple(pending), return_exceptions=True)
        try:
            await client.end_conversation(conversation_id)
        except BackendToolError:
            logger.exception("failed to close backend conversation")
        finally:
            await client.close()

    @session.on("conversation_item_added")
    def capture(event) -> None:
        message = event.item
        if not isinstance(message, llm.ChatMessage):
            return
        role = _role_value(message.role)
        text = _message_text(message)
        if role in {"user", "assistant"} and text:
            schedule(record_message(role, text))

    @session.on("close")
    def on_close(event) -> None:
        schedule(finalize())

    ctx.add_shutdown_callback(finalize)
    try:
        await session.start(room=ctx.room, agent=assistant)
        await session.generate_reply(
            instructions=(
                "Greet the citizen briefly, disclose that you are Janmitra AI, "
                "and ask how you can help."
            )
        )
    except Exception:
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
    os.environ.setdefault("LIVEKIT_URL", settings.livekit_url)
    os.environ.setdefault("LIVEKIT_API_KEY", settings.livekit_api_key)
    os.environ.setdefault("LIVEKIT_API_SECRET", settings.livekit_api_secret)
    agents.cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint, agent_name=settings.livekit_agent_name)
    )
