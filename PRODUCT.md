# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Rural citizens in India who need government support (farming, pensions, housing, food, health, work, loans, insurance) but cannot easily find or read official scheme information. They describe a situation in their own words and language rather than naming a scheme. Secondary audiences: the project's course examiner and operators who handle queued human-help requests.

## Product Purpose
Janmitra is a voice-first civic-guidance assistant. A citizen speaks, and Janmitra retrieves matching central-government schemes, explains benefits and next steps aloud, checks eligibility deterministically where a published rule set exists, lists documents to prepare, and queues a human handoff when self-service is not enough. Success is a citizen leaving a call knowing which scheme applies and what to do next.

## Positioning
Speech in, grounded answer out: the model explains facts retrieved from a published, reviewer-attested catalogue with citations, and never decides eligibility itself; a deterministic engine does. It answers in the citizen's spoken language (English, Hindi, Punjabi and transliterated speech are measured).

## Operating Context
A browser call screen presented as a phone call, connected over LiveKit to a Gemini Live native-audio worker, backed by a FastAPI service and PostgreSQL. A UCS503P course project at Thapar Institute of Engineering and Technology, evaluated at end-semester.

## Capabilities and Constraints
- 18 published central schemes across loan, insurance, grant, pension, banking and rural employment; 5 carry deterministic rule sets.
- Four tools: find_service, check_eligibility, get_documents, request_handoff.
- Browser channel only; no telephone or SIP access yet. A handoff queues an operator request; it does not transfer a live call.
- Live voice depends on Gemini Live capacity; free-tier limits close some calls.
- Never requests OTPs, PINs, passwords, full bank account or Aadhaar numbers.

## Brand Commitments
- Name: Janmitra (spelled this way in the product and the report).
- Voice: plain, calm, respectful; short sentences; never labels people by poverty, literacy or debt.
- Politically neutral: no party or government campaign slogans.

## Evidence on Hand
- Scheme catalogue: code/backend/data/*.json (names, aliases, categories, citations).
- Measured results: project-report-final/main.tex (100% test pass rate, 97.1% retrieval recall@3, 100% on Hindi, Punjabi and transliterated queries).
- No user testimonials, partner logos, usage numbers or photographs of real users exist; do not fabricate any.

## Product Principles
- Grounded before fluent: a spoken answer is only as good as the record behind it.
- Meet people in their own language and words, not in scheme names.
- Say what is uncertain; never promise approval, money or a completed action.
- Always leave a route to a human.

## Accessibility & Inclusion
Users may have low literacy and use low-end phones. Keep text large and high-contrast, honour reduced-motion preferences, and keep every call control keyboard- and screen-reader-operable.
