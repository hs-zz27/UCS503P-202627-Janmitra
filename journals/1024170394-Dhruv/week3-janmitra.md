# Janmitra — Weekly Engineering Journal

## Week 3 — The Deterministic Core: Rule Evaluator, Catalogue, Conversation State, Handoff Triggers

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 18 – 24 August 2026 |
| Member | Dhruv Srivastava (1024170394) |
| Status at end of week | The deterministic core is written: eligibility evaluator, catalogue reads and versioned publication, conversation state and the TTG clock, handoff trigger rules and state machine, audit writer. Still no HTTP endpoints, and nothing has been executed. |

> **On individual logs.** Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.
>
> **On Week 2.** My own Week 2 entry is a shorter record of proposal finalisation and backend planning. The fuller shared Week 2 write-up — the scope-reconciliation decisions D-19 to D-28, the day-by-day log and the risk review — is kept in the team's Week 2 journal, and the cross-references below point there.

---

## 1. Objective for the week

Everything Janmitra says to a citizen with a correctness obligation attached — you qualify, you do not qualify, bring these documents, this came from this source on this date, I am passing you to a person — is supposed to be decided by code we can test, not by a language model. This week was that code.

The order was chosen so that nothing depends on something unwritten:

1. The eligibility evaluator, as pure functions over a rule set and a dictionary of answers: no database, no network, no model.
2. Catalogue reads that can only see published versions, and a publication path that is append-only.
3. Conversation state, including the two timestamps the primary metric is computed from.
4. The handoff trigger rules, in one function, so "when do we hand off" has exactly one answer in the codebase.
5. The audit writer.

We also held to the rule from the build plan: **tools before voice**. None of this week's work knows that a phone call exists. If the voice leg misbehaves later, it cannot be confused with a logic bug here.

---

## 2. Day-by-day activity log

### Day 1 — Boundary cases before the evaluator

Before writing the evaluator we wrote down what the answers *should* be for the flagship scheme — the age boundary at exactly 18, an applicant who has answered nothing, an applicant who has answered everything but one question, an applicant who fails one mandatory condition while another is still unanswered.

That last case decided the design. If a citizen has already failed a mandatory condition, no further question can rescue them, so the evaluator must return a decisive result rather than continue asking. Conversely, if a condition is simply unanswered, the honest answer is *I need to ask you something else*, not *no*.

So the evaluator is **three-valued**: true, false, and unknown, where unknown means nobody has asked yet. Treating a missing answer as false would be the single most damaging bug this system could ship — it would tell a citizen they do not qualify for a scheme when in fact the question was never put to them.

### Day 2 — The evaluator

Written as pure functions. Answers are validated and coerced against the question types first; a validation failure raises rather than degrading into a verdict, because a bad extraction from the model must surface as a validation error and never as a wrong eligibility result.

The evaluator returns a full trace — every condition, whether it passed, failed or is unknown, which answer it depended on, and the sentence from the official source behind it. The agent reads the failing lines back to the citizen. The trace is also what the boundary tests assert against, condition by condition, rather than only checking the final verdict.

### Day 3 — Where the rule model broke, and what we chose to do

Encoding the flagship scheme's real published rules exposed a genuine gap, which is recorded in full in Section 6. In short: some official rules are *conditional on other answers* — a qualification requirement that only applies above a cost threshold that itself differs by sector — and a flat list of conditions cannot express that. We compared three ways out and chose one; the implementation is carried into Week 5.

This is exactly the kind of thing we wanted the journal to record: the design met the real world, the real world won, and the fix is a small extension to the data model rather than a patch in the evaluator.

### Day 4 — Catalogue: reads, search, publication

Reads go only through the version a service currently points at, and only if that version is published. A draft is never visible on a citizen path — that is a stated non-functional requirement, and it is enforced in the query rather than in a caller's discipline.

Discovery is deterministic token matching over name, aliases and description, filtered by category first. No vector database, as decided in Week 1. Two properties we insisted on: category filtering happens before scoring, and ties break on slug so the same query returns the same order on every run. Load tests and the AI evaluation set both depend on repeatability.

