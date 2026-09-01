![TIET Logo](assets/tiet-logo.svg){ .tiet-logo }

**UCS503P: Software Engineering Project**
**TIET Patiala**

# Janmitra

Janmitra provides voice-first, source-grounded guidance for government and civic
services. It is designed around three constraints: factual guidance comes only from a
reviewed catalogue, eligibility decisions are deterministic and explainable, and a
citizen can always be handed to a human operator with conversation context intact.

## Current implementation

- FastAPI modular monolith with role-gated HTTP APIs
- PostgreSQL persistence and Alembic migrations
- Versioned civic-service records with citation verification gates
- Deterministic eligibility traces and conditional questions/documents
- Conversation events, handoff queue, and audit records
- LiveKit Agents worker using Gemini Live
- Next.js browser harness for voice-session testing
- Automated backend and frontend checks

See [Architecture](architecture.md) for module boundaries, request flow, and the
features selectively adopted from the parallel prototype.

## Run the system

```powershell
docker compose up --build -d
cd code/frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

The API is available at `http://127.0.0.1:8000`; the browser harness defaults to
`http://127.0.0.1:3000`.
