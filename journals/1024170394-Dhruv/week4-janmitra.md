# Janmitra — Weekly Engineering Journal

## Week 4 — The Tool Surface, the Model Adapter, and the API

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 25 – 31 August 2026 |
| Member | Dhruv Srivastava (1024170394) |
| Status at end of week | The backend is structurally complete: four typed tool endpoints, the model adapter in three modes, role-based access, the dashboard routers and the application factory. **None of it has been executed.** No migration, no fixtures, no tests, no CI. By our own standing rule, nothing this week is done. |

> **On individual logs.** Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.
>
> **On Week 2.** My own Week 2 entry is a shorter record of proposal finalisation and backend planning. The fuller shared Week 2 write-up — the scope-reconciliation decisions D-19 to D-28, the day-by-day log and the risk review — is kept in the team's Week 2 journal, and the cross-references below point there.

---

## 1. Objective for the week

Week 3 produced the logic. This week put a surface on it — but in the order the build plan insists on: **tools before voice**. Every capability the voice agent will eventually call is first a plain HTTP endpoint with a typed request and a typed response. When the telephony leg is integrated and something goes wrong, we will be able to tell a voice problem from a logic problem in one `curl`.

The week's targets:

1. The four tool endpoints — `find_service`, `check_eligibility`, `get_documents`, `request_handoff` — with typed envelopes, citations on every factual response, audit and conversation events on every call.
2. The model adapter in its three modes, with schema validation as a hard gate on everything it returns.
3. Role-based access for the three seeded accounts, enforced by a real dependency.
4. The dashboard routers: catalogue with version history and diff, the operator queue, the audit query.
5. Domain-error to HTTP-status mapping in one place.

And one honest assessment at the end of it, recorded in Section 6.

---

## 2. Day-by-day activity log

### Day 1 — Typed tool envelopes

We wrote the request and response models before any handler. Two rules were fixed:

- **Every factual response carries `citation` and `service_version`.** FR-04 asks for the source and its verification date on every factual answer; we added the version number as well, because a citation without a version cannot be checked six weeks later once the record has moved on.
- **Requests forbid unknown fields.** A tool call arriving with a misspelled field fails loudly rather than silently proceeding with a default.

### Day 2 — The tool endpoints

The handlers are thin and do the same four things in the same order: load and check the conversation, do the deterministic work, record a conversation event and an audit event, return a typed response.

The behaviour worth recording is where the TTG clock stops. A cited scheme match stops it. A decided eligibility result stops it. A delivered document checklist stops it. A follow-up question does **not** — `needs_more_info` is not guidance, and letting it stop the clock would make the primary metric flattering and meaningless.

`request_handoff` was the interesting one: it computes the trigger from reported signals and **refuses with a conflict when no trigger fires**. The tool telling the agent "no, keep helping" is what makes the handoff precision half of the precision/recall measurement a property of the system rather than of the prompt.

### Day 3 — The model adapter

Three implementations behind one interface. Every method returns a validated Pydantic model, which is the Week 1 invariant expressed in code: model output that does not fit the schema never reaches a backend tool.

The mock is deterministic, including its failure injection — same input, same verdict, every run. A load test whose failures move between runs cannot support a before/after comparison, which is the entire point of the exercise.

### Day 4 — Access control and error mapping

Three seeded keys mapping to admin, operator and voice, with a dependency factory that returns 401 for an unknown key and 403 for a known key in the wrong role. Small, but it has to be real: §14 lists unauthorised admin/operator action tests, and those tests need something that actually refuses.

Domain exceptions are mapped to HTTP statuses in one registry, so the modules can raise meaningful errors without importing FastAPI, and no domain error can escape as a 500 with a stack trace. Every error response carries the request ID.

### Day 5 — Routers and the application

Catalogue reads and publication, version history and the field-level diff (admin only), the operator queue including full conversation context, and the audit query filterable by conversation, request ID and action. Then the application factory wiring middleware, error handlers and six routers together.

### Day 6 — A schema change we did not expect to make, and a stop

Preparing the seed fixtures, we hit the honesty problem described in Section 6.1 and changed the citation schema in response. Then we stopped, deliberately, rather than starting the fixtures: see Section 6.2.

---

## 4. Individual work log — Dhruv Srivastava (1024170394)

I built the model adapter, access control, error handling and the application wiring.

### 4.1 The adapter interface

An abstract base with three methods: `extract_intent`, `summarize_issue` and `draft_service_record`. Each returns a Pydantic model — `Intent`, `IssueSummary`, `DraftRecord` — and that is the whole enforcement mechanism for the project's central invariant. Model output that does not fit the schema raises `ModelOutputInvalid` and never reaches a tool. There is no path from raw provider text into a database row.

`Intent` deserves a note. It carries the action, an optional category, the query, any eligibility answers the citizen volunteered, a confidence score, a `wants_human` flag and the detected language. The confidence and the flag are *inputs to a deterministic trigger function*, never the trigger themselves — the model reports what it observed and the backend decides.

