# Run and test Janmitra

Use PowerShell from the repository root. Requirements: Docker Desktop (running),
Python 3.12+, and Node.js 22.13+ with npm. The API can run without provider credentials;
voice calls need matching LiveKit credentials and a Gemini API key.

## Configure once

```powershell
if (!(Test-Path code/backend/.env)) { Copy-Item code/backend/.env.example code/backend/.env }
if (!(Test-Path code/frontend/.env.local)) { Copy-Item code/frontend/.env.local.example code/frontend/.env.local }
py -3.12 -m venv code/backend/.venv
code/backend/.venv/Scripts/python.exe -m pip install -e 'code/backend[dev,voice,gemini]'
cd code/frontend
npm ci
cd ../..
```

Edit `code/backend/.env`: set `JANMITRA_GEMINI_API_KEY`, the three
`JANMITRA_LIVEKIT_*` credentials. `JANMITRA_MODEL_ADAPTER=real` enables backend
text tasks; use `mock` for offline API tests. Native voice retrieval returns compact
context directly to Gemini Live and does not need a second text-model answer.
Keep the default host database URL
on port 5438. Set the same LiveKit URL/key/secret in `code/frontend/.env.local`.
Set `JANMITRA_GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview`
for native audio-to-audio voice. Voice uses Gemini 3.1 only; no alternate model fallback.
`JANMITRA_GEMINI_LIVE_THINKING_LEVEL=low` is the default; supported levels are
`minimal`, `low`, `medium`, and `high`. Tune this within the same native voice model
to compare answer quality and latency, then restart the worker after changing it.
Both agent names must be `janmitra-agent`. Keep API role keys consistent between
Compose and the worker. Do not commit either environment file.

For a hosted browser harness, set `JANMITRA_HARNESS_ACCESS_CODE` and enter it in
the page. Production token issuance fails closed without a code. Set
`JANMITRA_HARNESS_ORIGIN=https://your-host` behind a reverse proxy. The token route
limits requests per process; a multi-instance deployment needs a shared limiter.

## Start

Terminal 1, repository root:

```powershell
docker compose --env-file code/backend/.env up --build -d
curl.exe http://127.0.0.1:8000/readyz
```

Readiness must return `{"status":"ready","database":"ok"}`. API docs are at
<http://127.0.0.1:8000/docs>. Migrations run automatically on container startup.

Terminal 2:

After updating code or bundled records, rebuild the API with the Terminal 1 command
and stop/restart the voice worker to load the changes. Existing processes and images
do not automatically pick up source or data edits.

```powershell
cd code/backend
.venv/Scripts/janmitra-voice.exe start
```

Terminal 3:

```powershell
cd code/frontend
npm run dev
```

Open <http://127.0.0.1:3000>, allow microphone access, and start a call. Ask about
crop insurance. The worker searches the published catalogue first; pending reference
chunks go directly to Gemini Live. Answers lead with useful source-backed facts and
qualify actual uncertainty; pending-review metadata remains intact without repeated
spoken boilerplate. A handoff queues a
request for an operator; it does not connect a telephone call. The current product uses
browser audio only. See [Voice architecture](voice-architecture.md) for the retrieval
contract, reference-agent comparison, and latency evaluation method.

Bundled service files remain pending review. Check their official sources in
`code/backend/data/REVIEW.md` before using `janmitra-seed data --confirm-reviewed
--actor "Your Name"`. Never attest review just to populate a demo.

## Automated checks

Backend (from `code/backend`):

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pip check
```

The default suite skips PostgreSQL concurrency tests when no test URL is set.
Run the full suite against the local Compose database:

```powershell
$env:JANMITRA_TEST_DATABASE_URL='postgresql+asyncpg://janmitra:janmitra@127.0.0.1:5438/janmitra'
.venv/Scripts/python.exe -m pytest -q
Remove-Item Env:JANMITRA_TEST_DATABASE_URL
```

These tests use temporary, uniquely named schemas, then remove only those schemas.
They exercise migrations, simultaneous publications/events, conversation closure,
and handoff transitions. Use a dedicated test database in shared environments.

Frontend (from `code/frontend`):

```powershell
npm test
npm run lint
npm run build
npm audit
```

Migration checks (repository root, with API running):

```powershell
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

