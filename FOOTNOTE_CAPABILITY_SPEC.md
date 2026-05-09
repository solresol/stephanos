# Stephanos Footnote Capability Specification

Date: 2026-05-09

## Transcript Basis

Source material:

- `/Users/gregb/Downloads/Greg and Greta_transcript.txt`, especially 42:40-49:43.
- Private filed excerpt: `../papers/stephanos/2026-05-08-greg-and-greta/sources/stephanus-conversation-excerpts.md`.

Greta's request is not just "comments somewhere in the interface." The desired end state is a stable, printable Stephanos PDF in which a reader sees normal superscript note markers in the translated text and matching footnotes at the bottom of the page. The review workflow should let a human highlight the relevant phrase, write or revise the note, and later print/export the result in standard scholarly form.

The clearest transcript requirements are:

- Footnotes are anchored at phrase level, not merely at headword or entry level.
- The reviewer should be able to highlight a sentence or phrase and attach a note.
- The published/PDF form should show a superscript marker at the end of the highlighted phrase and a footnote below.
- A headword-level overview note may be useful later, but the immediate need is phrase-specific minimal commentary.
- The content should be minimal: the basic things a reader needs to understand, not a full commentary rabbit hole.
- AI should automatically detect likely minimal footnotes after a translation is produced; Greta must be able to review, edit, reject, and add notes at any time.
- If a human translation replaces an AI translation, AI-generated notes should not be blindly carried forward; they should be ignored or rerun against the human text.
- The workflow should be available from the final translation overview workspace and also from the per-entry translation review screen.

## Product Goal

Provide a phrase-level scholarly footnote system for Stephanos translations:

1. AI automatically detects the main classes of minimal commentary Greta identified and attaches draft footnotes to the relevant phrase.
2. Human reviewers can add and curate notes while translating or final-reviewing entries.
3. Publishable notes export to the public HTML and PDF book, including AI-generated notes where no human review has happened.
4. The PDF renders them as true footnotes attached to the relevant phrase, not as a detached commentary list.

## Current State

The repo already has a useful partial foundation:

- PostgreSQL table `lemma_commentary_entries` exists with `lemma_id`, `source_text_version_id`, `phrase_text`, `commentary_text`, attribution, and timestamps.
- `review_cgi` has a "Phrase Commentary" panel that captures selected text from the working Greek or AI translation block.
- Review-side SQLite `commentary_entries` are imported into PostgreSQL by `import_reviews.py`.
- `generate_reference_site.py` displays commentary entries as collapsible per-entry commentary blocks.
- `generate_translation_review_packets.py` exports commentary blocks in review packets.

Main gaps:

- Notes are stored as quoted phrase text only; there is no reliable character-span anchor for placing a footnote marker back into the PDF translation.
- There is no explicit distinction between Greek-anchor, translation-anchor, or whole-entry commentary.
- There is no note status/lifecycle for AI-generated, AI-public, human-reviewed, stale, or rejected notes.
- The final review workspace does not expose the commentary/footnote editor.
- `generate_pdf_book.py` does not fetch commentary entries or render footnotes.
- The HTML reference site presents notes as commentary blocks, not inline note markers.

## MVP Scope

The MVP should make AI-detected phrase-level footnotes work end to end, with human editing layered on top. This matters because many headwords will not be translated or footnoted by a human; for those entries the AI footnotes may be the only commentary readers ever see.

Required:

- Add, edit, delete, and review footnotes from both:
  - `/cgi-bin/review.cgi` per-entry translation review.
  - `/cgi-bin/final_review.cgi` final translation workspace.
- Let users anchor a note to selected text in either:
  - the current Greek source text, for notes explaining source-language issues;
  - the current English translation, for notes that should be printed at a specific point in the English PDF.
