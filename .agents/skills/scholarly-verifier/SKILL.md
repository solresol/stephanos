---
name: scholarly-verifier
description: Independently verify every atomic specialist finding, including its claimed witness layer and source relation, and decide separately whether translation revision is required.
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

For each finding, verify separately:

1. the atomic proposition actually stated;
2. the witness or textual layer to which it is attributed;
3. the scope of any named source or parallel;
4. whether the evidence discriminates the proposed explanation from corruption,
   physical loss, interpolation, source compression, or another live
   alternative;
5. whether the accepted scholarly observation requires a change to the existing
   translation.

A claim about the surviving epitome is not automatically a claim about
Stephanos' original. Absence from the epitome is normally weak negative evidence.
Reject or mark `insufficient_evidence` any finding that assigns a local feature
to Hermolaos, a numbered epitomisation stage, a century, or a transmission
centre without typed evidence in the verification dossier. An unresolved choice
between epitomisation and ordinary corruption is an acceptable result.

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

Use `revision_required` only when the translation itself needs a bounded change.
A defensible textual, lexical, source, geographical, or redactional observation
may be `accepted` without requiring translation revision. If a specialist has
combined layer, source, date, form, or location claims that cannot receive one
verdict, do not silently split or repair it: judge the submitted atomicity and
use the rationale to identify the unsupported component.

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
one recorded revision request. Do not mark an entry release-ready when any
accepted finding still presents a recensional hypothesis as a fact about
Stephanos' original.
