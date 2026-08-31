# Janmitra — Weekly Engineering Journal

## Week 2 — Scope Reconciliation, Repository Foundations & Freezing the Canonical Record

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 11 – 17 August 2026 |
| Member | Harkamal Singh Lubana (1024170396) |
| Status at end of week | Governing scope resolved in favour of the submitted proposal. Backend repository scaffolded. Canonical service record and persistence model written and frozen. No endpoint exists yet, by design. |

> **On individual logs.** Week 1 was joint ideation and its journal is identical for all three of us. From this week the shared sections below (objective, day-by-day, decisions, risks) remain common to the team, and each member's journal additionally carries **Section 4 — Individual work log**, which differs.

---

## 1. Objective for the week

Two things had to be settled before a single line of feature code was worth writing.

**First, which document governs.** We were carrying two incompatible scope documents: the submitted proposal `UCS503_Janmitra_Proposal.pdf`, and an earlier internal note, *Lean Software Engineering Course Proposal v0.4*, which had quietly narrowed the build to web-only voice, Hindi and English, and a fixed 9–12-record catalogue. Building against both was not possible, and discovering the conflict at a checkpoint would have been far worse than resolving it now.

**Second, the build order.** Our Week 1 design has five surfaces reading the same scheme record — discovery, document checklist, eligibility, citations and the admin screen. If that record's shape is still moving when those surfaces are written, every change costs five edits. So the week's engineering objective was deliberately unglamorous: freeze the schema, stand up the repository around it, and write nothing that consumes it yet.

Concretely:

1. Reconcile the two scope documents and record the outcome as a decision, not a conversation.
2. Produce a single working handoff document that anyone — teammate, mentor or an assistant — can read cold and be current.
3. Scaffold the backend as the modular monolith the proposal describes, with six module boundaries visible in the directory layout from day one.
4. Freeze the canonical service record as a validated schema.
5. Write the persistence model, including the versioning semantics that make publication non-destructive.
6. Put request IDs and structured logging in before the first endpoint exists, because Time-to-Guidance cannot be reconstructed later if it was never logged.

---

## 2. Day-by-day activity log

### Day 1 — Reconciling the two scope documents

We put the submitted PDF and lean v0.4 side by side and worked through the seven dimensions where they disagreed: citizen channel, language coverage, catalogue size, eligibility engine, model layer, validation method and deployment.

The decision was that **the submitted proposal governs, without exception**. It is the document the mentor was given and the one the project will be graded against; a private note cannot silently shrink a submitted commitment. The two consequences that matter most:

- **Telephony / SIP into LiveKit is the citizen channel**, and stays on the critical path. v0.4 had listed it as a cut. It is not a cut. The browser and recorded-audio path is a development, test and load-test harness, and we agreed to describe it that way in every document so it never drifts back into being called a citizen channel.
- **10+ Indian languages and dialects stay in scope.** Hindi and English are simply the first two we will validate end to end. Anything not yet measured gets described as *supported but untested*, never as validated.

We also agreed the rule that stops this recurring: anything from v0.4 can only be re-adopted through an ADR carrying a reason and a date, raised with the mentor at the next checkpoint.

The proposal was revised to remove the remaining ambiguity and re-dated **17 August 2026**.

### Day 2 — The working handoff document

We wrote `context.md`: a single page holding positioning, problem statement, architecture, data model, the deliberate cuts, the evaluation criteria, the risk register, the demo script and the build plan. Its first line states that the submitted PDF outranks it, so that if the two ever disagree the page is what gets corrected.

This is not documentation for its own sake. Three people and a fifteen-week timeline generate a lot of decisions that live only in someone's memory; the cost of that shows up at the checkpoint when nobody can reconstruct why a thing was built the way it was. Writing §18 — the build plan, in order, with a definition of done for each piece — is what let this week end with an agreed next task instead of a discussion.

### Day 3 — Backend scaffold and the six module boundaries

We scaffolded the backend under `code/backend` as a Python package, and made the six modules from the proposal — conversation, catalogue, eligibility, ingestion, handoff, audit — actual directories rather than a diagram. The point of a modular monolith is that the boundaries are real even though the deployment is one process; if they are only in the architecture figure, they erode in week 9.

Tooling was fixed the same day: FastAPI, SQLAlchemy 2.0 with async sessions, Alembic, Pydantic v2 for every schema, `pydantic-settings` for configuration, `ruff` for linting and `pytest` for tests. Every setting that differs between local, staging and the load rig is read from the environment, so one image runs in all three — which is what the replica-count comparison in the scalability plan actually requires.

### Day 4 — Freezing the canonical service record

The whole day went on one file. The record covers slug, name, aliases, category, description, benefit and eligibility summaries, the eligibility rule set, required documents, application steps and the citation.

Two parts took the argument:

