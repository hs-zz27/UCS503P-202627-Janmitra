# Janmitra — Weekly Engineering Journal

## Week 1 — Ideation, Problem Selection & Proposal Finalisation

| Field | Value |
| --- | --- |
| Course | UCS503 / UCS503P — Software Engineering |
| Institute | Thapar Institute of Engineering and Technology, Patiala |
| Project | Janmitra — a voice-first civic scheme guidance platform |
| Team | Dhruv Srivastava (1024170394), Harkamal Singh Lubana (1024170396), Paras (1024170395) |
| Status at end of week | Project idea finalised; proposal written and submitted. No implementation started, by design. |

> **Note on this being a shared journal.** All three team members submit an identical Week 1 journal. Week 1 contained no separable engineering tasks — the entire week was joint ideation, problem selection, scope negotiation and proposal authoring, carried out together across six working days, where every decision recorded below was argued and agreed by all three of us. Producing three differing narratives would misrepresent how the work actually happened. From Week 2 onward, once implementation tasks are separable, each member's journal will additionally carry an individual work log.

---

## 1. Objective for the week

The goal for Week 1 was **not** to write code. It was to choose a problem worth fifteen weeks of engineering effort, and to convert it into a proposal that is specific enough to build against and honest enough to be graded on.

Concretely, we set out to:

1. Select a problem domain with a real, non-hypothetical user and a clear failure mode today.
2. Establish that the problem is a *software engineering* problem, not just an AI demo — i.e. that it has a workflow, a data lifecycle, correctness requirements and a scalability story.
3. Define what "done" means for one semester, in terms of demonstrable user journeys rather than a feature list.
4. Decide, in advance, what we are deliberately **not** building, and record each cut with its alternative.
5. Define measurable evaluation criteria before any code exists, so the metrics cannot be retrofitted to whatever we happen to build.
6. Produce and submit the formal proposal.

---

## 2. Day-by-day activity log

### Day 1 — Problem-space exploration

We started from the requirement that the project must address a real access problem rather than a hypothetical one. We converged on public welfare access in rural and tier-city India because the failure is well documented and observable: scheme information exists, but it is fragmented across formal webpages, PDFs and departmental notices, written at a reading level the intended beneficiary often cannot use.

We broke the problem down into five distinct failure modes rather than treating "access is hard" as one blob:

1. **Fragmentation** — information is scattered and written for administrators, not citizens.
2. **Language and dialect barriers** — the citizen may speak comfortably in a regional language or dialect while every portal assumes formal Hindi or English *reading* ability.
3. **Low self-service comfort** — many users prefer speaking over typing, and many do not own or use a smartphone with a data connection.
4. **Eligibility uncertainty** — a citizen cannot easily establish whether they qualify or what documents are required without an in-person visit.
5. **No graceful fallback** — when self-service is insufficient, there is no low-effort route to a human.

Separating these mattered later, because each one maps to a different component in the final design. Item 5 in particular is the one most systems ignore, and it became a first-class feature of ours rather than an afterthought.

### Day 2 — Framings considered and rejected

Before settling on a voice-first guidance layer, we discussed and rejected several framings of the same problem:

| Framing considered | Why we rejected it |
| --- | --- |
| A web or mobile scheme-aggregator portal | Reproduces the exact barrier we are trying to remove. It presumes smartphone ownership, a data connection, and reading fluency — the three things our user often lacks. |
| A text-only chatbot | Typing is the friction point for this user. Text is useful as a fallback, not as the primary channel. |
| An "ask anything about government schemes" RAG chatbot over a scraped corpus | Unverifiable output, no correctness story, and the engineering degenerates into prompt tuning. It also cannot be graded on workflow, data versioning or scalability. |
| A full grievance-filing and case-lifecycle system | Enormous scope, requires real institutional integration we cannot obtain, and does not fit a 15-week course build. Retained only as a stretch goal. |

What survived was a narrower and more defensible framing: **a guidance layer over a verified, human-reviewed catalogue, reachable by voice, that knows its own limits and hands off to a human when it reaches them.**

### Day 3 — Converging on Janmitra and fixing the positioning

We wrote the positioning statement early and deliberately, because it constrains every later decision:

> Janmitra is a guidance layer. It does not make official eligibility decisions, does not submit applications, and does not represent a government authority.

This single sentence resolved several arguments in advance. It rules out anything that looks like an official determination, it forces a visible disclaimer in the citizen experience, and it justifies why a deterministic rule engine — not the language model — owns the eligibility verdict.

We then defined success as **three complete journeys** rather than as a feature list:

1. **Guidance journey** — citizen describes a need, finds a scheme, answers a few questions, receives an eligibility pre-check, a document checklist and an official source link.
2. **Handoff journey** — the request is out of scope or the citizen asks for a person; the system captures a name, an optional phone number and a spoken issue summary, and queues it for a human operator with full context.
3. **Ingestion journey** — an admin imports an approved source, reviews the AI-extracted draft, and publishes a new version without overwriting the previous one.

Defining success as journeys, not features, was a conscious choice: a journey either works end to end in a demo or it does not, so it cannot be partially claimed.

### Day 4 — Deciding where AI belongs, and where it must not

We spent a full day on this, because it is the difference between a graded software engineering project and a chatbot demo.

We restricted generative AI to four jobs where natural-language flexibility is genuinely required: intent extraction into typed actions (`find_service`, `check_eligibility`, `request_handoff`), multilingual explanation of already-verified facts, escalation detection, and AI-assisted field extraction during ingestion.

Everything with a correctness obligation was made deterministic: eligibility rules, document-checklist selection, source and version selection, handoff triggering and handoff-record creation, and audit events.

The invariant we agreed on and wrote into the proposal:

> The model can never publish a record, decide eligibility, or create a handoff record directly. Every such action passes through a validated backend tool, and model output must pass schema validation before any tool consumes it.

This is what makes the critical behaviour unit-testable, and it is the argument we will make at every checkpoint.

### Day 5 — Scoping and architecture

**Catalogue size, flagship scheme, and deliberate cuts.** We sized the catalogue explicitly rather than leaving it open: **three categories — loan, banking / financial-inclusion, grant — with 3–4 real schemes each, roughly 9–12 service records.** Exactly one **flagship scheme** (whichever has the clearest published eligibility rules) receives the complete deterministic eligibility engine; the rest support discovery, explanation, citation and document checklist.

The reasoning: breadth across three genuinely different scheme types proves the data model and discovery generalise, while a single flagship eligibility engine proves the rule evaluator works, without multiplying rule-engineering effort across a dozen schemes and finishing none of them.

We then wrote down thirteen deliberate cuts with a named alternative for each — crawler, general scraping, OCR, vector DB / RAG, full grievance lifecycle, telephony, all-language support, per-scheme eligibility, microservices, Kubernetes, multi-tenancy, a full observability platform, and any handling of sensitive identity data. These are recorded as scope boundaries with future-work labels, not as omissions to be discovered later by a reviewer.

We also recorded eight implementation shortcuts — one canonical service record, snapshots instead of a crawler, typed tool calls instead of open-ended answers, category as a first-pass filter, one generic JSON rule evaluator, one application with three roles, an interchangeable real/mock/failure model adapter, and a stable local demonstration mode.

**Architecture sketch and data model.** We settled on a **modular monolith** with six modules — conversation, catalogue, eligibility, ingestion, handoff, audit — behind a replicable API, with Postgres holding services, versions, handoff requests, conversations and audit logs, and source snapshots stored alongside. Microservices were rejected explicitly: they add operational cost without adding any evidence the course is grading, and the monolith is still horizontally replicable because conversational state lives outside the application process.

The minimal data model was fixed on this day: `service`, `service_version`, `eligibility_rule`, `source_snapshot`, `handoff_request`, `conversation`, `audit_event`, with handoff states `NEW -> CONTACTED -> RESOLVED`. We also produced the system architecture diagram included as Figure 1 of the submitted proposal.

### Day 6 — Evaluation criteria and proposal submission

**Evaluation criteria, defined before any code exists.** We deliberately defined metrics this week so they cannot be reverse-engineered from whatever we end up building.

- **Primary — Time-to-Guidance (TTG):** time from session connect to a grounded, cited answer. The target median is to be *established* from a validation run, not claimed in advance.
- **Secondary:** citation correctness rate, eligibility-tool accuracy on boundary cases, handoff precision/recall on a small labelled set, user-rated clarity (1–5), and availability during test windows.
- **Scalability:** measured on the software we own, using a mock model adapter, reporting throughput, p50/p95/p99, error rate, resource use, the first bottleneck found, one applied fix, and a before/after comparison. Real-model latency and cost are reported separately and never extrapolated.

We agreed to state capacity in the honest form — "sustained X sessions within threshold Y; component Z was the bottleneck; after change Q it improved by N%" — rather than as an unqualified claim.

**Proposal authoring and submission.** We wrote, reviewed and submitted the formal proposal covering: higher-order goal, time-to-value, problem statement, proposed solution, solution approach, architecture diagram, evaluation criteria, pilot validation plan, scalability, engine-availability heuristic, scope and deliverables, and risks with mitigations. Submitted **10 August 2026** to Dr. Raghav B. Venkataramaiyer.

---

