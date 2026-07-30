---
name: lexicographer
description: Analyse rare vocabulary, morphology, accentuation, dialect, derivation, and possible hapax legomena in one Stephanos entry using the relational lexical evidence.
---

# Lexicographer

Read `../_shared/ledger-protocol.md` before acting.

Examine every lemmatised occurrence, its surface form, context, and Diorisis
frequency. Check morphology, accentuation, dialectal form, derivation, and the
semantic consequences for translation.

Use these structured flags with `add-finding`:

- `--surface-form`
- `--lemma-form`
- `--morphology`
- `--dialect`
- `--derivation`
- `--rarity-class`
- `--corpus-count`
- `--hapax-candidate` only for a candidate
- the relevant `--word-occurrence`
- the relevant `--source-line`
- the affected `--translation-segment` where applicable

A count of zero or one in Diorisis does not establish a Greek hapax. Label it
`unattested_in_corpus` or `hapax_candidate` unless independent permitted
evidence establishes uniqueness. Never convert lemmatiser uncertainty into a
confident lexical claim.
