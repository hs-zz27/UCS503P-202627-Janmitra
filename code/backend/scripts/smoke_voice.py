"""Opt-in live voice smoke test. Uses configured providers and a supplied PCM WAV.

Run from code/backend with the API, frontend, and worker already running:
  .venv/Scripts/python scripts/smoke_voice.py ../../.janmitra/voice-input.wav
This creates one test call and retains its synthetic transcript in the local database.
"""

import argparse
import asyncio
import base64
import json
import wave
from pathlib import Path
from time import perf_counter

import httpx
from livekit import rtc
from sqlalchemy import select

from app.db import dispose_engine, get_sessionmaker
from app.models import Conversation
from app.modules.conversation.service import events


async def run(audio: Path, frontend: str, access_code: str) -> None:
    started_at = perf_counter()
    speech_end_at = None
    first_response_at = None
    ready_at = None
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            frontend + "/api/livekit/token",
            json={},
            headers={"Origin": frontend, "X-Harness-Access-Code": access_code},
        )
        response.raise_for_status()
        credentials = response.json()
    token = credentials["participant_token"]
    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    room_name = claims["video"]["room"]
    room = rtc.Room()
    agent_joined = asyncio.Event()
    audio_received = asyncio.Event()
    worker_ready = asyncio.Event()
    readers: set[asyncio.Task] = set()
    received_frames = 0

    async def listen(track):
        nonlocal received_frames, first_response_at
        stream = rtc.AudioStream(track)
        try:
            async for item in stream:
                if any(item.frame.data):
                    received_frames += 1
                    if speech_end_at is not None and first_response_at is None:
                        first_response_at = perf_counter()
                    audio_received.set()
        finally:
            await stream.aclose()

    @room.on("participant_connected")
    def participant_connected(participant):
        agent_joined.set()

    @room.on("data_received")
    def data_received(packet):
        nonlocal ready_at
        if packet.topic != "janmitra.voice":
            return
        try:
            message = json.loads(packet.data)
        except (ValueError, TypeError):
            return
        if message.get("type") == "ready":
            ready_at = perf_counter()
            worker_ready.set()
        elif message.get("type") == "error":
            print(json.dumps({"voice_error": message.get("message")}), flush=True)

    @room.on("track_subscribed")
    def track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            task = asyncio.create_task(listen(track))
            readers.add(task)
            task.add_done_callback(readers.discard)

    source = None
    silence_task = None
    try:
        await room.connect(credentials["server_url"], token)
        if room.remote_participants:
            agent_joined.set()
        await asyncio.wait_for(agent_joined.wait(), timeout=30)
        with wave.open(str(audio), "rb") as wav:
            if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                raise ValueError("provide a mono 16-bit PCM WAV")
            rate = wav.getframerate()
            source = rtc.AudioSource(rate, 1)
            track = rtc.LocalAudioTrack.create_audio_track("smoke-microphone", source)
            await room.local_participant.publish_track(
                track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )
            await asyncio.wait_for(worker_ready.wait(), timeout=30)
            # A short quiet lead-in establishes the stream without a five-second sleep.
            for _ in range(50):
                await source.capture_frame(
                    rtc.AudioFrame(bytes(rate // 50 * 2), rate, 1, rate // 50)
                )
            while data := wav.readframes(rate // 50):
                await source.capture_frame(rtc.AudioFrame(data, rate, 1, len(data) // 2))
            await source.wait_for_playout()
            speech_end_at = perf_counter()
            for _ in range(100):
                await source.capture_frame(
                    rtc.AudioFrame(bytes(rate // 50 * 2), rate, 1, rate // 50)
                )
            await source.wait_for_playout()

            async def send_silence():
                while True:
                    await source.capture_frame(
                        rtc.AudioFrame(bytes(rate // 50 * 2), rate, 1, rate // 50)
                    )

            silence_task = asyncio.create_task(send_silence())
        await asyncio.wait_for(audio_received.wait(), timeout=30)
        # A greeting alone does not establish successful guidance. Wait for the tool event.
        cid = None
        found_tool = False
        for _ in range(30):
            async with get_sessionmaker()() as session:
                call = (
                    await session.execute(
                        select(Conversation).where(Conversation.livekit_room == room_name)
                    )
                ).scalar_one_or_none()
                if call is not None:
                    cid = call.id
                    found_tool = any(
                        e.kind == "tool.find_service" for e in await events(session, cid)
                    )
            if found_tool:
                break
            await asyncio.sleep(1)
        if not found_tool:
            raise RuntimeError("agent audio arrived but no scheme lookup was persisted")
        # Wait for the answer after the tool, rather than counting a greeting as success.
        answered = False
        for _ in range(90):
            async with get_sessionmaker()() as session:
                recorded = await events(session, cid)
            tool_seen = False
            for event in recorded:
                if event.kind == "tool.find_service":
                    tool_seen = True
                elif tool_seen and event.kind == "transcript.assistant":
                    answered = len(event.payload.get("text", "").strip()) >= 80
            if answered:
                break
            await asyncio.sleep(1)
        if not answered:
            raise RuntimeError("no completed guidance response was persisted after the tool")
    finally:
        if silence_task is not None:
            silence_task.cancel()
            await asyncio.gather(silence_task, return_exceptions=True)
        await room.disconnect()
        for task in tuple(readers):
            task.cancel()
        await asyncio.gather(*tuple(readers), return_exceptions=True)
        if source is not None:
            await source.aclose()

    closed = False
    for _ in range(15):
        async with get_sessionmaker()() as session:
            call = await session.get(Conversation, cid)
            closed = call is not None and call.ended_at is not None
            recorded = await events(session, cid)
        if closed:
            break
        await asyncio.sleep(1)
    print(
        json.dumps(
            {
                "agent_dispatched": True,
                "received_audio_frames": received_frames,
                "scheme_tool_called": found_tool,
                "guidance_response_recorded": answered,
                "ready_ms": round((ready_at - started_at) * 1000) if ready_at else None,
                "speech_end_to_first_audio_ms": (
                    round((first_response_at - speech_end_at) * 1000)
                    if first_response_at is not None and speech_end_at is not None
                    else None
                ),
                "retrieval_ms": [
                    e.payload.get("retrieval_elapsed_ms")
                    for e in recorded
                    if e.kind == "tool.find_service"
                ],
                "conversation_closed": closed,
                "event_kinds": [e.kind for e in recorded],
            }
        )
    )
    if not closed:
        raise RuntimeError("voice call disconnected without closing its backend conversation")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--frontend", default="http://127.0.0.1:3000")
    parser.add_argument("--access-code", default="")
    args = parser.parse_args()
    try:
        await run(args.audio, args.frontend, args.access_code)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