I also scoped the adapter explicitly in its docstring: it covers the text and structured-extraction calls the backend makes. The realtime speech leg — Gemini Live inside the LiveKit worker — does not pass through the API at all. Without that written down, someone will eventually look for the voice pipeline in this file.

### 4.2 The mock adapter

The important property is determinism, including failures. Failure injection hashes the input and compares against the configured rate, so the same call fails on every run. Random failure, even seeded, drifts as soon as call ordering changes under concurrency — and a load test whose failures move between runs cannot support the before/after comparison the scalability plan is built on.

Intent extraction is keyword-driven across English and romanised Hindi hints for each category, plus phrases that indicate wanting a person. Confidence is derived from how much of the utterance the mock actually recognised, which means a vague request deterministically lands below the handoff threshold. That is what lets us test the low-confidence trigger without a real model.

Latency is injectable, so the load rig can model a slow provider without paying for one.

### 4.3 The failure adapter and the Gemini adapter

The failure adapter raises `ModelUnavailable` from every method. It exists so the requirement that a failed model call must return a recoverable message and must not corrupt a handoff or service record has a test that can actually be run.

The Gemini adapter imports `google-genai` lazily inside its constructor, so the package's absence is a clear configuration error at startup rather than an import error at collection time. It uses JSON response mode at temperature zero, parses, then validates through the same Pydantic gate. Its system instructions state explicitly: never invent scheme facts, copy values from the source, omit any field the source does not support.

The factory selects by configuration and caches one adapter per process, and refuses `real` mode when no API key is configured rather than failing on the first citizen call.

### 4.4 Access control

Three seeded keys, one header, a `Role` enum, and a `require(*roles)` dependency factory. An unknown key is 401; a known key in the wrong role is 403. Tool routes accept voice and admin; the operator queue accepts operator and admin; version history, publication and audit are admin only.

It is intentionally not an auth product. It is also intentionally not a comment — §14 lists unauthorised-action tests, and those need something that refuses.

### 4.5 Error mapping and the application factory

One registry maps every domain exception to a status: not-found to 404, closed conversation and invalid transition to 409, answer validation to 422 with the error list, model unavailable to 503, invalid model output to 502. Every error body carries the request ID.

The 503 case has a comment I want to keep visible: it is recoverable *by contract* — no handoff and no service record has been written when it fires.

The factory configures logging, adds the request-ID middleware, registers the handlers and includes the six routers.

### 4.6 What I did not do, and one thing I got wrong

No CI. I made the same call as in Week 2 — a pipeline running zero tests is a signal that means nothing — but I have now deferred it twice, and the build plan asked for it in Week 2. It is on the Week 5 list with the first tests, and I am recording the deferral rather than quietly carrying it.

The mistake I want on the record: I let error handling end up in two places. Some tool handlers catch a missing service and raise a 404 themselves while the global registry also maps that exception. It works, but it is two places to change, and I only noticed while writing this entry. Consolidating into the registry is a Week 5 task, done once tests exist to confirm no status code moves.

Nothing I wrote this week has been executed.

## 5. Decisions taken this week

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| D-42 | Every factual tool response carries both the citation and the service version number | A citation without a version cannot be verified once the record moves on | Citation only |
| D-43 | Tool request models forbid unknown fields | A misspelled field must fail loudly, not silently take a default | Ignore extras |
| D-44 | The TTG clock stops on a scheme match, a decided eligibility result, or a delivered checklist — never on a follow-up question | A metric that a clarifying question can improve is not measuring guidance | Stop on any tool response |
| D-45 | `request_handoff` refuses when no deterministic trigger fires | Makes handoff precision a property of the system, not of the prompt | Create a handoff whenever asked |
| D-46 | Every model adapter method returns a validated Pydantic model | The Week 1 invariant, in code: unvalidated model output never reaches a tool | Return raw dicts and validate at the call site |
| D-47 | Mock failure injection is hash-derived, not random | A load test must be reproducible to support a before/after claim | Random failure with a seed |
| D-48 | The Gemini SDK is an optional dependency, imported lazily | Backend, tests and load rig must all run without it | Hard dependency |
| D-49 | A failed summary call degrades to the raw transcript rather than failing the handoff | Never drop a citizen because a model call failed; the operator gets worse prose but the same context | Fail the request; queue with an empty summary |
| D-50 | `Citation` carries a verification state and the name of the verifier; seeded records are `pending_review` | The catalogue is described as human-reviewed, so a record must be able to say when it is not yet | Trust the `verified_on` date alone |
| D-51 | Role checks are a real dependency returning 401 and 403 | The unauthorised-action tests need something that actually refuses | Document the roles; enforce later |
| D-52 | Domain-error to HTTP mapping lives in one registry | Modules stay free of FastAPI imports; no domain error escapes as a 500 | Try/except in each handler |

---

## 6. Problems hit and how they were resolved

### 6.1 Seeded records would have claimed to be human-verified

