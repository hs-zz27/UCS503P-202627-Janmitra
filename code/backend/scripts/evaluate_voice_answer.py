"""Opt-in Gemini 3.1 native-audio evaluation with current prompt and local RAG.

Uses real provider quota and saves the supplied audio's transcript in the chosen report.
Provide synthetic mono 16-bit 16 kHz PCM WAV files, one per conversation turn.
This isolates answer quality; use the browser for transport, interruption and handoff tests.
"""

import argparse
import asyncio
import json
import wave
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from app.api.tools import RETRIEVAL_GUIDANCE
from app.config import get_settings
from app.modules.catalogue.references import compact_records, load_reference_records, ranked_records
from app.schemas.service_record import ServiceCategory
from app.voice.prompt import SYSTEM_PROMPT

FIXTURES = Path(__file__).with_name("fixtures") / "voice-evaluation.json"


def pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("Evaluation WAV must be mono, 16-bit PCM, 16000 Hz")
        return audio.readframes(audio.getnframes())


async def evaluate(args, fixture: dict) -> dict:
    settings = get_settings()
    thinking_level = args.thinking_level or settings.gemini_live_thinking_level
    if not settings.gemini_api_key:
        raise ValueError("JANMITRA_GEMINI_API_KEY is required")
    inputs = [pcm(path) for path in args.audio]
    records = load_reference_records(str(settings.catalogue_data_dir.resolve()))
    report = {
        "scenario": fixture["id"],
        "model": settings.gemini_live_model,
        "thinking_level": thinking_level,
        "scope": "Native audio with current prompt and local retrieval; no LiveKit or HTTP",
        "expected_behavior": fixture["expected_behavior"],
        "forbidden_claims": fixture["forbidden_claims"],
        "quality_review": "Manual semantic review required; audio alone is not a quality pass",
        "turns": [],
        "completed": False,
    }
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_PROMPT,
        speech_config={
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": settings.gemini_live_voice,
                }
            }
        },
        thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
        input_audio_transcription={},
        output_audio_transcription={},
        tools=[
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="find_service",
                        description=(
                            "Call before answering any public-support request, including "
                            "vague or multiple needs. Retrieve benefits, documents and steps. "
                            "Use the citizen's situation; no scheme name is needed. "
                            "Leave category unset for broad or mixed needs."
                        ),
                        parameters={
                            "type": "OBJECT",
                            "properties": {
                                "query": {"type": "STRING"},
                                "language": {"type": "STRING"},
                                "category": {
                                    "type": "STRING",
                                    "enum": [c.value for c in ServiceCategory],
                                },
                                "limit": {"type": "INTEGER"},
                            },
                            "required": ["query"],
                        },
                    )
                ]
            )
        ],
    )
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options={"api_version": "v1alpha", "timeout": 15000},
    )
    try:
        async with client.aio.live.connect(model=settings.gemini_live_model, config=config) as live:
            for data in inputs:
                turn = {"citizen": "", "answer": "", "lookups": [], "audio_chunks": 0}
                report["turns"].append(turn)
                timing = {"input_end_at": None}

                async def send(data=data, timing=timing):
                    for position in range(0, len(data), 640):
                        await live.send_realtime_input(
                            audio=types.Blob(
                                data=data[position : position + 640],
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                        await asyncio.sleep(0.02)
                    timing["input_end_at"] = perf_counter()
                    for _ in range(75):
                        await live.send_realtime_input(
                            audio=types.Blob(data=bytes(640), mime_type="audio/pcm;rate=16000")
                        )
                        await asyncio.sleep(0.02)
                    await live.send_realtime_input(audio_stream_end=True)

                async def receive(turn=turn, timing=timing):
                    while True:
                        async for response in live.receive():
                            if response.data:
                                turn["audio_chunks"] += 1
                                input_end_at = timing["input_end_at"]
                                if (
                                    input_end_at is not None
                                    and "first_audio_after_input_ms" not in turn
                                ):
                                    turn["first_audio_after_input_ms"] = round(
                                        (perf_counter() - input_end_at) * 1000
                                    )
                            if response.tool_call:
                                replies = []
                                for call in response.tool_call.function_calls:
                                    arguments = call.args or {}
                                    category = arguments.get("category")
                                    selected = ranked_records(
                                        records,
                                        arguments.get("query", ""),
                                        category=ServiceCategory(category) if category else None,
                                        limit=max(1, min(int(arguments.get("limit", 3)), 3)),
                                    )
                                    turn["lookups"].append(
                                        {
                                            "query": arguments.get("query"),
                                            "slugs": [record.slug for record in selected],
                                        }
                                    )
                                    replies.append(
                                        types.FunctionResponse(
                                            id=call.id,
                                            name=call.name,
                                            response={
                                                "matches": [],
                                                "reference_context": compact_records(
                                                    tuple(selected),
                                                    language=arguments.get("language", "en"),
                                                ),
                                                "verification_state": "unverified",
                                                "knowledge_fallback_allowed": True,
                                                "response_guidance": RETRIEVAL_GUIDANCE,
                                            },
                                        )
                                    )
                                await live.send_tool_response(function_responses=replies)
                            content = response.server_content
                            if content:
                                if content.input_transcription:
                                    turn["citizen"] += content.input_transcription.text or ""
                                if content.output_transcription:
                                    turn["answer"] += content.output_transcription.text or ""
                                if (
                                    content.turn_complete
                                    and not response.tool_call
                                    and turn["audio_chunks"]
                                    and len(turn["answer"].strip()) > 60
                                ):
                                    return

                task = asyncio.create_task(send())
                try:
                    await asyncio.wait_for(receive(), timeout=90)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        report["completed"] = True
    except Exception as error:
        report["error_type"] = type(error).__name__
    finally:
        await client.aio.aclose()
        client.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List scenarios without provider calls")
    parser.add_argument("--scenario")
    parser.add_argument("--thinking-level", choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--audio", type=Path, nargs="+")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    if args.list:
        for fixture in fixtures["scenarios"]:
            print(f"{fixture['id']}: {fixture['turns'][0]}")
        return
    scenario = next((s for s in fixtures["scenarios"] if s["id"] == args.scenario), None)
    if scenario is None or not args.audio or args.report is None:
        parser.error("Provide a valid --scenario, --audio WAV(s), and --report output path")
    if len(args.audio) > len(scenario["turns"]):
        parser.error("There are more audio files than turns in this scenario")
    result = asyncio.run(evaluate(args, scenario))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Windows redirected consoles may use cp1252; the UTF-8 report preserves speech.
    print(json.dumps(result, ensure_ascii=True), flush=True)
    if not result["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
