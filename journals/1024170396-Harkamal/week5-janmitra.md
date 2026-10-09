# Janmitra — Weekly Engineering Journal

## Week 5 — Running the Code for the First Time

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 1 – 7 September 2026 |
| Member | Harkamal Singh Lubana (1024170396) |
| Status at end of week | The backend has been executed. 197 tests collected, 194 passing, 3 `xfail` documenting one real defect the suite found. `ruff` clean. CI runs lint and tests on every push and the signal now means something. The dominant risk carried since Week 2 — four weeks of code that had never run — is closed. |

> **On individual logs.** Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.
>
> **On Section 2.** Previous weeks logged work by day. This week's verification pass was done in one concentrated sitting rather than spread across six days, so Section 2 is ordered by the sequence the work was actually done in. Recording it as six days would be a tidier log and a false one.

---

## 1. Objective for the week

Week 4 closed with an assessment rather than a deliverable: *the backend is structurally complete and has never been executed.* By our own standing rule — nothing counts as done until it has a test and a place in the demo script — none of Weeks 2, 3 or 4 was done. Everything written since the persistence layer was reviewable, not verified.

Week 5 had exactly one objective: **make that statement false.** No new backend features until the existing ones have been run.

The targets, in the dependency order Week 4 §10 set out:

1. Install the dependencies and get an interpreter to import the package at all.
2. A test harness that can stand up the whole application — routers, middleware, error handlers, database — without a Postgres container.
3. Test suites over every module written in Weeks 2–4, at the level the requirement is stated at, not at the level of the function.
4. CI running lint and tests on every push.
5. An honest count at the end of what is covered and what still is not.

---

## 2. Sequence of work

### 2.1 What arrived from the rest of the team first

Before the verification pass began, a substantial merge landed from Dhruv: the LiveKit voice worker and its Gemini Live agent, a Next.js browser harness with a LiveKit token route, `docker-compose.yml` for Postgres plus the API, the Alembic migration for the seven tables, the `applies_when` guard extension to the evaluator that Week 3 had left open, the `janmitra-seed` loader, and the two GitHub Actions workflows. Eleven tests came with it, covering the evaluator's guards, two publication and handoff cases, and the voice worker's HTTP client.

That closed three of the six items carried into Week 5 (migration, guard extension, CI) before this week's individual work started. It also meant the verification pass had a real CI job to land in rather than a hypothetical one.

### 2.2 First execution

The dependencies had genuinely never been installed. A virtual environment, `pip install -e ".[dev]"`, and then the first ever `pytest` against this codebase. Eleven tests, all green — which proves that the modules import and that the evaluator and the voice client work, and proves nothing whatsoever about the API surface, access control, versioning, conversation state or the adapters.

That gap was the week's work.

### 2.3 The test harness

Written before any test. Described in Section 4.1.

### 2.4 The suites

Ten test modules, written module by module against the requirement each one exists to satisfy. Detailed in Section 4.2.

### 2.5 The defect

The suite found a real one on its first full run — the tool-failure handoff trigger cannot fire. Section 6.1.

### 2.6 The count

197 tests, `ruff` clean, CI green on both. Section 7.

---

## 4. Individual work log — Harkamal Singh Lubana (1024170396)

I wrote the verification pass over the backend I built in Weeks 3 and 4.

### 4.1 The test harness

`tests/conftest.py`. The decisions in it matter more than its length:

**SQLite in memory, not a Postgres container.** The portable `JSON`/`JSONB` column variant written in Week 2 was written for exactly this, and this is the week it paid. `pytest` stays a single command with no Docker dependency, which is what lets CI run the suite on a plain runner in seconds. Production and staging still get JSONB indexing. The cost is stated in Section 6.4.

**A file-backed database, not `:memory:`.** My first version used `:memory:` with a shared connection pool, and I changed it before writing a single test. With one shared connection a fixture session and a request session are the same transaction, which would have made the suite pass on interleaving that would deadlock or dirty-read against Postgres. A temporary file gives two real connections to one database — the shape production actually has.

**A fresh schema and a fresh `create_app()` per test.** No test can see another's rows, request IDs, published versions or dependency overrides. Test order cannot become load-bearing.

