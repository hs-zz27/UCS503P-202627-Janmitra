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
| Browser voice interface | `code/frontend` | Microphone input, streamed audio output, call controls |

The system remains a modular monolith. The voice worker does not duplicate eligibility,
catalogue, or handoff rules: it calls the API with the voice role. This keeps browser
voice consistent with the API and makes domain decisions testable without a
model or media session. The current product uses the browser channel; SIP trunks,
telephone dialing, and live phone transfers are outside this implementation.

## Request flow

1. The worker creates a conversation when a LiveKit participant connects.
2. User and assistant transcript events are persisted through the conversation API.
3. Gemini can invoke the exposed tools for service search, eligibility, documents, and
   handoff.
4. Scheme retrieval ranks published records and pending references together, with a
   published version replacing a local draft of the same slug. At most three records
   return in total; `context_order` preserves ranking across both kinds. Citations,
   versions and review metadata remain attached. Spoken answers lead with grounded
   facts and qualify actual uncertainty. The voice path does not wait for a separate
   text model to draft an answer.
5. A deterministic trigger creates a handoff. The conversation is marked `handed_off`
   immediately, preventing later writes from changing the closed record.
6. Operators view the queued request with its conversation events; administrators can
   inspect audit events.

## Trust boundaries

- API keys are role-specific: voice, operator, and administrator.
- LiveKit API secrets stay in the Next.js server-side token route and worker process.
- Service publication rejects records whose citations are not verified.
- Eligibility rules are evaluated by code, not inferred by the language model.
- Trained-knowledge fallback cannot claim verified eligibility, submission, approval,
  payment, or appointment status.
- Pending source records remain unverified even when their contents are useful retrieval
  context. They cannot support a verified eligibility verdict.
- The seed command validates every record through the same Pydantic schema and refuses
  unverified data.

## Voice design

The browser sends microphone audio over WebRTC to LiveKit. The worker maintains one
native audio session with `gemini-3.1-flash-live-preview`; tool results return to that
same model for the spoken response. There is no separate speech-to-text or text-to-speech
stage and no alternate voice-model fallback. Gemini handles turn detection with explicit
speech endpointing and `low` thinking by default. The thinking level is configurable
within the same model. Backend text tasks remain separate from
the latency-sensitive voice retrieval path.

See [Voice architecture](voice-architecture.md) for the retrieval contract, assistance
behavior, timing instrumentation, evaluation method and known limitations.

## Service data

Bundled service records under `code/backend/data` remain pending human review. They may
provide explicitly unverified retrieval context, but they are not automatically seeded
as verified facts. Check the official sources listed in `data/REVIEW.md` before using the
reviewer's explicit `janmitra-seed data --confirm-reviewed --actor "Your Name"`
attestation. Publication creates an immutable new version while the service points to
its current published version.
