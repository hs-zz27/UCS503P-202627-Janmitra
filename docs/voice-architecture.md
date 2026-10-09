# Browser voice architecture

Janmitra is a rural companion for practical public-service guidance. The browser sends
microphone audio over WebRTC to LiveKit; a worker maintains one native audio session
with `gemini-3.1-flash-live-preview`. The same model explains retrieved facts and streams
spoken audio back. There is no separate STT/TTS pipeline, alternate voice model, or
telephone integration.

```text
Browser microphone/speaker <-> LiveKit <-> Gemini 3.1 Live worker
                                              |
                                         HTTP tools
                                              |
                    FastAPI: retrieval, eligibility, documents, handoff queue
```

## Retrieval contract

The voice client sends `response_mode="context"` to `find_service`. The API ranks a
combined pool of published facts and pending references and returns at most three
records. A published version supersedes a draft with the same slug. `context_order`
preserves ranking across `matches` and `reference_context`, so a published match for
one need does not hide pending material for another.

Published matches retain citations and service versions. Pending references include
citations, first actions, application steps and document names, with
`publication_state="unpublished_reference"`. Top-level `verification_state` is
`verified`, `unverified`, or `mixed`; `answer_basis` describes the available context.
Only explicitly reviewed, published records support deterministic eligibility and
verified document results. The bundled 18 records remain pending human review.

Gemini Live answers directly from this context without an intermediate text-model
answer. Existing HTTP clients retain the `response_mode="prepared_answer"`
compatibility path. Backend ingestion and optional handoff summaries use a separate
text adapter. A handoff queues an operator request; it does not connect a phone call.

## Help starts with the person's need

People may describe debt pressure, crop loss, housing damage, food shortage, illness,
job loss, or several needs without knowing a scheme name. Give useful first help,
retain context across short follow-ups, and ask one understandable question at a time.
Match the citizen's latest spoken language and use familiar words and short steps.
Immediate danger and urgent medical symptoms take priority over forms or retrieval.

Lead with supported benefits, criteria, documents or application steps. Qualify actual
uncertainty instead of repeating blanket disclaimers. Preserve material conditions:
credit is repayable and does not waive existing debt; housing construction support is
not automatic roof repair; existing crop damage needs applicable prior insurance.
Do not invent amounts, deadlines, approval, legal outcomes or completed actions. Never
request an OTP, PIN, password, full bank account or Aadhaar number in conversation.

The catalogue does not cover every local programme or remedy. Missing context is not
proof that no help exists: give safe practical orientation and offer human help where
appropriate. The official [ERSS portal](https://112.gov.in/) identifies 112 for
emergencies. [NALSA's FAQ](https://nalsa.gov.in/faqs/) lists 15100 and District Legal
Services Authorities for legal-assistance orientation; eligibility is assessed by the
relevant institution. Janmitra cannot promise dispatch, representation or a result.

## Audio lifecycle and timing

Gemini server VAD uses high start/end sensitivity, 100ms prefix padding and 500ms
silence endpointing. `JANMITRA_GEMINI_LIVE_THINKING_LEVEL` defaults to `low` and accepts
`minimal`, `low`, `medium` or `high` within the same native session. The citizen starts
speaking first; the model's first answer briefly discloses that Janmitra is AI.

Transcript writes run asynchronously. Cleanup drains pending writes and closes the
conversation once. HTTP tools use a 20-second read timeout and a 3-second connect
timeout. Verified TLS setup runs outside the audio event loop and is reused.

Persisted metrics distinguish:

- `voice.startup.duration_ms`: conversation creation and session startup; excludes
  initial room connection and HTTP client creation.
- `voice.metrics`: available assistant-turn `ttft_seconds`, `e2e_latency_seconds` and
  `playback_latency_seconds`.
- `voice.turn_latency.response_latency_ms`: SDK speech-end to speaking state; excludes
  browser playout.
- `retrieval_elapsed_ms` and worker HTTP duration: backend lookup and transport time.

Quota errors close immediately. Recoverable errors ask the citizen to repeat; three
failures without resumed agent speech close the session. Actual speech clears the
recovery state; listening alone does not prove completed guidance. Browser
`janmitra.voice` messages communicate readiness, status and safe errors.

## Evaluation

`scripts/fixtures/voice-evaluation.json` contains sixteen meaning-based scenarios for
mixed needs, threats, food, health, employment, pension, education, fraud, family
distress, low literacy, multilingual speech and follow-up memory. Score useful help,
one-question behavior, grounding, oral clarity, multi-intent handling and privacy.
Unsupported material claims and fabricated actions are hard failures. Fixtures are
an evaluation guide, not evidence that every scenario has passed.

`scripts/evaluate_voice_answer.py --list` lists cases. Select `--scenario`, supply one
or more `--audio` mono 16-bit 16 kHz WAV files, and choose a `--report`. This opt-in test
uses real Gemini quota with the current prompt and local retrieval, without LiveKit
or HTTP. Reports require human semantic review. Use `scripts/smoke_voice.py` and the
browser separately for transport, interruption, persisted lookup, completed guidance
and conversation closure; see [Run and test](run-and-test.md).

Measure cold startup separately from warm turns. Compare repeated questions and report
sample count, median and slow-tail timing. Backend lookup time and isolated native
first-audio time are not browser end-to-end latency.

## Known limits

Grounded browser calls and isolated answers have completed, but integrated calls still
intermittently fail with 1011 errors. A direct SDK call can succeed; a solely provider-side
cause is not established. Key replacement did not eliminate the failures, and no
rotation pool is implemented or demonstrated as a remedy.

Complex mixed-need answers remain inconsistent. Native tests have missed retrieval,
matched the wrong spoken language, asked multiple questions, or omitted material loan
conditions. Other tests preserved crop-insurance and construction conditions. Prompt
and contract tests passing does not resolve these live quality gaps. The full scenario
set and regional dialects have not been certified; continued human evaluation is needed.
