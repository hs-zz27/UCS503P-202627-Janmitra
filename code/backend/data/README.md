# Reviewed service data

Place one canonical `ServiceRecord` JSON file per service in this directory. Records must
carry `verification_state: verified` and a named `verified_by` before the seed command will
publish them.

```powershell
janmitra-seed data --dry-run
janmitra-seed data --actor "reviewer-name"
```

Never use invented or model-generated values as verified scheme facts.
