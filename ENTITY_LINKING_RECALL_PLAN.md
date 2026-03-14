# Named Entity Linking Error Reduction Plan

**Created:** 2026-03-13
**Status:** Planning Phase

## Overview

The current named-entity pipeline is making far more mistakes by omission than by incorrect disambiguation. The Brady import and review pass shows that the main problem is not usually "the AI picked the wrong QID"; it is more often:

1. The AI extracted a name-like mention but never linked it to any identifier.
2. The AI failed to surface the entity cleanly enough for linking in the first place.
3. The AI had the right entity family in view but lacked a strong local candidate set.

This plan focuses on increasing recall for entity extraction and linking, especially for places and person-like entities, while keeping the current human-review model in place.

## Evidence From The Brady Comparison

After importing Brady's spreadsheet, applying Brady as the human reviewer where there was an existing AI row, and regenerating the comparison pages:

- `4156` `proper_nouns` rows were assigned a Brady human review result.
- Of those, `896` were already correct (`approved`).
- `3260` required correction.
- Within the corrected rows:
  - `3141` were corrected from an unlinked state (no machine QID).
  - `119` were corrected from a wrong machine QID.

At the grouped comparison level:

- `2892` groups were `brady_qid_text_match`: Brady had a QID and overlapped the AI text, but the AI had not linked the entity.
- `894` groups were `same_qid`.
- `118` groups were `different_qid`.

The biggest corrected category was place-like entity linking:

- `2439` corrected rows were `noun_type='place'` with `role='entity'`.

After applying Brady to the rows that already existed in `proper_nouns`, the largest remaining discrepancy bucket was still Brady-only QID groups:

- `7713` groups were `brady_only_qid`.
- The largest sub-buckets were place-like and male/person-like entities.

This strongly suggests that the dominant failure mode is recall, not final ranking.

## Main Causes

### 1. Conservative Linking Behavior

The system is often too reluctant to attach an identifier unless the answer looks obvious. That protects precision, but it leaves many real entities unlinked.

### 2. Incomplete Extraction Before Linking

Some of the remaining Brady-only groups appear to be entities that never became useful `proper_nouns` rows. In those cases, there is nothing for the linker to correct.

### 3. Weak Alias Coverage

The pipeline does not yet fully exploit the surface forms already present in Brady's spreadsheet:

- inflected Greek forms
- accent and breathing variation
- alternate Latinized spellings
- short context snippets that reveal the intended entity

Without a strong alias layer, the model has to infer too much from sparse context.

### 4. Place Names Are Harder Than Source Authors

The review data suggests that source-author linking is comparatively strong, while places are much weaker. Place mentions are more vulnerable to ambiguity, local spelling variation, and mention extraction failures.

### 5. Open-Ended Resolution Is Doing Too Much Work

The current flow still leaves too much responsibility with the model to invent or retrieve the right candidate. A short, curated candidate list should be doing more of that work.

## Goals

1. Increase recall for place and person entity linking.
2. Reduce the number of real mentions left unlinked.
3. Add missing entity rows where there is strong human evidence.
4. Reuse Brady as an authority layer, not just a one-time correction source.
5. Preserve the existing human-review model and avoid broad speculative automation.

## Non-Goals

This plan does not propose:

- a fully general named-entity canonicalization system
- automatic demonym handling
- additional place linking from lemma pages
- a new translation prompt
- generic performance work unrelated to entity recall

## Proposed Work

### Phase 1: Make Brady Data A First-Class Candidate Source

Build a reusable authority layer from Brady's tags so the pipeline can look up likely identifiers before asking the model to resolve anything.

Likely outputs:

- a normalized alias table keyed by `BillID`, text form, QID, Pleiades ID, and source authority
- reusable normalization for accents, case, punctuation, and transliteration variants
- a helper that returns a small candidate set for a mention from local data first

Why this comes first:

- It directly addresses the dominant failure mode: real entities with no machine QID.
- It uses the highest-quality human data already available.

### Phase 2: Improve Recall For Missed Mentions

Add a second-pass extraction or enrichment step aimed specifically at place and person mentions that appear in the text but are not ending up as useful linked rows.

Candidate approaches:

- re-scan lemma text for unresolved proper-name spans after the first extraction pass
- run a narrower model prompt for "find additional place/person mentions only"
- seed extraction with likely aliases from the Brady authority layer

Priority:

- places first
- then male/person entities
- source authors last, since they already appear relatively healthy

### Phase 3: Create Missing `proper_nouns` Rows From Strong Brady Matches

Right now Brady only corrects existing AI rows. The next major gain is to add rows for entities Brady tagged that the AI never surfaced.

Safeguards:

- only create rows when the Brady text clearly overlaps the lemma text
- mark provenance explicitly as Brady-derived
- keep the new rows visible in review/export pages

This is likely the highest-value follow-on step after Phase 1.

### Phase 4: Change The Model Task From Open-Ended Search To Candidate Selection

When the model is involved, it should mostly choose among plausible candidates rather than generate a link from scratch.

Desired behavior:

- local authority lookup first
- candidate set construction second
- model choice or abstention third

This should improve both accuracy and consistency.

### Phase 5: Add Ongoing Evaluation Against Human Authority

Use Brady as an evaluation baseline for recall-oriented metrics.

Useful metrics:

- percent of Brady-tagged QID rows matched by AI
- percent matched with no machine QID
- percent matched with wrong machine QID
- recall by noun type (`place`, `person`, `people`, `deity`, `other`)
- counts of Brady-only rows that still lack a corresponding `proper_nouns` entry

This evaluation should be cheap enough to run repeatedly after each improvement.

## Likely Implementation Surface

The first implementation pass will probably touch or add code in these areas:

- `extract_proper_nouns.py`
- `link_wikidata.py`
- `generate_brady_entity_review_page.py`
- `apply_brady_entity_resolutions.py`
- `import_brady_ground_truth.py`
- a new Brady alias/candidate helper module

The database may also need a small new table for reusable alias or candidate records if a pure on-the-fly approach turns out to be too slow or opaque.

## Risks And Caveats

### Brady Coverage Is High-Value But Not Complete

Brady's tags are authoritative where present, but they are not yet a complete annotation of the corpus. We should not treat every AI-only entity as automatically wrong.

### Recall Improvements Can Increase Noise

A more aggressive extraction pass may create more low-confidence candidates. The plan depends on keeping provenance visible and reviewable.

### Place Linking Needs Careful Normalization

Many place-like errors are probably recoverable with better alias handling rather than more model effort. The normalization layer matters at least as much as the prompt.

## Recommended Start Order

When work begins, the recommended order is:

1. Build the Brady-backed alias/candidate layer.
2. Re-run linking against existing `proper_nouns` rows using candidate selection.
3. Add missing `proper_nouns` rows from strong Brady-only matches.
4. Add a second-pass extraction for missed places and person entities.
5. Re-measure against Brady after each step.

## Immediate Next Step

No implementation is proposed in this document. The next action, when work begins, should be a small design pass for the Brady-backed alias/candidate layer and the minimal schema or helper code needed to support it.