- **The rule set is data inside the record, not code and not a side table.** A scheme becomes rule-backed by adding JSON questions and conditions. This is the shortcut the whole eligibility plan rests on: catalogue breadth becomes an import-and-review operation rather than new engineering.
- **The record validates its own internal references.** A rule set whose decision names a condition that does not exist, or a condition that tests a question nobody asks, or a document conditional on an unasked question, is rejected at parse time. These are exactly the mistakes a human reviewer makes at 1 a.m. while encoding a scheme, and they would otherwise surface as a wrong answer told to a citizen.

### Day 5 — Persistence model and versioning semantics

We wrote the tables from the Week 1 data model: `services`, `service_versions`, `source_snapshots`, `conversations`, `conversation_events`, `handoff_requests`, `audit_events`.

The one deliberate departure from the Week 1 ER sketch is that **`eligibility_rule` is not a table**. The rule set lives inside the versioned record payload, so changing a rule is necessarily a new version passing through the same human review gate as any other change. A side table would have allowed rules to mutate underneath a published version — precisely the thing the review gate exists to prevent. This is recorded as a decision rather than left as an inconsistency between the diagram and the code.

`conversations` carries two columns that exist purely for the primary metric: `connected_at` and `first_guidance_at`. Writing them now, before any endpoint can set them, was deliberate.

### Day 6 — Observability before endpoints

Structured JSON logging, a request-ID context variable and the middleware that populates it, all written before the first route. An inbound `X-Request-ID` is honoured and echoed back, so a request can be followed from the voice worker, through the API, into the audit table. Liveness and readiness were split: the load balancer must not evict a replica because Postgres was briefly busy, and a staging deploy must not go green before the database is reachable.

---

## 4. Individual work log — Harkamal Singh Lubana (1024170396)

My work this week was the data: the canonical service record, and the tables that store it.

### 4.1 The canonical service record

I wrote the schema as a set of Pydantic v2 models with `extra="forbid"` throughout, so a typo in a hand-written fixture is a parse error rather than a silently ignored field. The pieces:

- `ServiceRecord` — the top-level record: slug, name, aliases, category, description, benefit and eligibility summaries, optional rule set, documents, steps, citation.
- `LocalizedText` — any short string the agent may read aloud. English is mandatory as the pivot; other languages are optional and are added as the language sweep validates them.
- `RuleSet` — `questions`, `conditions` and a `decision`, all data.
- `EligibilityQuestion` — id, prompt, answer type (boolean, integer, number, enum, string), plus options, unit, min and max.
- `Comparison` — one leaf test: a question id, an operator (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `between`) and a constant taken from the official source.
- `Condition` — a *named* comparison carrying a description and the sentence from the official source that justifies it.
- `Decision` — `all_of` / `any_of` / `none_of` over condition ids.
- `RequiredDocument` — checklist entries, optionally gated on an answer.
- `Citation` — source URL, title, publisher, verification date and the snapshot id.

Naming the conditions rather than nesting one big boolean expression was a deliberate choice. A named condition can carry its own justification text and can be reported individually, which is what lets the agent say *why* a citizen did not qualify instead of just that they did not. It is also what makes a per-condition boundary test possible.

### 4.2 Validation the schema does on itself

Four checks that all run at parse time:

1. A condition may only test a question the rule set actually declares.
2. A decision may only reference conditions that exist.
3. Condition ids must be unique within a rule set.
4. A document may only be conditional on a question the rule set asks.

An enum question with no options, and a non-enum question that declares options, are both rejected as well. `between` requires a two-element value and `in`/`not_in` require a list.

These are cheap to write and they catch the specific class of mistake a tired human makes while encoding a scheme at speed. I would rather a fixture fail to load than have it load and quietly never fire a condition.

### 4.3 Persistence model

I wrote all seven tables. The parts worth recording:

- **Publication is append-plus-repoint.** `service_versions` rows are immutable. Publishing writes a new row and moves `services.current_version_id`; nothing is ever updated in place and nothing is deleted. Version numbers are unique per service by constraint, not by convention.
- **The circular foreign key.** `services.current_version_id` points at `service_versions`, which points back at `services`. I resolved it with `use_alter=True` on the service-side constraint and a `post_update` relationship, so the constraint is emitted after both tables exist.
- **`conversation_events` has a unique constraint on `(conversation_id, seq)`.** The sequence number is derived inside the transaction, so if two API replicas write a turn to the same call concurrently, one fails loudly instead of both succeeding with the same position. Silent interleaving in a transcript is the kind of bug that is invisible until an operator reads a nonsensical handoff context.
- **`conversations.tool_failure_streak`** is a column, not an in-memory counter, because "tools failed repeatedly" is a handoff trigger and it has to survive the request landing on a different replica.
- **`audit_events` carries `request_id`** alongside actor, action, entity type and entity id.

### 4.4 What I did not do

