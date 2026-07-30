---
name: source-critic
description: Verify cited authors, works, quotations, fragment references, and parallels for one Stephanos entry using structured citation and quotation evidence.
---

# Source critic

Read `../_shared/ledger-protocol.md` before acting.

Check each structured citation mention against the associated citation unit and
resolved quotation passage. Distinguish author identification, work
identification, passage numbering, direct quotation, paraphrase, verbal
parallel, and an unresolved traditional attribution.

Use these structured flags with `add-finding`:

- `--cited-author`
- `--cited-work`
- `--cited-reference`
- `--proposed-identification`
- `--parallel-reference`
- one or more `--citation-mention`
- one or more `--quote-passage`
- the relevant `--source-line`

Do not claim that a source is verified merely because an extraction model
created a citation row. A missing or unresolved passage is a negative or
uncertain result, not permission to invent a reference.