Every service record carries a citation with a `verified_on` date, and `context.md` describes the catalogue as *verified* and *human-reviewed*. Writing the first fixtures, the problem became obvious: a seeded record would carry a verification date that no human had earned. It would be indistinguishable from a record someone had actually checked against the official page, and the citizen would be told "verified on this date" on the strength of nothing.

Fixed in the schema rather than in a convention. `Citation` now carries:

- `verification_state`, either `pending_review` or `verified`, defaulting to `pending_review`;
- `verified_by`, the person who checked it, which the schema **requires** once the state is `verified`.

Seeded and freshly imported records are `pending_review`. A record becomes verified when a named team member checks it against the official source and says so. The rule follows: no scheme appears in a demo or a pilot run while it is `pending_review`.

This is the sort of thing that would have been very difficult to retrofit — by the time anyone noticed, there would be a dozen fixtures with unearned dates and no way to tell which had actually been checked.

### 6.2 Four weeks of code, none of it ever run

The honest status at the end of this week: the backend is structurally complete and has **never been executed**. Dependencies have not been installed. The database layer has not opened a connection. There is no Alembic migration, so no schema exists to connect to. There are no seed fixtures, no tests, and no CI job.

Our own standing rule from the build plan is that *nothing counts as done until it has a test and a place in the demo script*. By that rule, none of Weeks 2, 3 or 4 is done. What exists is written and reviewable, not verified.

We considered pressing on into ingestion and stopped instead. The reasoning: the further we build on unexecuted code, the larger the eventual debugging surface, and the first import will tell us more about four weeks of assumptions than another week of typing would. Section 10 is the order in which that gets fixed, and it goes ahead of every new feature.

We also note the build plan asked for CI on day one and we do not have it. That was a judged trade — a green pipeline that runs no tests teaches the team to trust a signal that means nothing — but it has now been deferred twice, so it is scheduled explicitly rather than left to sit.

### 6.3 Which layer owns a "not found"

Some tool handlers translate a missing service into a 404 themselves; the global registry also maps that exception. Duplication that works today, but it is two places to change. Marked for consolidation into the registry when the tests are written and can confirm no status code moves.

---

## 7. Deliverables produced this week

- Typed tool envelopes, with citation and service version on every factual response
- Four tool endpoints: `find_service`, `check_eligibility`, `get_documents`, `request_handoff`
- Model adapter interface, deterministic mock, always-failing failure adapter, Gemini adapter, and the selection factory
- Role-based access for the three seeded accounts, with 401/403 behaviour
- Catalogue routes including admin-only version history and field-level diff
- Operator queue routes returning the handoff together with its conversation context
- Audit query route filterable by conversation, request ID and action
- Domain-error to HTTP-status registry, with the request ID on every error response
- Application factory wiring middleware, handlers and six routers
- Citation verification state added to the canonical record

---

## 8. Contribution split

| Member | Week 4 contribution |
| --- | --- |
| Dhruv Srivastava (1024170394) | Joint review of the TTG stopping rule and the handoff refusal behaviour. Individually: the model adapter family and the selection factory, role-based access control, the domain-error registry, the application factory and health wiring. |
| Harkamal Singh Lubana (1024170396) | Joint review of the TTG stopping rule and the handoff refusal behaviour. Individually: the typed tool envelopes and the four tool endpoints, the catalogue, conversation, handoff-queue and audit routers, and the citation verification-state change. |
| Paras (1024170395) | Joint review of the TTG stopping rule and the handoff refusal behaviour. Individual log maintained in his own journal and not duplicated here. |

---

## 9. Risks reviewed

| Risk | Status this week |
| --- | --- |
| Four weeks of unexecuted code | **The dominant risk now.** Everything written since Week 2 is unverified. Week 5 is migration, fixtures, tests and CI, ahead of any new feature. |
| CI deferred past the point the build plan asked for it | Deferred twice. Now scheduled with the first test suite rather than left open-ended. |
| Telephony / SIP provisioning delay | Unchanged. Still the largest schedule risk and still untouched by anything built so far. |
| Seeded data presenting itself as verified | **Closed** by D-50. The schema now distinguishes pending from verified and names the verifier. |
| Rule model expressiveness (`applies_when`) | Still open from Week 3. Scheduled for Week 5 with the flagship fixture, since the fixture cannot be encoded correctly without it. |
| Scope creep | None. Ingestion was explicitly not started despite the module directory existing. |

---

## 10. Carried into Week 5 — in this order

1. Alembic migration for the seven tables, applied against a real Postgres.
2. The `applies_when` guard extension to the evaluator, with its boundary tests.
3. Seed fixtures: the initial working set of schemes as hand-reviewed JSON, all `pending_review`, with the flagship fully rule-backed.
4. Test suite — evaluator boundary cases first, then the tool endpoints, versioning, handoff transitions and the unauthorised-action tests.
5. CI: build, lint and tests on every push. No further feature work until this is green.
6. Dockerfile and Compose for Postgres plus the API, as the basis for the replica-count comparison later.
