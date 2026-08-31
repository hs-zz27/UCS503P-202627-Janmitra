# Janmitra — Weekly Engineering Journal

## Week 3 — The Deterministic Core: Rule Evaluator, Catalogue, Conversation State, Handoff Triggers

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Week | 18 – 24 August 2026 |
| Member | Harkamal Singh Lubana (1024170396) |
| Status at end of week | The deterministic core is written: eligibility evaluator, catalogue reads and versioned publication, conversation state and the TTG clock, handoff trigger rules and state machine, audit writer. Still no HTTP endpoints, and nothing has been executed. |

> **On individual logs.** Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.

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

## 4. Individual work log — Harkamal Singh Lubana (1024170396)

I owned the eligibility engine this week — the module the project's correctness claim rests on.

### 4.1 Shape of the module

Pure functions over a `RuleSet` and a dict of answers. No database session, no HTTP, no model adapter, nothing to mock. Every test is a plain function call, which is what allows the boundary suite to be exhaustive without being slow.

Four entry points:

- `validate_answers(questions, answers)` — coerce and range-check.
- `evaluate(rule_set, answers, language)` — the verdict plus the full trace.
- `next_questions(rule_set, answers, language)` — what the agent should ask next.
- `build_document_checklist(record, answers, language)` — the checklist (this one takes the whole record, since documents live outside the rule set).

### 4.2 Three-valued evaluation

`evaluate_comparison` returns `True`, `False` or `None`, where `None` means the answer it needs is absent. Combination follows the decision groups:

- `all_of` — any false condition is a failure; any unknown condition is undecided.
- `none_of` — any true condition is a failure; any unknown is undecided.
- `any_of` — decisive only when every branch is known. If none is true but some are unknown, the group is undecided; if none is true and all are known, the group fails.

Then: any definite failure gives `not_eligible`; otherwise any undecided condition gives `needs_more_info`; otherwise `eligible`. The result carries `failed_conditions` so the agent can name the reason, and `missing_answers` so it knows what to ask.

That last list is derived from the conditions that were undecided, not from the questions that are simply absent from the dict. The difference matters: a rule set can declare a question that no condition currently references, and asking a citizen a question that cannot change the outcome is wasted time on a phone call.

### 4.3 Answer validation

Each answer type has its own coercion, and all of them are strict where being lenient would be dangerous:

- **Boolean** accepts real booleans and the strings yes/no/true/false. Nothing else.
- **Integer and number** reject booleans outright — Python would otherwise happily treat `True` as `1` and silently satisfy an age condition.
- **Enum** requires membership in the declared options.
- Declared `min`/`max` are enforced during coercion, so an implausible transcription like an age of 900 fails validation instead of producing a confident verdict.

Unknown keys are ignored rather than rejected, because a voice transcript will carry detail the rule set does not use, and refusing the whole call over an extra field would be the wrong trade.

Failures are collected and raised together as one error listing every problem, so the caller does not have to fix them one round-trip at a time.

### 4.4 Ordering comparisons

`gt`, `gte`, `lt`, `lte` and `between` raise if handed a non-number, including a boolean. An ordering comparison against a string would otherwise either throw somewhere unhelpful or, worse, compare lexicographically and produce a confident wrong answer.

### 4.5 The document checklist

Deterministic selection, sharing the same comparison evaluator as the rule engine so the two can never disagree about what an answer means. A document whose gate is false is dropped; a document whose gate is *unknown* stays in the list marked `conditional`, with the question it depends on named. On a phone call, "you may also need your caste certificate, depending on your category" is more useful than silence.

### 4.6 Language handling

One helper picks a language off a localised string and falls back to English. That fallback is a correctness decision, not laziness: the record holds the verified text, and the model translates it for the citizen at speaking time. A missing Hindi translation must degrade to English text that still gets explained — it must never become a missing fact.

### 4.7 Where I stopped

The evaluator implements the flat condition model. The `applies_when` guard extension from Section 6.1 is specified but not written, and until it is, the flagship scheme cannot be fully encoded. I would rather have that stated in a journal than have a fixture that quietly drops the rule it cannot express.

I also wrote no tests yet, which by our own standing rule means none of this is done. That is the top of my Week 5 list, ahead of any new feature.

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