**Settings built explicitly with `_env_file=None`.** The suite must never pick up a developer's local `.env`. A test that passes because someone's machine happens to have `JANMITRA_ADMIN_API_KEY` set is worse than no test.

**Record factories rather than fixtures on disk.** `loan_record()` is a fully rule-backed scheme with an age band, a residency list, a guarded income ceiling and a conditional document; `pension_record()` is a scheme with no rule set at all, published on a checklist and a citation alone. Between them they cover both halves of the catalogue, and both shapes exist in every suite that needs them.

### 4.2 The suites

| Module | Tests | What it pins down |
| --- | --- | --- |
| `test_api_auth.py` | 13 | 401 for a missing or unknown key, 403 for a known key in the wrong role, across every router. The §14 unauthorised-action tests, made real. |
| `test_api_tools.py` | 28 | The four tools end to end over HTTP: citation and version on every factual response, the TTG stopping rule, the trace from conversation event to audit row to service version. |
| `test_api_dashboard.py` | 18 | Sessions, publication and version history, the reviewer's diff, the operator queue with its conversation context, audit filtering. |
| `test_catalogue_service.py` | 17 | Search scoring and stable ordering, append-plus-repoint versioning, the field-level diff. |
| `test_conversation_service.py` | 10 | The TTG clock written once and never back-filled, per-call event numbering, the failure streak. |
| `test_eligibility_answers.py` | 42 | Answer coercion and validation, every comparison operator, `any_of` / `none_of`, document checklists, language fallback. |
| `test_handoff_service.py` | 21 | The full trigger precedence table and the `new → contacted → resolved` walk. |
| `test_model_adapters.py` | 24 | Mock determinism including reproducible failure injection, the failure adapter, the selection factory. |
| `test_resilience.py` | 7 | Degrade-never-corrupt: an unavailable model still queues the handoff, and never leaves a half-written call. |
| `test_seed_records.py` | 6 | The loader refuses unverified records, by name, before touching the database. |

186 tests added to the 11 that existed.

Three of those deserve specific mention, because they test decisions rather than functions:

**The TTG stopping rule (D-44).** A cited match stops the clock; a second match does not move it; a `needs_more_info` result does not start it; a zero-match search does not start it. This is the primary evaluation metric of the project, and it is now impossible to make it flattering by accident.

**The handoff refusal (D-45).** `request_handoff` returns 409 and creates nothing when no deterministic trigger fired. The test asserts the empty queue, not just the status code — the refusal has to be a refusal to *write*, not merely a refusal to reply.

**Degrade, never corrupt (D-49).** The failure adapter is injected through the same dependency the real one uses, so the test exercises the production path. An unavailable summariser still produces a queued handoff carrying the trimmed transcript. A `ModelUnavailable` escaping a dependency maps to 503, not 500.

### 4.3 The defect the suite found

Described in Section 6.1. Three tests document it as `xfail(strict=True)` rather than being deleted or weakened to match the broken behaviour. I have not applied the fix — the reasoning is in 6.1.

### 4.4 What I did not do

I did not write the seed fixtures. `data/` still contains only its README; the flagship scheme is still not encoded as a reviewed record. The `applies_when` blocker that stopped me last week is gone — Dhruv shipped the guard extension and my tests cover it — so the only thing standing between here and the fixtures is the review work itself, which is exactly the work that cannot be shortcut. It is the top of my Week 6 list.

I also did not touch the frontend harness or the voice worker beyond reading them. Their tests are Dhruv's.

---

## 5. Decisions taken this week

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| D-53 | The unit suite runs on SQLite, not a Postgres container | The portable JSON column variant was written for this; `pytest` stays one command and CI needs no service container | Testcontainers; a required local Postgres |
| D-54 | A file-backed SQLite database, not `:memory:` with a shared connection | One shared connection makes a fixture session and a request session the same transaction, hiding concurrency behaviour production would have | `:memory:` with `StaticPool` |
| D-55 | A fresh schema and a fresh application per test | Test order must never become load-bearing | Session-scoped schema with truncation between tests |
| D-56 | Test settings are constructed with `_env_file=None` | A suite that passes because of a developer's local `.env` is worse than no suite | Rely on the default env prefix |
| D-57 | Tests are written against the requirement, not the function | The value is in pinning D-44, D-45 and D-49 down, not in line coverage | Coverage-target-driven testing |
| D-58 | A found defect is recorded as `xfail(strict=True)`, not deleted and not fixed silently | The suite stays green and honest, and the marker fails loudly the moment someone fixes the bug | Weaken the test to match the bug; leave the suite red |
| D-59 | The fix for the tool-failure defect is deferred to a reviewed change, not slipped into the test commit | It is a transaction-boundary change in a shared dependency; it deserves its own review, not a footnote in a test PR | Fix it inline this week |

