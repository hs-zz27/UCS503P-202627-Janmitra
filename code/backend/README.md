# Janmitra backend

FastAPI modular monolith for conversations, versioned civic-service records,
deterministic eligibility, documents, human handoff requests and audit events.

Use [Run and test](../../docs/run-and-test.md) for canonical installation, configuration,
startup, migration and test commands. The API is on port 8000; local Compose PostgreSQL
is on host port 5438. Containers apply Alembic migrations before API startup.

## Component boundaries

The LiveKit worker calls `JANMITRA_BACKEND_BASE_URL` with `JANMITRA_VOICE_API_KEY`; it
does not access the database directly. Voice uses only `gemini-3.1-flash-live-preview`
for native audio, with no separate STT/TTS stage or telephone integration.

Voice retrieval requests `response_mode="context"`, merging published records and
pending references in one ranked result. Gemini Live answers from compact facts
without a second answer-generation call. Existing API clients retain the default
`prepared_answer` mode. Ingestion and optional handoff summaries use the backend text
adapter; the mock adapter supports offline development.

Only reviewed, published records support deterministic eligibility and verified
checklists. Pending references retain their provenance and cannot become official
personal eligibility decisions. Handoff creates an operator queue item, not a transfer.

## Service records

`data` contains one JSON record per service. Human reviewers must check
[data/REVIEW.md](data/REVIEW.md) and the linked official evidence before publication.
`janmitra-seed` validates records and requires a named, explicit review attestation for
pending records. Publication creates immutable versions. Never confirm review merely
to populate a demo.

See [Architecture](../../docs/architecture.md) and
[Voice architecture](../../docs/voice-architecture.md) for contracts, timing boundaries,
evaluation methods and known limitations.
