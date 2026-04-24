# Translation Guidance Plan

## Purpose

Move the current spreadsheet-based translation guidance into the Stephanos
application and database so that:

- guidance rules are first-class project data, not ad hoc prompt text
- editing is restricted to authenticated users
- active guidance is visible publicly in read-only form
- rule changes produce explicit backlog work instead of silent rewrites
- AI matching against the Greek corpus can run incrementally within token budget

This plan is driven by the three spreadsheets currently in `~/Downloads` plus
the 2026-04-23 meeting transcript:

- `Preferred Glosses.xlsx` (`66` rows)
- `Preferred Translations of Formulae.xlsx` (`28` rows)
- `Preferred Translations of Proper Nouns.xlsx` (`58` rows)

## Working Distinctions

The transcript makes three operationally different kinds of rule clear:

1. Proper-noun preferences
   These are close to global normalization rules. If the preferred rendering of
   a name changes, we usually want a consistent search-and-replace style update.

2. Formula preferences
   These are strong translation-scaffolding rules. They should be detected
   before translation and supplied to the translator as structured guidance.

3. Gloss preferences
   These are advisory defaults, not mandatory global replacements. They should
   help the model and the reviewer, but they must not silently overwrite
   context-sensitive human decisions.

The system has to preserve those distinctions all the way through import,
matching, backlog creation, and retranslation.

## Design Principles

- The application database becomes the canonical home for guidance after the
  initial import.
- Spreadsheet import is a seed workflow, not the long-term source of truth.
- Public read access is allowed; write access is authenticated only.
- Deletes are logical retirements underneath, even if the UI exposes "delete".
- Existing reviewed/canonical translations are never rewritten in place.
- Rule changes must create explicit backlog items for follow-up.
- Matching and retranslation are queued and incremental.

## Fit With Existing Repo Architecture

This work should reuse existing Stephanos patterns rather than inventing a
parallel system:

- authenticated web-side write actions in the review CGI
- append-only local review logs that import into PostgreSQL
- PostgreSQL as the canonical publication data store
- queue-driven background work for translation and analysis
- public pages generated from PostgreSQL-backed read models

## Proposed Phases

### Phase 1: Canonical Storage

- Add PostgreSQL tables for guidance rules, revisions, match results, scan
  queue items, and human backlog items.
- Seed the three spreadsheets into the new tables.
- Preserve workbook/sheet/row provenance for the imported rules.

### Phase 2: Read Models

- Generate public read-only listings for active rules.
- Add protected edit-side views for searching, filtering, and auditing the
  rules.
- Show which rules currently apply to a lemma once matching data exists.

### Phase 3: Authenticated CRUD

- Add create/update/retire/reactivate flows for the guidance tables.
- Track the logged-in user on every change.
- Record append-only revisions so older translation decisions remain auditable.

### Phase 4: Incremental Matching

- Add per-lemma/per-rule match rows.
- Add a queue for corpus scanning so rules can be checked incrementally.
- Use deterministic matching where possible.
- Use AI only where exact or fuzzy matching is not enough, especially for
  formulae.

### Phase 5: Backlog and Retranslation

- When a rule changes, create backlog items for affected lemmas.
- Auto-queue fresh machine translations where safe.
- Create review backlog instead of silent mutation for reviewed/canonical text.
- Make backlog state visible so no follow-up work is lost.

### Phase 6: Analytics

- Add rule-frequency reporting.
- Count formula usage by source bucket or version.
- Support later paper-oriented analysis without changing the operational data
  model.

## First Implementation Slice

This first pass does not try to finish the entire feature. It lays down the
foundation needed to build the rest safely:

- high-level plan document
- detailed design document
- PostgreSQL migration for guidance, queue, match, and backlog tables
- bootstrap schema update for fresh databases
- spreadsheet seed importer CLI
- queue-enqueue CLI for incremental matching work

This slice does **not** yet include:

- the protected CRUD web UI
- the AI/deterministic matching worker
- translation prompt integration
- public pages for the new rules
- automatic backlog expansion from every rule edit

## Immediate Next Steps After This Slice

1. Build protected edit-side pages for browsing and editing rules.
2. Add a worker that consumes the scan queue and writes match results.
3. Surface matched rules in the lemma review/export layer.
4. Convert rule changes into explicit backlog items for translation refresh and
   human review.
5. Feed matched rules into the translation pipeline as structured pre-translation
   guidance.