Publication writes a new version row and repoints the service; existing versions are never touched. We also wrote the field-level diff the admin review screen will need — it flattens both records to dotted paths so a reviewer sees `rule_set.conditions.0.test.value: 18 → 21` instead of two walls of JSON.

### Day 5 — Conversation state and the TTG clock

Conversation state lives in Postgres, not in the voice worker, which is what allows N identical replicas behind a load balancer. The two metric timestamps are written by the system that owns them: `connected_at` when the call is answered, `first_guidance_at` the first time a grounded, cited answer goes out. `first_guidance_at` is written once and never moved, so a later answer cannot flatter the number.

### Day 6 — Handoff triggers and the state machine

The four deterministic triggers — the citizen asked for a person, tools failed repeatedly, the request is out of scope or nothing matched, agent confidence below the configured floor — live in one function that returns a trigger or nothing at all. The model may *report* signals into it; it does not decide, and it cannot create the record.

Trigger order is not arbitrary: an explicit request for a person outranks every inference the system makes about the citizen. If someone asks for a human, they get a human, regardless of how confident the agent was.

The queue state machine — `NEW → CONTACTED → RESOLVED` — is enforced in code, with an invalid transition raising rather than silently succeeding.

---

## 4. Individual work log — Dhruv Srivastava (1024170394)

I took the four service modules around the evaluator: catalogue, conversation, handoff and audit.

### 4.1 Catalogue

**Reads.** `get_published` and `list_published` join a service to the version it currently points at and require that version's status to be `published`. Both conditions are in the SQL. A draft cannot reach a citizen path even if a caller forgets to filter, which is the only way I am willing to enforce a stated non-functional requirement.

**Search.** Category filter first, then token scoring over name, aliases and description. Tokens are lowercased, stripped of a small stopword list — "scheme", "how", "need", "want", and similar, which carry no signal in a spoken civic request — and scored in tiers: a phrase or alias appearing verbatim in the query scores highest, then overlap with name and alias tokens, then description overlap with a hard ceiling so a long description cannot outrank an actual name match.

Two deliberate properties: the same query returns the same results in the same order every run, with slug as the tie-break; and the whole thing is a single function, so if catalogue growth ever makes token matching the wrong tool, a retrieval layer replaces this function's body without touching a caller.

**Publication.** `publish` creates the service on first publication, computes the next version number from the highest existing one, writes a new immutable row and then repoints `current_version_id`. Nothing existing is modified. Reject and draft handling belongs to the ingestion module and is not written yet.

**Diff.** `diff_records` flattens both payloads to dotted paths and returns before/after per changed path. Recursing through lists by index means a reviewer sees `rule_set.conditions.2.test.value` changed rather than "the conditions array changed", which is the difference between a review that catches a wrong threshold and one that does not.

### 4.2 Conversation

`create`, `get`, `get_active`, `append_event`, `mark_guidance_delivered`, `note_tool_failure`, `clear_tool_failures`, `set_category`, `end`, and a `time_to_guidance` helper.

The parts that matter:

- **`get_active` refuses a conversation that has already ended**, so a stray tool call from a worker that has not noticed the call dropped cannot append to a finished transcript.
- **`mark_guidance_delivered` is idempotent** — it writes `first_guidance_at` only when it is null. TTG measures the *first* grounded answer, and a metric that improves the more you talk is not a metric.
- **`append_event` derives its sequence number inside the transaction** and relies on the unique constraint to reject a concurrent duplicate.
- **`note_tool_failure` and `clear_tool_failures`** maintain the streak counter in the database, because the streak is a handoff trigger and the next request may land on a different replica.

### 4.3 Handoff

`decide_trigger` is one function taking the settings and the observed signals, returning a trigger or `None`. Ordering, and the reasoning for it:

1. **The citizen asked for a person.** Outranks everything. If someone asks for a human they get a human, regardless of how confident the agent was.
2. **Repeated tool failures**, at or above the configured streak length. The system is broken; do not make the citizen keep trying.
3. **Out of scope**, as reported by the agent.
4. **No match** from discovery.
5. **Confidence below the configured floor.**