- Persist enough anchor metadata to reinsert the note marker in exported text.
- Automatically detect footnote candidates after translation, at least for the explicit transcript categories.
- Render publishable translation-anchored notes in `generate_pdf_book.py` as LaTeX `\footnote{...}` calls at the anchor point.
- Render the same notes in public HTML as inline numbered markers plus a note list or HTML footnotes.
- Keep existing commentary entries readable and importable during migration.

Out of scope for MVP:

- Full entry-level introduction/commentary paragraphs.
- General-purpose XML/TEI export.
- Automatic scholarly citation verification for every note.
- Cross-entry commentary indexes.

## Note Content Model

Each note should have:

- `lemma_id`: owning assembled lemma.
- `anchor_source`: `translation`, `greek`, or `entry`.
- `anchor_text`: the selected phrase as displayed when the note was created.
- `anchor_start` and `anchor_end`: character offsets within the normalized displayed text, when available.
- `source_text_version_id`: for Greek/source anchors, existing field remains useful.
- `translation_variant_kind`: for translation anchors, e.g. `ai`, `human`, `reviewed`, `final_review`.
- `translation_variant_id`: nullable id or stable marker for the translation text the anchor was created against.
- `commentary_text`: note body to print.
- `note_kind`: controlled but optional category.
- `generation_source`: `human`, `ai_detected`, `ai_rerun`, or `human_edited_ai`.
- `review_status`: `unreviewed`, `approved`, `edited`, `rejected`, `needs_revision`, or `stale`.
- `publication_status`: `public_ai`, `public_reviewed`, `private`, or `suppressed`.
- `confidence`: AI confidence bucket, e.g. `high`, `medium`, `low`.
- `evidence_text`: short machine-readable explanation for why the note was generated.
- `created_by`, `updated_by`, `created_at`, `updated_at`: existing attribution pattern.

For migration, existing rows in `lemma_commentary_entries` can default to:

- `anchor_source = 'greek'` if a `source_text_version_id` exists.
- `anchor_source = 'translation'` if imported from translation selection and no source id exists.
- `review_status = 'approved'` for human/imported rows.
- `publication_status = 'public_reviewed'` for human/imported rows.
- `generation_source = 'human'` unless clearly marked otherwise.

## Note Categories

Greta's examples suggest these initial categories:

- `wordplay_etymology`: explain name/wordplay that disappears in English.
- `geography_non_obvious`: geographic claim, mismatch, uncertainty, or orientation problem.
- `unique_attestation`: place/person/form known only from Stephanos or nearly only from Stephanos.
- `source_or_version`: epitome-only material, variant tradition, source compression, or source-status context.
- `ambiguity`: unresolved identification, uncertain place, uncertain sense, or ambiguous referent.
- `translation_explanation`: short note explaining an unavoidable translation choice.
- `other_minimal`: reviewer-approved note that does not fit a narrower category.

These categories should guide AI detection, filters, and later reporting, but should not block manual note creation.

## Review UI Behavior

### Per-entry review page

Keep the current phrase commentary panel, but relabel it as "Footnotes / Commentary" or split it into tabs:

- "Footnote notes" for printable/public notes.
- "Reviewer notes" for non-public internal notes, if needed later.

The form should show:

- selected phrase;
- anchor source (`Greek`, `English translation`, `Whole entry`);
- category;
- status;
- note body;
- provenance (`human`, `ai_detected`, or `human_edited_ai`);
- edit/delete/reject controls.

When a reviewer selects text:

- capture the displayed normalized text;
- capture selection offsets when the browser can identify them reliably;
- store the selected text even when offsets are unavailable;
- warn if the selected phrase appears more than once in the target text.

### Final review workspace

Each row should expose the same footnote editor without requiring a round-trip to the per-entry page. The useful minimal version is:

- show existing public, private, stale, and suppressed notes under the row with clear status labels;
- let the reviewer select text in the final English textarea or source pane;
- add/edit notes in-place;
- include note status in row search/filtering.

This matches the transcript request that the footnoting happen on the final translation overview screen while the reviewer can see the whole workflow.

