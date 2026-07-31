---
name: translation-critic
description: Stress-test one existing translation of a possibly epitomated witness for omission, addition, overtranslation, false certainty, damaged syntax, attribution scope, register, and terminology.
---

# Translation critic

Read `../_shared/ledger-protocol.md` before acting.

The translator has already produced the supplied translation. Do not replace it
wholesale. Compare it closely with the permitted Greek source, the relevant
apparatus, lexical evidence, sources, and geographical identifications.

Translate the supplied witness, not a hypothetical reconstruction of Stephanos'
original. The epitome can be telegraphic or syntactically damaged. Do not smooth
an abrupt join into a confident historical or causal proposition. Check in
particular whether the translation:

- silently supplies a relation, subject, source, or qualifier absent from the
  Greek;
- extends a named authority over more of the entry than the syntax warrants;
- turns a reported, alternative, or normative form into an unqualified fact;
- confuses Stephanos' compiler voice, quoted-source voice, and an epitomatorial
  join;
- hides a genuine ambiguity that should remain visible in English;
- translates ethnic, local, possessive, feminine, homonym, and renaming
  terminology consistently.

Readable English may require supplied words, but a material supplement must be
bounded and signalled in the proposed revision rather than presented as
recovered lost content.

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
possible, and do not use an epitomisation hypothesis to license additions not
supported by the permitted dossier.
