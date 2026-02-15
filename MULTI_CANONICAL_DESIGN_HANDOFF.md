# Multi-Canonical Translation Design Handoff

Date: 2026-02-15
Project: Stephanos translation pipeline (merah SQLite bridge + raksasa Postgres)

## 1. Scope of this document

This document defines the remaining design work for multi-canonical translations and the concrete implementation needed to make it safe and operational.

It also records the current decision:
- Nodegoat sync should happen only when exactly one translation would be presented.
- Meineke apparatus display is required on edit/review pages, not on public pages.

## 2. Current architecture constraints

1. Write path from UI:
- Review/edit UI writes to SQLite on `merah`.
- Nightly sync copies SQLite back to `raksasa`.
- `import_reviews.py` applies changes to Postgres.

2. Source of truth:
- Postgres on `raksasa` remains authoritative.
- `review_data.json` is a nightly snapshot deployed to `merah`.

3. Nodegoat limitation:
- Nodegoat has a single effective translation lane for what we sync.
- We cannot represent multiple canonicals in parallel there without lossy collapsing.

4. Risk gating:
- Some variants are blocked by risk flags and must never be public/synced.

## 3. Why multi-canonical is hard

### 3.1 Ambiguity in intent
"Canonical" used to mean one selected variant. Multi-canonical introduces at least three meanings that must be separated:
1. Publicly displayed now.
2. Editorially approved as canonical candidates.
3. Externally synced to Nodegoat.

If these are not separated, actions like "remove canonical" are ambiguous and error-prone.

### 3.2 Conflict between systems
- UI writes are delayed (nightly import).
- Public pages are generated from Postgres.
- Nodegoat accepts only one translation lane.

Without explicit rules, two canonical variants can be valid locally but impossible to represent downstream.

### 3.3 Edit operations need reversibility
Editors need to:
1. Add canonical candidate.
2. Remove one candidate but keep others.
3. Clear all canonicals.
4. Set one variant as primary without deleting others.

Current single-pointer model does not encode all of these operations cleanly.

### 3.4 Deterministic precedence required
When multiple editors act on the same lemma in one day, import must be deterministic.

## 4. Required semantics (target behavior)

Define two separate concepts:

1. `canonical_set`:
- Zero to many variants marked canonical candidates for a lemma.

2. `primary_canonical`:
- Zero or one variant designated as the primary presentation variant.

Rules:
1. Public pages may show one or many canonicals depending on UX mode.
2. If UX mode is single-translation, use `primary_canonical` if set.
3. If no `primary_canonical`, fallback deterministically (latest approved canonical candidate by timestamp/id).
4. Blocked variants cannot be canonical candidates.
5. Nodegoat sync occurs only when exactly one variant is effectively presentable.

## 5. Data model changes needed

## 5.1 Postgres (raksasa)

Add a canonical membership table (if not already present):

`lemma_canonical_variants`
- `lemma_id`
- `variant_kind`
- `variant_id`
- `is_active` (bool)
- `is_primary` (bool)
- `updated_by`
- `updated_at`
- unique on (`lemma_id`, `variant_kind`, `variant_id`)
- partial unique on (`lemma_id`) where `is_primary=true`

Keep `lemma_publication_targets` for backward compatibility during migration.

## 5.2 SQLite (merah)

Add/extend intent table for canonical actions (append-only or upsert with timestamp):

`canonical_variant_actions`
- `lemma_id`
- `action` (`add`, `remove`, `set_primary`, `clear_all`, `clear_primary`)
- `variant_kind` nullable
- `variant_id` nullable
- `reviewer_username`
- `reviewed_at`
- `notes`

Reason: importing explicit actions is less ambiguous than importing snapshots.

## 6. Import algorithm (SQLite -> Postgres)

For each lemma, process actions ordered by `(reviewed_at, sqlite_rowid)`.

Action effects:
1. `add`: set membership active for given variant.
2. `remove`: deactivate membership for given variant; if primary, clear primary.
3. `set_primary`: ensure membership active, set primary true, clear other primary.
4. `clear_primary`: clear only primary flag.
5. `clear_all`: deactivate all memberships and clear primary.

Validation before applying any action:
1. Variant exists.
2. Variant is approved.
3. Variant has non-empty translation text.
4. Variant is not blocked by risk gating.

Rejected actions should be logged with reason.

## 7. Public selection algorithm

Input: lemma variants + canonical memberships + risk flags.

1. Build `eligible_variants` from approved, non-empty, non-blocked variants.
2. Intersect with active canonical membership set.
3. If empty, use existing fallback policy.
4. If single-translation mode:
- use primary if present and eligible.
- else deterministic fallback from canonical set.
5. If multi-translation mode:
- return ordered eligible canonical set.

Current practical recommendation:
- Keep single-translation public mode for now.
- Store multi-canonical metadata now.

## 8. Nodegoat sync rule (explicit)

For each lemma:
1. Compute `presented_variants` using the same algorithm as public presentation.
2. If `count(presented_variants) == 1`, sync that translation to Nodegoat.
3. Else do not sync translation for this lemma.

On skip, log reason in sync report:
- `zero_presented_variants`
- `multiple_presented_variants`
- `blocked_only`
- `non_approved_only`

Do not attempt to collapse multiple variants into one for Nodegoat.

## 9. UI changes needed

Review/edit page actions should be explicit and independent:
1. `Add as canonical`
2. `Remove from canonical`
3. `Set as primary`
4. `Clear primary`
5. `Clear all canonicals`

Do not overload a single checkbox for all canonical actions.

## 10. Migration plan

## Phase A: Stabilize current flow (short)
1. Keep current single-pointer compatibility.
2. Keep canonical override behavior from SQLite for local visibility.
3. Add explicit clear operation support end-to-end.

## Phase B: Introduce canonical set model
1. Add Postgres canonical membership table.
2. Add SQLite canonical action table.
3. Update import pipeline to process canonical actions.
4. Keep writing `lemma_publication_targets` as compatibility projection from canonical set + primary.

## Phase C: Nodegoat-safe sync
1. Update `sync_nodegoat.py` to evaluate presentable set.
2. Sync only when exactly one variant is presentable.
3. Emit report artifact of skipped lemmas and reasons.

## Phase D: Optional multi-display UX
1. Decide whether public pages should show multiple canonicals.
2. If yes, add ordered rendering; if no, keep primary-only display and preserve extra canonical variants for editorial use.

## 11. Open decisions needed from editorial team

1. Should public pages remain single-translation for now? (recommended: yes)
2. When multiple canonicals exist, should one be mandatory primary? (recommended: yes)
3. Should "remove canonical" preserve historical audit trail? (recommended: yes, action log)
4. Should Nodegoat skip silently or display an editorial warning report? (recommended: warning report)

## 12. Immediate next implementation items

1. Remove any remaining SSH-proxy assumptions from canonical endpoints.
2. Add explicit canonical action schema in SQLite and import logic in Postgres.
3. Refactor `sync_nodegoat.py` to enforce `exactly_one_presented_variant` rule.
4. Produce daily report: `canonical_sync_ambiguities.html` or JSON equivalent.

## 13. Non-goals for now

1. Public rendering of Meineke apparatus (edit/review only).
2. Representing multiple translation lanes in Nodegoat.
3. Real-time cross-host canonical writes from `merah` to `raksasa`.

## 14. Summary

The core issue is not storage but semantics under delayed sync and single-lane downstream constraints.

The robust solution is:
1. Model canonical membership and primary separately.
2. Capture explicit canonical actions in SQLite.
3. Apply deterministically on nightly import.
4. Sync to Nodegoat only when exactly one translation is presentable.