## AI Detection And Publication Workflow

AI footnoting is the core capability, not an optional add-on. It should generate public-ready minimal commentary for entries that may never receive human review, while preserving clear provenance and giving reviewers the ability to improve or suppress any note later.

Automatic triggers:

- After an AI translation is saved, run footnote detection against that translation.
- After a human/final translation is saved, mark older translation-anchored AI notes stale and rerun detection against the new text.
- A batch job should cover translated entries with no current footnote pass, because the point is broad coverage rather than only reviewer-initiated notes.
- A manual "Detect footnotes" button remains useful for reruns and debugging, but it is not the primary workflow.

Prompt inputs:

- current Greek source text;
- current English translation;
- headword and metadata;
- existing public/rejected/stale notes;
- available place/source/citation/entity metadata where cheap;
- category list above;
- instruction to produce only minimal notes and to skip speculative filler;
- instruction to output no note when there is no real reader-facing issue.

Expected output:

```json
{
  "notes": [
    {
      "anchor_source": "translation",
      "anchor_text": "selected phrase in the English translation",
      "note_kind": "wordplay_etymology",
      "commentary_text": "Short printable note.",
      "confidence": "high",
      "publication_status": "public_ai",
      "evidence": "Brief reason for reviewer inspection."
    }
  ]
}
```

Insertion rules:

- High-confidence AI notes with an unambiguous anchor enter as `review_status = 'unreviewed'` and `publication_status = 'public_ai'`.
- Medium/low-confidence AI notes, notes with weak evidence, and notes with ambiguous anchors enter as `publication_status = 'private'` and `review_status = 'needs_revision'`.
- Human-approved or human-edited notes use `publication_status = 'public_reviewed'`.
- Rejected notes use `publication_status = 'suppressed'` and must not reappear unless a later rerun materially changes the evidence.
- If a new human/final translation is saved, stale AI notes tied to the older translation should be marked `stale`; rerun detection against the new translation and keep the old notes visible only as history.
- Human-edited notes remain publishable unless the anchor can no longer be matched.

Public AI notes must be transparent. The generated PDF/HTML should expose provenance at least in metadata/front matter and ideally in the review/export reports: counts of AI-public notes, human-reviewed notes, stale notes, and suppressed notes. The footnote body itself should stay readable and scholarly; do not clutter every note with a long warning label unless the publication design later requires that.

## Export Behavior

### PDF

`generate_pdf_book.py` should:

- fetch publishable note rows grouped by lemma (`public_ai` and `public_reviewed`);
- apply only notes whose `anchor_source = 'translation'` for inline PDF footnotes;
- insert `\footnote{...}` immediately after the anchored phrase;
- escape note text with the same LaTeX discipline used for translations;
- detect duplicate anchor text and use offsets when available;
- if an anchor cannot be found, emit a warning and place the note in a fallback "Notes on this entry" block rather than silently dropping it.

Greek-anchored notes need a policy decision. The pragmatic MVP policy is to let them appear in the editor and HTML commentary, but not inline in the translation PDF unless a reviewer also supplies a translation anchor.

### Public HTML

`generate_reference_site.py` should keep the collapsible commentary as a fallback, but publishable translation-anchored notes should also be shown inline:

- superscript note marker after the anchored phrase;
- note text below the entry or in a local footnote list;
- rejected, stale, private, and needs-revision notes hidden from public output.
- AI-public notes shown publicly with provenance available in page metadata, export reports, or a visible publication note.

## Anchor Matching Rules

Use a layered approach:

1. Prefer stored offsets against the exact normalized text version.
2. Fall back to exact `anchor_text` match.
3. If exactly one normalized match exists, use it.
4. If no match or multiple matches exist, mark the note `needs_revision` and surface it in the UI.
5. Never guess silently in public export.

This is the key implementation detail that separates a publishable footnote system from the current commentary list.

## Database Migration Plan

Add columns to `lemma_commentary_entries`:

```sql
ALTER TABLE lemma_commentary_entries
    ADD COLUMN IF NOT EXISTS anchor_source TEXT NOT NULL DEFAULT 'greek',
    ADD COLUMN IF NOT EXISTS anchor_start INTEGER,
    ADD COLUMN IF NOT EXISTS anchor_end INTEGER,
    ADD COLUMN IF NOT EXISTS translation_variant_kind TEXT,
    ADD COLUMN IF NOT EXISTS translation_variant_id TEXT,
    ADD COLUMN IF NOT EXISTS note_kind TEXT,
    ADD COLUMN IF NOT EXISTS generation_source TEXT NOT NULL DEFAULT 'human',
    ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'approved',
    ADD COLUMN IF NOT EXISTS publication_status TEXT NOT NULL DEFAULT 'public_reviewed',
    ADD COLUMN IF NOT EXISTS confidence TEXT,
    ADD COLUMN IF NOT EXISTS evidence_text TEXT,
    ADD COLUMN IF NOT EXISTS stale_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stale_reason TEXT;
```

Mirror the same fields in review-side SQLite `commentary_entries`, then update:

- `review_cgi/init_schema.sql`;
- `review_cgi/common.go`;
- `review_cgi/save.go`;
- `review_cgi/templates.go`;
- `review_cgi/final_review.go`;
- `import_reviews.py`;
- `export_for_review.py`;
- `generate_reference_site.py`;
- `generate_pdf_book.py`;
- `schema/base_schema.sql` and `stephanos_schema.sql` after migration dump refresh.

## Acceptance Criteria

AI-detection MVP:

- After an AI translation is generated, the system automatically runs footnote detection for the transcript categories: wordplay/etymology, non-obvious geography, unique attestation, and ambiguity.
- High-confidence AI notes with unambiguous anchors are exported publicly as footnotes even without human review.
- The generated PDF contains a superscript marker immediately after the selected phrase and a matching footnote at the bottom of the page.
- The public HTML shows the same publishable note inline or as a local footnote.
- Human-created or human-edited notes override AI-public notes where appropriate.
- Rejected, stale, private, and needs-revision notes do not appear in public output.
- Duplicate or missing anchors produce visible warnings and do not silently attach to the wrong phrase.

Human review follow-up:

- A reviewer can click "Detect footnotes" for an entry to rerun detection.
- AI notes are categorized, editable, suppressible, and reviewable.
- Human approval changes the note into `public_reviewed`; human rejection suppresses it.
- Saving a new final translation marks older AI notes stale or requires rerun.

## Suggested Implementation Order

1. Add schema columns and preserve compatibility with existing commentary entries.
2. Implement the AI detection job and store AI-public/private/stale/suppressed note states.
3. Implement anchor matching and export warnings.
4. Implement PDF rendering for publishable translation-anchored notes.
5. Implement public HTML inline rendering and provenance reporting.
6. Update review import/export paths so local review notes carry anchor/status/provenance metadata into PostgreSQL.
7. Upgrade the per-entry review UI to capture `anchor_source`, offsets, category, status, and publication state.
8. Add final-review row footnote viewing/editing.
9. Add stale-note detection when final translations change.

The AI detector is the central piece because it gives broad footnote coverage across entries that will not receive human attention. Human review improves and overrides that layer; it should not be required before a high-confidence AI note can become part of the public AI-generated edition.

## Initial Cron Policy

The initial daily-pipeline integration should keep this lane deliberately low priority:

- `run_daily_pipeline.sh` ensures the footnote schema before strict schema preflight.
- After translation, it runs `detect_footnotes.py` with `FOOTNOTE_DETECTION_LIMIT=1` by default.
- Operators can set `FOOTNOTE_DETECTION_LIMIT=0` to disable it, or raise the limit temporarily for backfills.
- The detector records zero-note runs so the daily one-check pass can slowly advance instead of repeatedly checking the same headword.