Returning `None` is a real outcome, not an edge case: it means the agent should keep helping. The endpoint layer turns it into a refusal in Week 4.

`create` accepts a null name and a null phone. A citizen who will not give a number still gets queued, and the operator still sees the category and the conversation context — that was decision D-11 in Week 1 and this is where it becomes code. Blank strings are normalised to null so the queue does not show empty-looking rows that are technically populated.

`update_status` checks an explicit transition table. `NEW` may go to `CONTACTED` or straight to `RESOLVED`; `CONTACTED` may go to `RESOLVED`; `RESOLVED` goes nowhere. An invalid transition raises rather than silently succeeding — a resolved case quietly reopening is a data-integrity bug no operator would ever spot.

### 4.4 Audit

One `record` function that writes an audit row with the current request ID pulled from the context variable, and simultaneously emits a structured log line with the same fields. Two sinks, one call site, no chance of a critical action being in the log but not the table.

### 4.5 What I did not do

No ingestion module. It is Week 6 work in the build plan and depends on the review screen, and I did not want a half-written importer sitting in the tree pretending to be a deliverable.

Nothing this week has been run. Same admission as Harkamal's: no migration, no fixtures, no tests. The database layer has never opened a connection.

## 5. Decisions taken this week

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| D-29 | Eligibility evaluation is three-valued: a missing answer is *unknown*, never false | Telling a citizen they do not qualify because nobody asked is the worst failure this system could have | Two-valued logic treating missing as false |
| D-30 | A definite failure is decisive even while other conditions remain unknown | No further question can rescue a mandatory condition that has already failed; continuing to ask wastes a phone call | Ask every question before deciding anything |
| D-31 | Answers are validated and coerced before evaluation; a validation failure raises | A bad extraction must surface as a validation error, never as a wrong verdict | Coerce leniently and evaluate anyway |
| D-32 | The evaluator returns a per-condition trace, not just a verdict | The agent must be able to say *why*, and boundary tests assert per condition | Return the outcome only |
| D-33 | A document gated on an unanswered question stays in the checklist, marked conditional | On a phone call, "you may also need X" is more useful than silence | Drop unresolved documents |
| D-34 | Discovery is deterministic keyword matching with category filtering first and slug as tie-break | Repeatability is required by both the load tests and the AI evaluation set | Vector search; unordered results |
| D-35 | Catalogue reads see only the currently published version, enforced in the query | A draft must never reach a citizen path, regardless of caller discipline | Filter in the service layer |
| D-36 | Publication is append-plus-repoint; version rows are immutable | Non-destructive versioning is a graded deliverable and an audit requirement | Update in place with a history table |
| D-37 | The version diff is computed on flattened dotted paths | A reviewer needs to see the changed field, not two JSON blobs | Whole-document diff |
| D-38 | `first_guidance_at` is written exactly once | A later answer must not improve the measured TTG | Update on each grounded answer |
| D-39 | All four handoff triggers live in one function, ordered so an explicit request wins | One place to test, one place to change, and the citizen's own words outrank our inference | Trigger checks spread across call sites |
| D-40 | The handoff state machine rejects invalid transitions in code | A resolved case silently reopening is a data-integrity bug an operator would never notice | Trust the dashboard to send valid transitions |
| D-41 | Conditions gain an `applies_when` guard list (design agreed, implementation in Week 5) | Real official rules are conditional on other answers; the flat model cannot express them | Derived question computed by the model; nested expression tree |

---

## 6. Problems hit and how they were resolved

### 6.1 The rule model could not express a real government rule

Encoding the flagship loan scheme, we hit this published requirement: an applicant needs a minimum educational qualification **only** for projects above ₹10 lakh in the manufacturing sector, or above ₹5 lakh in the service sector. The requirement is conditional on two other answers at once, and the threshold itself depends on one of them.

