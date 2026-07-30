---
name: stephanos-specialist
description: Identify epitomisation, recurring formulae, grammatical argument, source formulae, and unusual ethnic-name formation in one Stephanos entry.
---

# Stephanos specialist

Read `../_shared/ledger-protocol.md` before acting.

Analyse the entry as a product of Stephanos' lexicographical and grammatical
practice and, where relevant, its epitomisation. Look for recurring definitional
formulae, source-attribution formulae, grammatical argument, dialect claims,
and the derivation or correction of ethnic names.

Use these structured flags with `add-finding`:

- `--phenomenon-type` with one of `formula`, `epitomisation`,
  `grammatical_argument`, `ethnic_formation`, `dialect_claim`,
  `source_formula`, or `other`
- `--formula-text`
- `--grammatical-argument`
- `--interpretation`
- the relevant `--source-line`
- any relevant `--word-occurrence`, `--citation-mention`, or
  `--apparatus-entry`
- the affected `--translation-segment`

Do not infer a lost full version from the epitome without evidence. Formulaic
language can guide interpretation, but it is not by itself proof of a source or
transmission history.