I wrote no Alembic migration this week. The schema is settled but not yet materialised into a versioned migration, and I did not want to generate one against a model I might still adjust while writing the evaluator against it. It is the first task in my Week 3 queue.

## 5. Decisions taken this week

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| D-19 | The submitted proposal PDF is the sole source of truth for scope; lean v0.4 is superseded | It is the document submitted and graded; a private note cannot shrink a submitted commitment | Build to v0.4; maintain both |
| D-20 | Telephony/SIP into LiveKit remains the citizen channel; browser/recorded audio is a test harness only | Removing the smartphone and data-connection barrier is the point of the project | Web-only voice with phone as future work |
| D-21 | Any re-adoption of a v0.4 narrowing requires an ADR with a reason and a date | Makes scope drift visible instead of silent | Informal agreement |
| D-22 | Freeze the canonical service record before writing any endpoint | Five surfaces read it; a moving schema costs five edits per change | Evolve the schema alongside the features |
| D-23 | Eligibility rules are JSON data inside the versioned record, with no `eligibility_rule` table | A rule change must go through the same review gate as any other change; a side table would let rules mutate under a published version | Separate rules table as per the Week 1 ER sketch |
| D-24 | The record validates its own internal references at parse time | Catches unresolvable conditions and orphaned documents before they become a wrong answer to a citizen | Validate at evaluation time; trust the reviewer |
| D-25 | `LocalizedText` requires English as a pivot and falls back to it | The record holds the *verified* text and the model translates at speaking time; a missing translation must never become a missing fact | Per-language records; fail on missing translation |
| D-26 | JSON columns declared portable with a JSONB variant for Postgres | Unit tests run in seconds without a container while staging and production still get JSONB indexing | Postgres-only columns and a test container for every run |
| D-27 | Request IDs, structured JSON logs and the TTG timestamp columns exist before the first endpoint | TTG cannot be reconstructed later if it was never logged | Add observability once features work |
| D-28 | Liveness and readiness are separate endpoints | A busy database must not evict a replica; a deploy must not go green before the database is reachable | One combined health check |

---

## 6. Problems hit and how they were resolved

| Problem | Resolution |
| --- | --- |
| Two scope documents disagreeing on seven dimensions, with the narrower one easier to build | Settled by rule rather than by preference: the submitted document governs. Recorded as D-19 so it cannot be relitigated informally. |
| `services.current_version_id` and `service_versions.service_id` reference each other, so neither table can be created first | Declared the service-side foreign key with `use_alter=True` and made the relationship `post_update`, so SQLAlchemy emits the constraint after both tables exist. |
| Wanting JSONB indexing in production but not wanting every unit test to need a Postgres container | A single portable column type with a Postgres variant, defined once and used by every JSON column. |
| Risk of the browser harness quietly becoming "the citizen channel" in casual conversation | Written into `context.md` and into the code comments as a test harness, in the same words, everywhere it appears. |

---

## 7. Deliverables produced this week

- Scope reconciliation and the governing-document decision, recorded as ADRs
- Revised and re-submitted proposal, dated 17 August 2026
- `context.md` — the working handoff document, including the §18 build plan
- Backend package scaffold with the six module boundaries as real directories
- Environment-driven configuration and a documented `.env.example`
- The canonical service record schema, with internal-reference validation
- The persistence model for all seven entities, with non-destructive versioning semantics
- Structured JSON logging, request-ID propagation, and split liveness/readiness checks

---

## 8. Contribution split

| Member | Week 2 contribution |
| --- | --- |
| Dhruv Srivastava (1024170394) | Joint scope reconciliation and build-order planning. Individually: repository scaffold, configuration layer, structured logging and request-ID propagation, async database layer, liveness/readiness split. |
| Harkamal Singh Lubana (1024170396) | Joint scope reconciliation and build-order planning. Individually: canonical service record schema and its validation rules, persistence model for all seven entities, versioning semantics. |
| Paras (1024170395) | Joint scope reconciliation and build-order planning. Individual log maintained in his own journal and not duplicated here. |

---

## 9. Risks reviewed

| Risk | Status this week |
| --- | --- |
| Scope drifting back towards the superseded lean v0.4 | Mitigated by D-19 and D-21. The governing document is now stated in the first paragraph of `context.md`. |
| Telephony / SIP provisioning delay | Still open and still the largest schedule risk. The plan remains a two-provider spike, with the recorded-audio harness keeping every other workstream unblocked. |
| Evaluation measurement ambiguity | Reduced: the two TTG timestamps now exist as columns with written definitions, before anything can set them. |
| Schema churn once features are written | Mitigated by freezing the record this week. If it does change, the cost is now visible as a migration rather than hidden in five files. |

---

## 10. Carried into Week 3

The deterministic core: the eligibility rule evaluator, catalogue reads and versioned publication, conversation state, the handoff trigger rules, and the audit writer. Still no endpoints — tools before voice, and logic before both.