Our flat list of conditions combined by `all_of` / `any_of` / `none_of` cannot say that. We considered three options:

| Option | Verdict |
| --- | --- |
| Ask the agent for a derived answer such as "is this project above the education threshold?" | **Rejected.** It moves a piece of the eligibility rule into the model, which breaks the invariant the whole project rests on. |
| Replace the flat list with a nested boolean expression tree | **Rejected.** Fully general, but it makes a rule set much harder for a human reviewer to read, and human review is the gate that makes the catalogue trustworthy. |
| Give each condition an optional `applies_when` list of guard comparisons, all of which must hold for the condition to apply | **Chosen.** It reads the way the official text reads — "for projects above X in sector Y, the applicant must…" — and it keeps a rule set a flat, reviewable list. |

Semantics agreed: if any guard is false, the condition does not apply and is neutral — skipped in `all_of`, ignored in `any_of`, and skipped in `none_of`. If a guard is unknown, the condition is unknown, and the *guard's* question is what the agent should ask next, not the condition's. An `any_of` group in which every branch turns out to be inapplicable is satisfied, since nothing bars the applicant.

The evaluator currently implements the flat model. The guard extension is scheduled for Week 5 alongside the first seeded fixtures, and until it lands we will not claim the flagship scheme is fully encoded.

### 6.2 Neutral is not the same as true

While specifying the above, we caught a trap: making an inapplicable condition evaluate to *true* works for `all_of` and breaks `none_of`, where a "true" condition means the applicant is barred. Neutral has to mean **ignored by whichever group references it**, not a fixed boolean. Written down before implementation rather than found by a wrong answer later.

### 6.3 Concurrent turn writes

Two replicas appending a turn to the same conversation could both compute the same sequence number. Resolved with the unique constraint from Week 2 plus deriving the sequence inside the transaction, so one write fails loudly instead of two succeeding at the same position.

---

## 7. Deliverables produced this week

- Deterministic three-valued eligibility evaluator with per-condition tracing
- Answer validation and coercion for all five answer types, with range checking
- Next-question selection driven by what the evaluator still needs
- Deterministic document-checklist builder, including conditional entries
- Catalogue: published-only reads, category-filtered deterministic search, append-only publication, field-level version diff
- Conversation state, turn-event sequencing, tool-failure tracking, and the TTG clock
- Handoff trigger rules and the `NEW → CONTACTED → RESOLVED` state machine
- Audit writer with request-ID tagging
- Written specification for the `applies_when` guard extension, with the two rejected alternatives

---

## 8. Contribution split

| Member | Week 3 contribution |
| --- | --- |
| Dhruv Srivastava (1024170394) | Joint boundary-case derivation and the `applies_when` design review. Individually: catalogue service, conversation service and the TTG clock, handoff trigger rules and state machine, audit writer. |
| Harkamal Singh Lubana (1024170396) | Joint boundary-case derivation and the `applies_when` design review. Individually: the eligibility evaluator, answer validation and coercion, next-question selection, document-checklist builder. |
| Paras (1024170395) | Joint boundary-case derivation and the `applies_when` design review. Individual log maintained in his own journal and not duplicated here. |

---

## 9. Risks reviewed

| Risk | Status this week |
| --- | --- |
| Telephony / SIP provisioning delay | Unchanged and still the largest schedule risk. Nothing written this week depends on it, which was the intent. |
| Rule model not expressive enough for real schemes | **Materialised.** Caught early, on the first real scheme, with a chosen fix and two recorded alternatives. Cost is one small schema change plus evaluator work in Week 5. |
| Nothing written so far has been executed | **New and growing.** Three weeks of code exist with no migration, no fixtures, no tests and no CI. Flagged here explicitly; see Week 4's carried-forward list. |
| Scope creep | None this week. Every item built maps to a named requirement or to §18.2 of the build plan. |

---

## 10. Carried into Week 4

The tool surface: `find_service`, `check_eligibility`, `get_documents` and `request_handoff` as plain HTTP endpoints, the model adapter in its three modes, role-based access, and the routers the dashboard will use.
