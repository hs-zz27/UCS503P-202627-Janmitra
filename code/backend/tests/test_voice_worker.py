import asyncio
from types import SimpleNamespace

import pytest

from app.voice import worker
from app.voice.client import BackendToolError


@pytest.fixture
def voice_runtime(monkeypatch):
    state = SimpleNamespace(
        closed=0,
        ended=0,
        events=[],
        create_error=False,
        model_error=False,
        mutable=False,
        model_name="fake",
        greetings=0,
        notifications=[],
        shutdowns=0,
        thinking_level="low",
    )

    class Client:
        def __init__(self, **kwargs):
            pass

        async def create_conversation(self, **kwargs):
            if state.create_error:
                raise BackendToolError(503, "unavailable")
            return {"id": "conversation"}

        async def append_event(self, *args, **kwargs):
            await asyncio.sleep(0)
            state.events.append(kwargs)

        async def end_conversation(self, *args):
            state.ended += 1

        async def close(self):
            state.closed += 1

    class Session:
        def __init__(self, **kwargs):
            self.handlers = {}
            state.session = self

        def on(self, name):
            def register(handler):
                self.handlers[name] = handler
                return handler

            return register

        async def start(self, **kwargs):
            pass

        async def generate_reply(self, **kwargs):
            state.greetings += 1

        def shutdown(self, **kwargs):
            assert kwargs == {"drain": False}
            state.shutdowns += 1

    class Context:
        job = SimpleNamespace(metadata="[]")

        class Participant:
            async def publish_data(self, data, **kwargs):
                import json

                state.notifications.append((json.loads(data), kwargs))

        room = SimpleNamespace(name="room", local_participant=Participant())

        async def connect(self):
            pass

        def add_shutdown_callback(self, callback):
            self.shutdown = callback

    def model(**kwargs):
        state.model_options = kwargs
        if state.model_error:
            raise RuntimeError("model construction failed")
        return SimpleNamespace(capabilities=SimpleNamespace(mutable_chat_context=state.mutable))

    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="fake",
            backend_base_url="http://test",
            voice_api_key="fake",
            gemini_live_model=state.model_name,
            gemini_live_voice="fake",
            gemini_live_thinking_level=state.thinking_level,
        ),
    )
    monkeypatch.setattr(worker, "BackendToolClient", Client)
    monkeypatch.setattr(worker, "AgentSession", Session)
    monkeypatch.setattr(worker, "JanmitraVoiceAgent", lambda *args: object())
    monkeypatch.setattr(worker.google.realtime, "RealtimeModel", model)
    return state, Context()


async def test_close_drains_transcripts_and_finalizes_once(voice_runtime):
    state, context = voice_runtime
    await worker.entrypoint(context)
    state.session.handlers["conversation_item_added"](
        SimpleNamespace(
            item=worker.llm.ChatMessage(role="user", content=["Hello"]),
        )
    )
    state.session.handlers["close"](None)
    await asyncio.wait_for(asyncio.gather(context.shutdown(), context.shutdown()), timeout=1)
    assert len([event for event in state.events if event["kind"] == "transcript.user"]) == 1
    assert state.ended == 1
    assert state.closed == 1


async def test_metrics_and_errors_are_delivered_without_sensitive_details(voice_runtime):
    state, context = voice_runtime
    await worker.entrypoint(context)
    state.session.handlers["error"](
        SimpleNamespace(error=SimpleNamespace(recoverable=True, message="secret-provider-key"))
    )
    assert "metrics_collected" not in state.session.handlers
    state.session.handlers["conversation_item_added"](
        SimpleNamespace(
            item=worker.llm.ChatMessage(
                role="assistant",
                content=["An answer"],
                metrics={
                    "llm_node_ttft": 0.6,
                    "e2e_latency": 1.2,
                    "provider_request_ids": ["private-provider-id"],
                },
            )
        )
    )
    state.session.handlers["user_state_changed"](
        SimpleNamespace(old_state="speaking", new_state="listening")
    )
    state.session.handlers["agent_state_changed"](SimpleNamespace(new_state="speaking"))
    await context.shutdown()
    errors = [payload for payload, _ in state.notifications if payload["type"] == "error"]
    assert errors[0]["recoverable"] is True
    assert "secret-provider-key" not in str(state.notifications)
    metrics = [event for event in state.events if event["kind"] == "voice.metrics"]
    assert metrics[0]["payload"]["ttft_seconds"] == 0.6
    assert "private-provider-id" not in str(metrics)
    assert any(event["kind"] == "voice.turn_latency" for event in state.events)
    assert all(options["topic"] == "janmitra.voice" for _, options in state.notifications)


