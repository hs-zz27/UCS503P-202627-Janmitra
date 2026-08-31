# Janmitra — Weekly Engineering Journal

## Week 4 — The Tool Surface, the Model Adapter, and the API

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 25 – 31 August 2026 |
| Member | Harkamal Singh Lubana (1024170396) |
| Status at end of week | The backend is structurally complete: four typed tool endpoints, the model adapter in three modes, role-based access, the dashboard routers and the application factory. **None of it has been executed.** No migration, no fixtures, no tests, no CI. By our own standing rule, nothing this week is done. |

> **On individual logs.** Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.

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

## 4. Individual work log — Harkamal Singh Lubana (1024170396)

I built the surface the voice agent will actually call, plus the dashboard routers.

### 4.1 Typed tool envelopes

A shared `ToolRequest` base carrying `conversation_id` and `language`, so every tool call is attached to a call and knows which language to answer in. Then per-tool request and response models.

`ServiceSummary` is what discovery returns — name, category, description, benefit and eligibility summaries, whether the scheme is rule-backed, the version number, the citation, and the match score with what it matched on. Deliberately not the full record: the agent needs enough to name a scheme and cite it, and shipping the entire rule set into a voice context is wasted tokens and latency.

`CheckEligibilityResponse` carries the outcome, the per-condition trace, the missing answers, the failed conditions, the next questions, the document checklist, the version, the citation, and a spoken disclaimer. The disclaimer is part of the response rather than left to the prompt, because "this is guidance, not an official decision" is a positioning commitment from Week 1 and it should not be able to go missing because someone edited a system prompt.

### 4.2 The four tool endpoints

Each handler follows the same shape: load the conversation and refuse if the call has ended, do the deterministic work, write a conversation event and an audit event, return the typed response.

**`find_service`** records the category on the conversation, searches, and — on zero matches — returns a *suggested* handoff trigger rather than creating a handoff. The suggestion is advice to the agent; the decision still runs through `request_handoff`.

**`check_eligibility`** refuses with a conflict, not an error, when a scheme has no rule set, and says in the message to offer the checklist and citation instead. Most of the catalogue will be in that state for most of the semester, so it needs to be a normal path with a useful instruction, not a failure.

An answer-validation failure returns 422 **and** increments the conversation's tool-failure streak. That is the loop closing: repeated bad extractions eventually trip the tool-failure handoff trigger and get the citizen to a person instead of leaving them stuck with an agent that cannot parse them.

**`get_documents`** exists separately because a citizen frequently wants only the paperwork, and forcing them through an eligibility interview to get a checklist would be exactly the kind of portal behaviour the project exists to avoid.

**`request_handoff`** computes the trigger from the reported signals plus the conversation's own failure streak, and returns a conflict if nothing fires. If no summary was given but a transcript was, it asks the adapter to draft one — and if that call fails, it falls back to the trimmed transcript rather than failing the handoff. It also returns a spoken confirmation phrased as a helpline transfer, with no case ID read out, which is decision D-10 from Week 1 surviving into the code.

### 4.3 Routers

- **Catalogue** — published reads for any role; version history and the field-level diff restricted to admin; publication restricted to admin and audited.
- **Handoff queue** — list and filter by status, and a detail route returning the handoff *together with* the conversation and its full event list. An operator calling a citizen back without context would defeat the purpose of the handoff.
- **Audit** — admin-only, filterable by conversation, request ID or action. This is what turns "the system cited the right source" from an assertion into something a mentor can check at a checkpoint.
- **Conversations** — create on call connect, append events, read, and end. Ending computes and audits the TTG value.

### 4.4 The citation change

Described in Section 6.1. I wrote it into the schema as soon as we saw it, before any fixture existed, which is why it cost one small edit instead of a cleanup pass across a dozen records.

### 4.5 Where I stopped

I did not write the seed fixtures. Encoding the flagship scheme correctly needs the `applies_when` extension, which is not implemented, and I was not willing to write a fixture that silently omits a rule it cannot express. Fixtures and the evaluator extension are the top of my Week 5 list, in that dependency order.

No tests from me this week either. Stated plainly: my four weeks of work are unverified.

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