---

## 6. Problems hit and how they were resolved

### 6.1 The tool-failure handoff trigger cannot fire

**The defect.** Three sites in `app/api/tools.py` increment the conversation's tool-failure streak and then raise `HTTPException` — the 404 for an unknown slug in `check_eligibility` and in `get_documents`, and the 422 for an answer-validation failure. `app/db.py` rolls the session back on *any* exception leaving the request.

So the increment never survives the request that made it. The counter is permanently zero, and `HandoffTrigger.TOOL_FAILURE` from context.md §18.3 is unreachable through the API. A citizen whose answers the agent repeatedly cannot parse is never escalated to a person on that basis — which is precisely the failure mode the trigger exists to catch, and it is the loop I described myself as "closing" in last week's §4.2.

**How it was found.** Not by reading the code — I wrote that code four weeks ago and read it many times since. It was found by asserting the *requirement* over HTTP: call the tool twice with a bad slug, then call `request_handoff` with signals that should fire nothing else, and expect `tool_failure`. It returned 409.

**Confirmed, not assumed.** I temporarily added `await session.commit()` after each `note_tool_failure` and re-ran: all three tests flipped to `XPASS`. Then I reverted `app/api/tools.py` to the committed version — `git status` confirms no application code changed this week.

**Why it is not fixed yet.** The obvious fix commits mid-request inside a dependency whose whole contract is "one session per request, committed on a clean exit". In these three paths nothing else is pending, so committing there is safe today — but that is a property of the current handlers, not a guarantee, and someone adding a write above the failure point later would silently start committing partial work on an error path. The alternatives are a separate short-lived session for the counter, or moving the counter write into the exception handler where the request outcome is already known. That is a design decision about transaction boundaries in a shared dependency, and it belongs in its own reviewed change (D-59). The three `xfail(strict=True)` markers hold the requirement in place until then and will fail the build the moment it is fixed, so it cannot be quietly closed.

**What it says about the four unexecuted weeks.** One real defect, in a path that has no happy-case symptom — the API returns exactly the right status code and exactly the right body; only the invisible side effect is lost. It is a good argument for the rule we set and then broke: nothing counts as done until it has been run.

### 6.2 Three of my own test expectations were wrong, not the code

Worth recording because it is evidence the tests are testing something.

**Search scoring.** I asserted that a scheme whose description mentions a micro enterprise would match "small business loan". It does not — the tokeniser strips stopwords and there is no token overlap. The scorer was right and my expectation was lazy. Fixed the fixture, not the scorer.

**Version isolation.** I asserted that republishing a scheme with different aliases would make an old-alias query return nothing. It still matches, at a lower score, through the scheme's *name* tokens. Again the code was right. I rewrote the test to assert what actually matters — that search reads the current version, that the superseded alias no longer produces the strong alias-grade match, and that the new alias does.

**The guarded question.** I expected `annual-income` to be listed as a missing answer when only `age` was known. It is not, and should not be: its condition is guarded on `occupation`, which is itself unknown, so the engine asks for the guard first. That is the three-valued design from Week 3 behaving exactly as intended — the agent asks for the answer it actually needs next, rather than reading out a question it may not need at all.

In all three cases I changed the test. Recording it because the opposite temptation — adjusting the code until the test I first imagined passes — is how a suite quietly stops being evidence.

### 6.3 The slug pattern rejects short identifiers

Writing synthetic rule sets, `Comparison(var="x", ...)` fails validation: the `Slug` type requires at least three characters. Briefly irritating, then obviously correct — a question id of `x` in a reviewed government record would be a defect. Renamed the synthetic ids and moved on. Noting it only because it is the schema's constraint reaching into a place I did not expect it to, which is what a frozen canonical record is supposed to do.

### 6.4 What SQLite does not cover

