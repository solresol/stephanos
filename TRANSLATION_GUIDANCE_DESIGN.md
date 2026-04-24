# Translation Guidance Detailed Design

## Overview

The new guidance layer introduces four connected concerns:

1. Canonical rule storage
2. Authenticated rule change history
3. Incremental matching of rules against Greek source text
4. Explicit backlog follow-up when rules change

The main goal is to stop treating guidance as external spreadsheet knowledge and
instead make it part of the same auditable, queryable workflow as translations,
commentary, and entity review.

## Terminology

### Guidance Rule

A single preferred translation policy item.

Examples:

- a proper noun with a preferred English form
- a recurring Greek formula with a preferred English rendering
- a Greek lexeme with a preferred default gloss

### Rule Revision

An append-only snapshot of a rule at the moment it was created, updated,
retired, or reactivated.

### Match

The recorded result of checking whether a given rule applies to a given lemma's
current source text.

### Scan Queue Item

A queued request to evaluate one rule against one lemma/source-text version.

### Backlog Item

A human- or system-facing follow-up task created because a rule changed or a
match result requires translation review.

## Rule Semantics

### Proper Nouns

- default application mode: `replace`
- operational meaning: strong normalization preference
- preferred handling: deterministic/entity-backed matching first
- downstream effect: safe to propose broad translation reruns when changed

### Formulae

- default application mode: `required`
- operational meaning: strong translation scaffolding
- preferred handling: candidate prefilter plus AI adjudication
- downstream effect: should be injected into pre-translation context

### Glosses

- default application mode: `advisory`
- operational meaning: preferred default wording, not a universal replacement
- preferred handling: deterministic phrase/lemma detection first, AI fallback
- downstream effect: should inform drafts and reviewer UI, but not trigger
  silent replacement of reviewed text

## Data Model

### `translation_guidance_rules`

Current canonical state for each rule.

Key columns:

- `rule_key`: stable internal key used by scripts/importers
- `rule_code`: optional human code such as a future `Gabe 7`
- `kind`: `gloss`, `formula`, or `proper_noun`
- `label`: the Greek form/pattern/name as displayed
- `normalized_label`: normalized lookup form used by scripts
- `preferred_translation`: the preferred English rendering when one has been set
- `word_class`: workbook category or later editorial grouping
- `status`: `in_progress`, `settled`, `unsure`, `retired`
- `application_mode`: `replace`, `required`, `advisory`
- `citations_text`: raw Stephanos citations from the seed material
- provenance fields for workbook/sheet/row

Notes:

- The current design keeps workbook citations as raw text. They can be
  normalized later into structured references if needed.
- The model allows `rule_code` to be empty because the current spreadsheets do
  not yet expose the `Gabe n` identifiers discussed in the transcript.

### `translation_guidance_rule_revisions`

Append-only audit table recording every create/update/retire/reactivate event.

Key columns:

- `rule_id`
- `revision_number`
- `action`
- `changed_by`
- `change_summary`
- `source_context_json`
- `snapshot_json`

Why snapshots instead of diff-only rows:

- simpler imports
- simpler replay/debugging
- easier explanation of which rule state drove older matching or translation work

### `translation_guidance_scan_queue`

Internal queue for checking rules against lemmas incrementally.

Key columns:

- `rule_id`
- `rule_revision_id`
- `lemma_id`
- `source_text_version_id`
- `status`
- `priority`
- `detector_kind`
- `attempts`
- timestamps and error text

Design choices:

- queue items are revision-specific, so a changed rule creates new work without
  overwriting older results
- the active-queue uniqueness constraint prevents duplicate pending/running jobs
  for the same `(rule revision, lemma, source text)`

### `translation_guidance_matches`

Stored results of matching work.

Key columns:

- `rule_id`
- `rule_revision_id`
- `lemma_id`
- `source_text_version_id`
- `detector_kind`
- `detector_version`
- `match_status`
- `occurrence_count`
- `confidence`
- `evidence_text`
- `evidence_json`

Design choices:

- match rows are tied to a rule revision so later edits do not blur historical
  results
- the table stores "not matched" as well as "matched"; otherwise we cannot tell
  whether a lemma was checked

### `translation_guidance_backlog_items`

Explicit follow-up work generated from rule changes or later automation.

Key columns:

- `rule_id`
- `rule_revision_id`
- `lemma_id`
- `source_text_version_id`
- `backlog_kind`
- `status`
- optional translation variant reference
- `priority`
- `created_by`
- timestamps

Expected uses:

- `scan_rule`: a visible reminder that matching still needs to happen
- `rerun_translation`: safe machine rerun candidate
- `review_translation`: human review required before changing canonical output

## Import Workflow

### Input Shape

Current workbook columns:

- Glosses: Greek word, citations, proposed translation, word class, notes,
  status
- Formulae: formula, citations, proposed translation, notes, word class, status
- Proper nouns: Greek name, transliteration, word class

### Import Behavior

- parse `.xlsx` directly without requiring a heavy spreadsheet dependency
- normalize status text and application mode by rule kind
- write a canonical rule row
- create revision `1` on first insert
- if the importer later changes a current row, write a new revision snapshot

### Import Provenance

Store enough provenance to answer:

- which workbook seeded this rule
- which sheet it came from
- which row it came from
- which importer run last touched it

## Editing Model

### Permissions

- protected edit side only for authenticated users
- public side can read current rule state and later aggregate usage summaries

### CRUD Semantics

- create: insert current row + revision `1`
- update: update current row + append revision
- delete: implemented as retire in the canonical table + append revision
- undelete: reactivate + append revision

### Audit Requirements

- every change carries the authenticated username
- append-only revisions are never rewritten
- the current table is optimized for reads; revisions preserve history

## Matching Pipeline

### Deterministic First

Proper nouns and many glosses should be handled without AI where possible:

- exact normalized Greek form matches
- alias/fuzzy expansion later if needed
- existing entity extraction data for proper nouns where appropriate

### AI Where Needed

Formulae are the hardest case because they are often patterns rather than
single lexical items.

Recommended pipeline:

1. deterministic prefilter to shortlist candidate lemmas
2. queue only those candidates for AI adjudication
3. store explicit result rows with evidence and multiplicity

This minimizes token spend and preserves explainability.

## Translation Integration

The future worker should gather current matched rules before translation.

Recommended prompt assembly order:

1. base translation profile
2. source-text specific context
3. matched proper-noun replacements
4. matched formula requirements
5. matched gloss preferences

Important constraint:

- matched glosses should be presented as advisory preferences, not mandatory
  replacements

## Backlog Logic

When a rule changes:

1. identify likely affected lemmas
2. create explicit backlog rows
3. auto-rerun only where safe
4. require human review where canonical or reviewed work already exists

This avoids the current failure mode where consistency changes are remembered
socially but not tracked operationally.

## Public Read Model

Later public pages should show:

- active rules by category
- citations/examples for each rule
- counts of matched lemmas
- links to affected lemmas

The public side is read-only. Editing remains on the protected side.

## First Implementation Boundaries

Implemented in the first slice:

- schema foundation
- seed importer
- queue-enqueue helper

Deferred:

- edit UI
- scan worker
- automatic backlog generation from every rule edit
- integration into translation prompts and review export
- public pages

## Open Questions

1. Should `rule_code` become mandatory once the formula catalogue is stabilized?
2. Should gloss rules eventually support multiple preferred renderings ranked by
   context rather than one preferred string?
3. Do proper-noun rules need a separate alias table immediately, or only once
   the edit UI exists?
4. Should source citations eventually be normalized into structured lemma
   references instead of raw text?
