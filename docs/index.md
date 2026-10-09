![TIET Logo](assets/tiet-logo.svg){ .tiet-logo }

**UCS503P: Software Engineering Project**
**TIET Patiala**

# Janmitra

Janmitra provides voice-first, source-grounded guidance for government and civic
services. Reviewed catalogue answers and deterministic eligibility results are
verified; catalogue gaps use source-backed pending references passed directly to Gemini
3.1 Live. Spoken answers lead with useful facts and qualify actual uncertainty; the
records remain pending review. Human
handoff requests enter an operator queue with conversation context.

## Current implementation

- FastAPI modular monolith with role-gated HTTP APIs
- PostgreSQL persistence and Alembic migrations
- Versioned civic-service records with citation verification gates
- Deterministic eligibility traces and conditional questions/documents
- Conversation events, handoff queue, and audit records
- LiveKit Agents worker using Gemini Live
- Next.js browser harness for voice-session testing
- Automated backend and frontend checks

See [Architecture](architecture.md) for module boundaries and request flow, and
[Voice architecture](voice-architecture.md) for behavior, evaluation and known limits.

## Run the system

Follow [Run and test](run-and-test.md) for the database, API, LiveKit worker, browser,
and automated checks.