@pytest.mark.parametrize(
    "detail",
    [
        "1011 Resource has been exhausted (e.g. check quota)",
        "RESOURCE_EXHAUSTED",
    ],
)
async def test_quota_error_is_safe_and_actionable(voice_runtime, detail):
    state, context = voice_runtime
    await worker.entrypoint(context)
    state.session.handlers["error"](
        SimpleNamespace(
            error=SimpleNamespace(recoverable=True, message=detail + " private-api-key")
        )
    )
    await context.shutdown()
    error = next(payload for payload, _ in state.notifications if payload["type"] == "error")
    assert error["code"] == "usage_limit"
    assert error["recoverable"] is False
    assert "Gemini 3.1 Live is currently at its usage limit" in error["message"]
    assert "private-api-key" not in str(state.notifications)
    assert state.shutdowns == 1


async def test_recovery_is_bounded_until_audio_actually_resumes(voice_runtime):
    state, context = voice_runtime
    await worker.entrypoint(context)
    error = SimpleNamespace(error=SimpleNamespace(recoverable=True, message="1011 Internal error"))
    for _ in range(3):
        state.session.handlers["error"](error)
        state.session.handlers["agent_state_changed"](SimpleNamespace(new_state="listening"))
    await context.shutdown()
    errors = [payload for payload, _ in state.notifications if payload["type"] == "error"]
    assert "repeat your last request" in errors[0]["message"]
    assert errors[-1]["code"] == "recovery_failed"
    assert errors[-1]["recoverable"] is False
    assert state.shutdowns == 1


async def test_resumed_audio_resets_failure_count_and_announces_recovery(voice_runtime):
    state, context = voice_runtime
    await worker.entrypoint(context)
    error = SimpleNamespace(error=SimpleNamespace(recoverable=True, message="1011 Internal error"))
    for _ in range(2):
        state.session.handlers["error"](error)
    state.session.handlers["agent_state_changed"](SimpleNamespace(new_state="speaking"))
    state.session.handlers["error"](error)
    await context.shutdown()
    assert state.shutdowns == 0
    assert any(
        payload == {"type": "ready", "state": "speaking"} for payload, _ in state.notifications
    )


@pytest.mark.parametrize("failure", ["create_error", "model_error"])
async def test_startup_failures_release_client(voice_runtime, failure):
    state, context = voice_runtime
    setattr(state, failure, True)
    with pytest.raises((BackendToolError, RuntimeError)):
        await worker.entrypoint(context)
    await context.shutdown()
    assert state.closed == 1
    assert state.ended == (0 if failure == "create_error" else 1)


@pytest.mark.parametrize("thinking_level", ["minimal", "low", "medium", "high"])
async def test_gemini_31_uses_configured_thinking_and_waits_for_citizen(
    voice_runtime, thinking_level
):
    state, context = voice_runtime
    state.model_name = "gemini-3.1-flash-live-preview"
    state.mutable = True
    state.thinking_level = thinking_level
    await worker.entrypoint(context)
    assert state.greetings == 0
    assert state.model_options["thinking_config"].thinking_level.value.lower() == thinking_level
    vad = state.model_options["realtime_input_config"].automatic_activity_detection
    assert vad.silence_duration_ms == 500
    await context.shutdown()
    assert state.closed == 1