## 3. Decisions taken this week

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| D-01 | Voice-first, with text as fallback | The target user speaks more comfortably than they read or type | Text-first chatbot; web portal |
| D-02 | Guidance layer only — no official decisions, no application submission | Keeps the system honest, legally safe, and gradeable on workflow rather than authority | Full application-filing system |
| D-03 | Success defined as three complete journeys | A journey works end to end or it does not; a feature list can be half-claimed | Feature checklist |
| D-04 | Verified, human-reviewed catalogue with versioned publication | Creates a real data lifecycle and makes citations provable | Live scraping; unversioned overwrite |
| D-05 | Deterministic rule engine owns eligibility; the model never decides | Makes critical behaviour testable and explainable | LLM-judged eligibility |
| D-06 | Typed backend tool calls; model explains, backend supplies facts | Removes hallucination risk from factual answers | Open-ended generation over a corpus |
| D-07 | Structured Postgres/JSON lookup instead of a vector DB and RAG | ~9–12 curated records do not justify a retrieval stack or its evaluation burden | Vector database + RAG |
| D-08 | Three categories x 3–4 schemes, one flagship eligibility engine | Proves generality and depth without multiplying rule work | One scheme only; all schemes fully ruled |
| D-09 | Category-first discovery before free-form intent extraction | More reliable for vague, non-technical phrasing than open-ended NLU alone | Pure NLU intent detection |
| D-10 | Human handoff as a first-class feature, framed as a helpline transfer | Matches the user's existing mental model; ticket/case framing does not | Digital ticket system; no fallback |
| D-11 | Phone number optional in handoff | Trust barrier; operator still has conversation context and category | Mandatory contact capture |
| D-12 | Modular monolith with six modules | Same replicability, far lower operational cost, easier to test | Microservices; Kubernetes |
| D-13 | One application, three roles, three seeded accounts | Avoids spending weeks on auth and org management | Registration, OAuth, password reset |
| D-14 | Interchangeable model adapter with real / mock / failure modes | Enables repeatable load tests and failure testing without per-call cost | Real model in all tests |
| D-15 | Stable demonstration mode with local corpus and recorded voice fallback | The live demo must not depend on a government website being reachable | Live source fetch during demo |
| D-16 | Metrics defined before implementation | Prevents retrofitting metrics to whatever gets built | Define metrics at the end |
| D-17 | No Aadhaar, bank details, OTPs or real sensitive data anywhere | Privacy by construction; synthetic and anonymous demo data only | Realistic personal test data |
| D-18 | LiveKit retained rather than cut | The team already has working experience with LiveKit worker management, turn detection and session handling, so it carries no extra risk for us | Simpler audio stack |

---

## 4. Deliverables produced this week

- Finalised problem statement with five itemised failure modes
- Product definition and positioning statement
- Three semester success journeys
- Catalogue sizing and flagship-scheme strategy
- Generative-AI boundary (four permitted uses) and the deterministic component list
- Thirteen deliberate cuts, each with a named semester alternative
- Eight implementation shortcuts
- System architecture diagram and the minimal data model
- Evaluation criteria: primary TTG metric, five secondary metrics, and the scalability testing method
- Ten functional requirements (FR-01 … FR-10) and six non-functional requirements
- Risk register with mitigations
- Eight-step demo script
- `UCS503_Janmitra_Proposal.pdf`, submitted 10 August 2026
- Internal lean scope document v0.4 ("semester-build scope")

---

## 5. Contribution split

| Member | Week 1 contribution |
| --- | --- |
| Dhruv Srivastava (1024170394) | Joint — problem selection, scope negotiation, architecture discussion, proposal review |
| Harkamal Singh Lubana (1024170396) | Joint — problem selection, scope negotiation, architecture discussion, proposal review |
| Paras (1024170395) | Joint — problem selection, scope negotiation, architecture discussion, proposal review |

All Week 1 work was carried out together across the six working days listed above. No task in this week was independently separable, which is why this journal is identical for all three members. Individual work logs begin in Week 2.

---

## 6. Risks identified

| Risk | Mitigation agreed this week |
| --- | --- |
| Data privacy / consent | No Aadhaar numbers, bank details or OTPs stored; handoff contact information optional and minimal |
| Rural-user adoption | Voice-first design, short spoken confirmations, handoff framed as a familiar helpline transfer |
| Evaluation measurement ambiguity | Define connect/response timestamps and handoff trigger conditions **before** development begins |
| Scope creep across a 15-week timeline | Explicit non-goals and cuts recorded as ADRs and reviewed at every checkpoint |
| Operational failure during demo or pilot | Locally seeded stable demonstration mode: verified corpus, source snapshots, recorded voice fallback |
| Divergence between the submitted proposal and the internal lean scope | Reconcile explicitly in Week 2 and confirm the governing scope with the mentor |
