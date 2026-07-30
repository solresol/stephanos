# Scholarly translation workflow

This workflow adds six independent specialist readings and one independent
verification pass around the existing translation pipeline. It does not create
a replacement translator.

## Copyright boundary

The scholarly snapshot trigger accepts only current public Greek source
versions whose `source_document` is `meineke` or `kiesling`. The dossier builder
uses an explicit table allow-list and never reads:

- `billerbeck_german_pages`
- `lemma_billerbeck_german_refs`
- Billerbeck OCR or translated discussion
- `text_pair_differences`

The Kappa cohort is selected using the Greek initial, entry number, version,
and non-empty Meineke reference. This gives the 317 official epitome entries
and excludes the additional reconstructed Κάλαμος without using Billerbeck
content as a selector.

## Relational identity

`scholarly_entries` is the editorial/publication unit. An entry has one or more
`scholarly_entry_witnesses`, each linked to a concrete `assembled_lemmas` row
and a role such as `full`, `epitome`, or `parisinus`. A witness then links to a
permitted immutable Greek source version.

An analysis snapshot combines:

- one entry witness;
- one permitted Greek source-text version;
- one completed run from the existing translator; and
- an input hash.

The headword is display metadata and is never the identity key.

## One automation

One recurring Codex automation performs at most one new analysis entry and one
earlier verification entry per invocation:

1. Refresh the Kappa entries, source/translation snapshots, and skill versions.
2. Select the earliest current snapshot with an unfinished specialist job.
3. Run each unfinished specialist skill independently:
   - `textual-critic`
   - `lexicographer`
   - `source-critic`
   - `historical-geographer`
   - `stephanos-specialist`
   - `translation-critic`
4. Select an earlier snapshot whose six specialist jobs have completed but
   whose current verifier job has not.
5. Run `scholarly-verifier`.

If there is no analysis work, the invocation may still drain one unverified
entry. Leases expire after twelve hours, so an interrupted invocation resumes
without duplicating completed work.

## Installation

Apply the migration once:

```bash
psql -v ON_ERROR_STOP=1 -d stephanos \
  -f migrations/20260730_scholarly_workflow.sql
```

Register skills and populate the current Kappa snapshots:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py bootstrap-kappa
```

Inspect queue state:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py status
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py next-analysis
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py next-verification
```

## Ledger rules

- One `scholarly_findings` row contains one independently verifiable claim.
- Specialist-specific data belongs in the corresponding one-to-one subtype
  table.
- Evidence belongs in typed junction tables with concrete foreign keys or
  source-validating database triggers.
- No scholarly workflow table contains a JSON or array column.
- A specialist may complete with an explicit negative result.
- The verifier records one verdict per finding and does not rewrite the
  specialist's claim.
- A `revision_required` verdict must be connected to a relational translation
  revision request. The request remains an input to the existing translator;
  it is not a second translation system.

## Adding a full and epitome witness

Both witnesses belong to the same `scholarly_entries` row. Add separate
`scholarly_entry_witnesses` rows with `witness_role_code = 'full'` and
`witness_role_code = 'epitome'`, each pointing at its own
`assembled_lemmas.id`. Never merge them because the headword strings happen to
match.
