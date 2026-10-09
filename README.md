# Janmitra

Janmitra is a voice-first assistant for government and civic-service guidance. It uses
reviewed source records when available, source-grounded pending reference material for
catalogue gaps, deterministic code for verified eligibility checks, and a human handoff
queue when self-service is not enough. The current product is browser voice using
`gemini-3.1-flash-live-preview` for native audio input and output.

Detailed setup, checks, and troubleshooting: [Run and test](docs/run-and-test.md).

## What is implemented

- FastAPI API with conversation, catalogue, eligibility, handoff, and audit modules
- PostgreSQL database with Alembic migrations
- LiveKit Agents worker using only Gemini 3.1 Live for speech conversations
- Verified-first retrieval with compact, provenance-labelled pending references when
  published facts are unavailable; the Live model explains the result directly
- Next.js browser microphone and streamed audio interface
- Verified-record publication and seed command
- Backend and frontend CI checks

## Repository map

| Path | Purpose |
| --- | --- |
| `code/backend` | API, domain logic, database models, migrations, voice worker, and tests |
| `code/frontend` | Browser-based voice-call interface |
| `docs` | Architecture and generated project documentation |
| `project-proposal` | Project proposal sources |
| `project-report-prototype-stage` | Prototype-stage report sources |
| `project-report-final` | Final report sources |
| `journals` | Weekly team-member journals |
| `presentations` | Presentation material |

Runtime code is under `code`; the other directories are course deliverables.

## Prerequisites

- Docker Desktop
- Node.js 22.13+ and npm
- Python 3.12 or newer
- A LiveKit Cloud project
- A Gemini API key with access to the configured live model

Docker is enough to run the database and API. LiveKit and Gemini credentials are needed
only when you want to speak to the agent.

For an API-only start without an environment file, use `docker compose up --build -d`
with the mock adapter. For the complete setup, configure the files in the guide first.

## Quick backend start

From the repository root:

```powershell
cd D:\UCS503P-202627-Janmitra
docker compose --env-file code/backend/.env up --build -d
curl.exe http://127.0.0.1:8000/readyz
```

The readiness response should be:

```json
{"status":"ready","database":"ok"}
```

- API: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- PostgreSQL: `127.0.0.1:5438`

Stop the backend with:

```powershell
docker compose down
```

Do not add `-v` unless you intentionally want to delete the local database volume.

## Talk to Janmitra

Use three terminals. All LiveKit values must come from the same LiveKit project, and the
agent name must match in the backend and frontend files.

### Terminal 1: API and database

```powershell
cd D:\UCS503P-202627-Janmitra
docker compose --env-file code/backend/.env up --build -d
```

### Terminal 2: voice worker

```powershell
cd D:\UCS503P-202627-Janmitra\code\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,voice,gemini]"
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Set these values in `code/backend/.env`:

```dotenv
JANMITRA_MODEL_ADAPTER=real
JANMITRA_GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview
JANMITRA_GEMINI_LIVE_THINKING_LEVEL=low
JANMITRA_GEMINI_API_KEY=your_gemini_api_key
JANMITRA_LIVEKIT_URL=wss://your-project.livekit.cloud
JANMITRA_LIVEKIT_API_KEY=your_livekit_api_key
JANMITRA_LIVEKIT_API_SECRET=your_livekit_api_secret
JANMITRA_LIVEKIT_AGENT_NAME=janmitra-agent
```

Start the worker and leave it running:

```powershell
janmitra-voice start
```

### Terminal 3: browser harness

```powershell
cd D:\UCS503P-202627-Janmitra\code\frontend
if (!(Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
notepad .env.local
```

Set the same LiveKit project values in `code/frontend/.env.local`:

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_AGENT_NAME=janmitra-agent
NEXT_PUBLIC_LIVEKIT_AGENT_NAME=janmitra-agent
```

Then run:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`, click **Start call**, and allow microphone access. Never
commit `.env` or `.env.local`; only their example files belong in Git.

## Review and publish service data

An initial catalogue of major central rural-service programmes is included under
`code/backend/data`. Records are deliberately stored as `pending_review`: a teammate must
check each official link in `code/backend/data/REVIEW.md` before publishing.

From `code/backend`, validate before publishing:

```powershell
janmitra-seed data --dry-run --confirm-reviewed --actor "Your Name"
janmitra-seed data --confirm-reviewed --actor "Your Name"
```

The confirmation records the reviewer and current date in the published database version;
it does not modify the pending source files. See
[`code/backend/data/README.md`](code/backend/data/README.md) for the data policy.

## Common problems

| Problem | Check |
| --- | --- |
| Secure-session error | Fill `code/frontend/.env.local`, then restart `npm run dev` |
| Call connects but stays silent | Confirm `janmitra-voice start` is running |
| Call is silent | Speak to the agent; inspect worker logs for provider errors |
| Worker does not receive the call | Use `janmitra-agent` in both environment files |
| Browser has no audio | Allow microphone and autoplay permissions |
| No published catalogue scheme is returned | Relevant pending references go directly to Gemini Live for a factual answer; pending-review metadata is retained and only published reviewed records support verified eligibility |
| Port 3000 is occupied | Run `npm run dev -- --port 3001` and open port 3001 |

## Run checks

Backend:

```powershell
cd code/backend
python -m pip install -e ".[dev,voice,gemini]"
pytest
ruff check .
```

Frontend:

```powershell
cd code/frontend
npm ci
npm test
npm run lint
npm run build
npm audit
```

## Future scope

1. Add state-specific catalogues and a scheduled re-verification workflow.
2. Add an operator dashboard for queued handoffs, notes, and callback status.
3. Consider telephone integration separately after validating the browser experience.
4. Expand Hindi and regional-language evaluation with real speakers.
5. Add realistic load tests and multilingual user evaluation.
6. Deploy the API, worker, frontend, and managed database with HTTPS and backups.
7. Add production authentication, secret rotation, rate limiting, and access controls.
8. Add monitoring for latency, tool failures, handoffs, call completion, and worker health.
9. Define transcript/contact-data consent, retention, redaction, and deletion policies.
10. Complete user evaluation, demo evidence, reports, journals, and final presentation.

## More documentation

- [Backend details](code/backend/README.md)
- [Frontend details](code/frontend/README.md)
- [Architecture](docs/architecture.md)
- [Voice design, reference comparison, and latency evaluation](docs/voice-architecture.md)
