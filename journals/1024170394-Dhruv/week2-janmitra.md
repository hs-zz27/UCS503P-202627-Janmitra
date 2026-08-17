# Janmitra - Week 2 Journal

## Proposal Finalisation and Backend Planning

This week, we completed the final review of the Janmitra project proposal. After checking the scope, architecture, deliverables, and evaluation criteria, we finalised the proposal and pushed the completed version to the project repository.

My individual contribution was to think through the backend technology stack and how its components would fit together. I proposed using Python with FastAPI for the backend API and PostgreSQL for storing scheme versions, eligibility rules, conversations, handoff requests, and audit records. I also considered a modular monolith structure for the catalogue, eligibility, ingestion, conversation, handoff, and audit modules. This keeps the first implementation manageable while preserving clear module boundaries.

For the voice workflow, the backend will integrate with LiveKit and Gemini Live. The language model will handle conversation and explanation, while validated backend tools will remain responsible for deterministic operations such as eligibility checks, record publication, and handoff creation.

### Outcomes

- Finalised and pushed the project proposal.
- Identified FastAPI (Python) and PostgreSQL as the core backend stack.
- Planned a modular monolith architecture for the initial implementation.
- Defined a clear boundary between AI-driven conversation and deterministic backend logic.
- Prepared the backend direction for the implementation phase.
