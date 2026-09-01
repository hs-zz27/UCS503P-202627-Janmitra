# Architecture

## Repository boundary

Runtime code is isolated under `code/`. The remaining top-level directories are course
artifacts: reports, presentations, journals, and generated documentation. Keeping that
boundary explicit prevents prototype code from leaking into academic deliverables or
vice versa.

## Runtime components

| Component | Location | Responsibility |
| --- | --- | --- |
| FastAPI API | `code/backend/app` | Conversation orchestration and all trusted domain rules |
| PostgreSQL | `docker-compose.yml` | Durable conversations, records, handoffs, and audit data |
| Alembic | `code/backend/alembic` | Repeatable schema creation and upgrades |
| Voice worker | `code/backend/app/voice` | LiveKit room lifecycle, Gemini Live session, and HTTP tool calls |
| Browser harness | `code/frontend` | Development-only microphone/call interface |

The system remains a modular monolith. The voice worker does not duplicate eligibility,
catalogue, or handoff rules: it calls the API with the voice role. This keeps phone and
browser channels behaviorally consistent and makes domain decisions testable without a
model or media session.

## Request flow

1. The worker creates a conversation when a LiveKit participant connects.
2. User and assistant transcript events are persisted through the conversation API.
3. Gemini may invoke only the exposed tools: service search, eligibility, documents,
   and handoff.
4. Factual responses originate from a published, verified service record and retain its
   citation and service version.
5. A deterministic trigger creates a handoff. The conversation is marked `handed_off`
   immediately, preventing later writes from changing the closed record.
6. Operators view the queued request with its conversation events; administrators can
   inspect audit events.

## Trust boundaries

- API keys are role-specific: voice, operator, and administrator.
- LiveKit API secrets stay in the Next.js server-side token route and worker process.
- Service publication rejects records whose citations are not verified.
- Eligibility rules are evaluated by code, not inferred by the language model.
- The seed command validates every record through the same Pydantic schema and refuses
  unverified data.

## Parallel prototype adoption

The useful implementation in `D:\Janmitra` was adopted selectively:

- LiveKit/Gemini voice integration and a browser call harness
- initial database migration and containerized development workflow
- seed-command and CI patterns
- focused voice-client and lifecycle tests

It was not copied wholesale. Its narrower database and direct worker persistence would
have replaced the current versioned catalogue, deterministic eligibility engine, audit
trail, and role-gated API. The adopted worker instead uses the existing API as its single
domain boundary. Prototype package versions were also updated where security advisories
or incompatible duplicate protocol types were present.

## Service data

No government-service facts are fabricated or seeded by default. Add one reviewed JSON
record per service under `code/backend/data`, ensure every citation is marked verified,
then run `janmitra-seed data` from `code/backend`. Publication creates an immutable new
version while the service points to its current published version.