Documentation (repository root):

```powershell
code/backend/.venv/Scripts/python.exe -m pip install -e '.[docs]'
code/backend/.venv/Scripts/python.exe -m mkdocs build --strict
```

Optional live voice smoke test, with all three components running (backend directory):

```powershell
.venv/Scripts/python.exe scripts/smoke_voice.py path/to/question.wav
```

Supply a mono, 16-bit PCM WAV asking about a scheme. This uses real provider quota
and retains a synthetic conversation in the local database. Success requires agent
dispatch, received audio, a persisted scheme lookup, a completed guidance response, and conversation closure.

For prompt and retrieval quality without LiveKit or the HTTP API, use the opt-in
native-audio evaluator from `code/backend`:

```powershell
.venv/Scripts/python.exe scripts/evaluate_voice_answer.py --list
.venv/Scripts/python.exe scripts/evaluate_voice_answer.py --scenario low-literacy-documents --audio path/to/first-turn.wav path/to/follow-up.wav --report ../../.janmitra/voice-evaluation.json
```

Supply one mono, 16-bit PCM, **16 kHz** WAV per conversation turn. This uses real Gemini
quota, the current system prompt and local pending-reference retrieval, and saves a
report with transcripts, tool results and audio counts. It does not start application
servers or test browser transport, interruption, or the HTTP handoff lifecycle. Review
the report against the scenario's expected behavior and forbidden claims yourself;
received audio or script completion is not an automatic answer-quality pass.

## Troubleshooting and shutdown

- API not ready: `docker compose logs --tail 80 api postgres`.
- Token rejected: check same-origin browser access, configured access code, and
  restart Next.js after editing environment files.
- No dispatched agent: check that the worker is running and both agent names match.
- Provider failure: check credentials, model access, quota, and the worker log.
- Interrupted audio: follow the request to repeat. Quota failures close immediately;
  three recoverable failures without resumed agent speech also close the session.
  A listening indicator alone does not establish successful recovery.
- Slow answers: compare worker tool durations and `retrieval_elapsed_ms`; voice calls
  should request context and avoid the legacy prepared-answer generation path.
- No verified schemes: review and publish records, or answer from source-backed pending
  references while retaining their pending-review status and qualifying actual uncertainty.
- Stop worker/frontend with Ctrl+C; stop containers with `docker compose down`.
  Database data survives. `down -v` deletes it.

## Gemini 3.1 provider status

Voice uses `gemini-3.1-flash-live-preview` for native audio input and output, with no
separate speech-to-text/text-to-speech pipeline and no alternate voice-model fallback.
The settings reject other live models. LiveKit Agents/Google 1.8.5 and Google GenAI
2.29.0 are the minimum verified client versions in this workspace.

Earlier live checks encountered Google 1011 errors, with the prior key explicitly
reporting `Resource has been exhausted (e.g. check quota)`. A replacement key from a
different account completed one synthetic English call: audio received, scheme lookup,
guidance response, and conversation closure all passed. Agent readiness took 2,431ms;
end of speech to first returned audio took 3,064ms. This is one successful test, not a
production reliability or latency guarantee. A repeat call with that key encountered
`1011 Internal error` without a quota message. It received some audio but failed to
invoke scheme retrieval or complete guidance after retry; conversation cleanup succeeded. Changing
keys did not eliminate intermittent integrated-flow failures. A minimal direct SDK test
with the replacement key subsequently completed a short answer with 79 audio chunks,
without LiveKit or tools, so a solely provider-side cause is not established. No
key-rotation pool is implemented or demonstrated as a remedy. Use the live smoke test to verify behavior and check
Gemini project usage/quota when a resource-exhausted error appears. A working key does
not require rotation solely because of a 1011 response. Rotate it if exposed or explicitly
blocked by the provider. Local API/unit tests do not establish speech reliability.