Stated plainly so it is not mistaken for coverage we have:

- The `JSONB` variant of the JSON columns is never exercised. The suite runs the portable `JSON` path.
- Concurrent writes are not tested. The `uq_conversation_event_seq` constraint that stops two replicas interleaving events on one call is asserted for correct single-writer numbering only; the race it exists to lose is not simulated.
- The Alembic migration is not applied by the unit suite, which builds the schema from the models directly. A drift between `alembic/versions/001_initial_schema.py` and `app/models` would not be caught.

The third is the one that will bite first. A migration check against a real Postgres belongs in CI as a separate job, and it goes on the Week 6 list.

---

## 7. Deliverables produced this week

- `tests/conftest.py` — SQLite-backed harness standing up the full application with per-test isolation, plus rule-backed and rule-free record factories
- Ten test modules covering access control, the four tool endpoints, the dashboard and operator routes, catalogue search and versioning, conversation state and the TTG clock, the eligibility engine's answer handling and combinators, the handoff trigger table and status walk, the three adapter modes, model-failure degradation, and the seed loader
- 186 tests added; 197 collected in total, 194 passing, 3 `xfail(strict=True)`
- `ruff check .` clean across the package and the suite
- One real defect found, confirmed by experiment, and documented in a form that fails the build when it is fixed
- CI (arriving from Dhruv this week) now runs lint and tests on every push — a green pipeline that means something

---

## 8. Contribution split

| Member | Week 5 contribution |
| --- | --- |
| Dhruv Srivastava (1024170394) | The LiveKit voice worker and Gemini Live agent, the Next.js browser harness and token route, `docker-compose.yml`, the Alembic migration, the `applies_when` guard extension, the seed loader, and the two CI workflows — with the first eleven tests. |
| Harkamal Singh Lubana (1024170396) | The test harness and the verification pass over Weeks 2–4: access control, the tool endpoints, the dashboard and operator routes, catalogue versioning and search, conversation state and TTG, the eligibility engine's answer handling, the handoff trigger table, the adapters and failure degradation, and the seed loader. Found and documented the tool-failure trigger defect. |
| Paras (1024170395) | Individual log maintained in his own journal and not duplicated here. |

---

## 9. Risks reviewed

| Risk | Status this week |
| --- | --- |
| Four weeks of unexecuted code | **Closed.** The backend has been run. 197 tests, one real defect found, CI green on lint and tests. |
| CI deferred past the point the build plan asked for it | **Closed.** Workflows landed this week and the backend job runs `ruff` and `pytest` on every push. |
| Rule model expressiveness (`applies_when`) | **Closed.** The guard extension shipped and is covered by the engine and answer suites. |
| Tool-failure handoff trigger unreachable | **New, open.** Found by the suite this week. Held by three strict `xfail` markers; fix scheduled as a reviewed change in Week 6 (D-59). |
| Seed fixtures still absent | **Open and now the blocking one.** No reviewed scheme record exists, so there is nothing to demo and nothing for an end-to-end voice run to talk about. Top of Week 6. |
| Migration drift from the models | **New, open.** The unit suite builds the schema from the models and never applies Alembic. A Postgres migration job is needed in CI. |
| Telephony / SIP provisioning delay | Unchanged. Still the largest schedule risk. The browser harness now gives us a way to demonstrate the voice path without it, which reduces the demo risk but not the pilot risk. |
| Scope creep | None. No backend feature work this week by deliberate choice. |

---

## 10. Carried into Week 6 — in this order

1. **Seed fixtures.** The initial working set of schemes as hand-reviewed JSON, all `pending_review`, with the flagship fully rule-backed now that guards exist. Nothing else I do matters until there is a record to talk about.
2. **The tool-failure trigger fix**, as its own reviewed change, with a decision on where the counter write belongs relative to the request transaction. The three `xfail` markers come out with it.
3. **A migration job in CI** — apply Alembic to a real Postgres and assert no drift from the models.
4. **An end-to-end run** over the browser harness against seeded data: connect, ask, get a cited answer, check eligibility, request a person. This is the first time the whole system will have been exercised as one thing.
5. **A first Time-to-Guidance measurement** from that run — the metric has been defined and tested since Week 3 and has never once been recorded against a real conversation.
