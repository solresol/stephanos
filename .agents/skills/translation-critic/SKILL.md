---
name: translation-critic
description: Stress-test one existing AI translation for omissions, additions, overtranslation, false certainty, misconstrued syntax, register, and inconsistent terminology.
---

# Translation critic

Read `../_shared/ledger-protocol.md` before acting.

The translator has already produced the supplied translation. Do not replace it
wholesale. Compare it closely with the permitted Greek source, the relevant
apparatus, lexical evidence, sources, and geographical identifications.

Use these structured flags with `add-finding`:

- `--issue-type` with one of `omission`, `addition`, `overtranslation`,
  `false_certainty`, `terminology`, `syntax`, `register`, `proper_name`,
  `geography`, or `textual_reading`
- `--source-phrase`
- `--translation-phrase`
- `--proposed-revision`
- the relevant `--source-line`
- the affected `--translation-segment`
- any other typed evidence supporting the criticism

Prefer a bounded correction to stylistic rewriting. Record uncertainty where
the Greek or apparatus permits more than one rendering. Do not mark a
translation defective merely because another idiomatic English version is
possible.
