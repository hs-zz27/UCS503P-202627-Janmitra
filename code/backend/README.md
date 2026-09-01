# Janmitra backend

FastAPI orchestrator for versioned civic-scheme records, deterministic eligibility,
conversation state, human handoff, and audit events.

## Docker development

From the repository root:

```powershell
docker compose up --build -d
```

The API container applies Alembic migrations before starting. API documentation is at
`http://127.0.0.1:8000/docs`; PostgreSQL is exposed on host port `5438`.

## Local development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

The optional LiveKit worker requires `pip install -e ".[voice]"` and the LiveKit/Gemini
settings documented in `.env.example`.

Copy `.env.example` to `.env`, supply real LiveKit and Gemini credentials, then run:

```powershell
janmitra-voice dev
```

The worker calls the API configured by `JANMITRA_BACKEND_BASE_URL` and authenticates with
`JANMITRA_VOICE_API_KEY`. It does not access the database directly.

## Service records

Place reviewed data at `data/services.json`; see `data/README.md` for the format. Import
and publish it with:

```powershell
janmitra-seed data --actor team-member
```

The command validates all records before writing and rejects citations that are not
marked `verified`.

## Checks

```powershell
pytest
ruff check .
```
