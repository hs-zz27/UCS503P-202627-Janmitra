# Service catalogue review

This directory contains one canonical `ServiceRecord` JSON file per service. New and
updated records stay `pending_review` in Git so the repository never claims that a model or
importer performed the required human review.

Before publishing, open [REVIEW.md](REVIEW.md), follow every official source, and compare the
record's description, benefit, eligibility, documents, and steps with that source. Then use
your own name to attest that review:

```powershell
janmitra-seed data --dry-run --confirm-reviewed --actor "Your Name"
janmitra-seed data --confirm-reviewed --actor "Your Name"
```

`--confirm-reviewed` marks pending records verified only in the database version being
published. It does not rewrite the JSON. Re-review the source before every publication,
especially monetary amounts, dates, eligibility thresholds, and state-specific rules.

Never use invented or model-generated values as verified scheme facts. Do not publish a
record when its source is unavailable, ambiguous, expired, or contradicted by a newer
official notice.
