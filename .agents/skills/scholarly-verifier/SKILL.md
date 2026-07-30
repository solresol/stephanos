---
name: scholarly-verifier
description: Independently verify all specialist findings for an earlier fully analysed Stephanos entry and decide whether translation revision is required.
---

# Scholarly verifier

The automation supplies an earlier `snapshot_id` and a running verifier
`run_id`. Read the complete evidence and specialist findings:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py \
  verification-dossier --snapshot-id SNAPSHOT_ID
```

Do not consult Billerbeck discussion, OCR, German translations, or derived
Billerbeck comparisons. Recheck each finding against its typed evidence rather
than accepting the specialist's summary.

Record exactly one verdict for every `finding_id`:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py record-verdict \
  --run-id RUN_ID \
  --finding-id FINDING_ID \
  --verdict accepted \
  --rationale 'The linked source line and lexical occurrence support the claim.'
```

Verdicts are `accepted`, `rejected`, `insufficient_evidence`,
`revision_required`, or `superseded`.

When one or more findings require a changed translation, first record those
verdicts and then create a relational revision request:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py request-revision \
  --run-id RUN_ID \
  --finding-id FINDING_ID \
  --requested-change 'Specific bounded correction for the existing translator.'
```

Finish only after every finding has a verdict:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py \
  complete-verification \
  --run-id RUN_ID \
  --overall-verdict accepted \
  --summary 'Independent verification summary.'
```

Add `--release-ready` only when every finding is accepted and the translation
requires no revision. A revision-required overall verdict must have at least
one recorded revision request.
