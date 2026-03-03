---
name: translation-analysis
description: Analyze differences between human-reviewed translations and AI translation variants (legacy + translation runs) to identify patterns and generate prompt guidance. Use when reviewing translation quality, comparing Gabriel’s corrections, or improving the translation system.
allowed-tools: Bash, Read, Grep, Write
---

# Translation Analysis Skill

Analyze human translator corrections to identify systematic differences from AI translations and generate actionable guidance for improving the translation prompt.

This project now has *multiple* translation surfaces (so do **not** assume “one AI translation” or “one human translation”):
- **Legacy assembled translation** (AI): `assembled_lemmas.translation` (single string)
- **Queue-driven AI runs**: `translation_runs` (many rows per lemma; statuses + review)
- **Human translations**: review workflow in SQLite (`reviews.db`) and normalized variants in PostgreSQL (`human_translations`)

Human review/correction data lives *first* in a SQLite DB (`reviews.db`) on `merah`, and is imported into PostgreSQL nightly. As a result, **PostgreSQL review fields can be up to ~1 day behind SQLite**.

## Data Sources

### Review Database (SQLite on `merah`) — canonical + freshest
```bash
# Recommended: use the repo sync helper (writes to ~/stephanos/review_data/reviews.db)
./sync_review_db.sh

# Or pull directly (ad-hoc):
scp stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/reviews.db /tmp/reviews.db

# Pick one local path to use in commands below:
SQLITE_DB="$HOME/stephanos/review_data/reviews.db"   # after ./sync_review_db.sh
# SQLITE_DB="/tmp/reviews.db"                        # after scp
```

**File location on `merah`:** `/var/www/vhosts/stephanos.symmachus.org/db/reviews.db`

Tables/columns you can rely on (current):

**`reviews`** (1 row per `lemma_id`)
- `lemma_id` (PK) — links to `assembled_lemmas.id`
- `review_status` — `not_reviewed` | `reviewed_ok` | `reviewed_corrections`
- `corrected_greek_text` — human-corrected Greek (if OCR had errors)
- `corrected_english_translation` — *initial* human translation
- `reviewed_english_translation` — reviewed/approved translation (often empty; fall back to `corrected_english_translation`)
- `notes` — reviewer notes explaining changes
- `reviewed_at` — timestamp of last update
- `reviewer_username` — legacy field (kept for backwards compatibility)
- Per-field tracking: `greek_corrected_by`, `initial_translation_by`, `reviewed_translation_by`

**`translation_variant_reviews`** (optional; per-variant review status)
- `lemma_id`, `variant_kind`, `variant_id`
- `variant_status` (e.g. `draft`, `approved`, `rejected`, …)
- `source_text_version_id` (optional)
- `set_canonical` (legacy boolean; see `canonical_variant_actions` when present)
- `notes`, `reviewer_username`, `reviewed_at`

**`canonical_variant_actions`** (optional; append-only canonical selection log)
- `id` (autoincrement), `lemma_id`
- `action`: `add` | `remove` | `set_primary` | `clear_all` | `clear_primary`
- `variant_kind`, `variant_id` (nullable for clear actions)
- `reviewer_username`, `reviewed_at`, `notes`

**`metadata`** (optional bookkeeping)

### PostgreSQL Database
```bash
psql -U stephanos stephanos -c "SELECT id, lemma, greek_text, translation FROM assembled_lemmas WHERE id = <lemma_id>"
```

Key places to look in PostgreSQL (current):
- `assembled_lemmas`
  - Greek text: `greek_text`, `human_greek_text`, `corrected_greek_scan`
  - Legacy AI translation: `translation`
  - Human review translations (imported from SQLite): `corrected_english_translation`, `reviewed_english_translation`, `review_status`, `reviewed_by`, `reviewed_at`, `human_notes`
- `translation_runs` — AI translation variants (many per lemma)
- `human_translations` — normalized human translation variants (many per lemma; stages + statuses)
- `lemma_canonical_variants` — canonical memberships (optional; multi-canonical)
- Prompt versioning (current system): `translation_prompt_profiles` + `translation_prompt_profile_versions`
- Legacy prompt table (still exists): `translation_prompts`

## Analysis Workflow

### Choosing where to read translations from (SQLite vs PostgreSQL)

For the *human* translations/corrections you can choose either source:
- **SQLite (preferred / freshest):** `reviews.corrected_english_translation` and `reviews.reviewed_english_translation`
- **PostgreSQL (convenient / cached):** `assembled_lemmas.corrected_english_translation` and `assembled_lemmas.reviewed_english_translation`

Because `import_reviews.py` pulls from SQLite nightly, **PostgreSQL may lag SQLite by up to ~1 day** for these fields. If you’re doing analysis to improve translation prompts, prefer SQLite when possible.

For the *AI* translation text:
- **Legacy single translation:** `assembled_lemmas.translation`
- **Variant runs:** `translation_runs.translation_text` (filter to `status='approved'` if you want reviewed variants)

### Step 1: Get Statistics
```bash
sqlite3 "$SQLITE_DB" "SELECT
  COUNT(*) as total,
  SUM(CASE WHEN review_status = 'reviewed_ok' THEN 1 ELSE 0 END) as ok,
  SUM(CASE WHEN review_status = 'reviewed_corrections' THEN 1 ELSE 0 END) as corrected,
  SUM(CASE WHEN corrected_english_translation IS NOT NULL AND length(corrected_english_translation) > 0 THEN 1 ELSE 0 END) as initial_english_fixes,
  SUM(CASE WHEN reviewed_english_translation IS NOT NULL AND length(reviewed_english_translation) > 0 THEN 1 ELSE 0 END) as reviewed_english_fixes
FROM reviews"
```

### Step 2: Extract Corrections with Notes
```bash
sqlite3 "$SQLITE_DB" "SELECT
  lemma_id,
  review_status,
  corrected_greek_text,
  corrected_english_translation,
  reviewed_english_translation,
  notes,
  reviewed_at,
  COALESCE(greek_corrected_by, reviewer_username) AS greek_corrected_by,
  COALESCE(initial_translation_by, reviewer_username) AS initial_translation_by,
  COALESCE(reviewed_translation_by, reviewer_username) AS reviewed_translation_by
FROM reviews
WHERE review_status != 'not_reviewed'"
```

If you can’t access SQLite, you can pull the same “human translation” fields from PostgreSQL (may be up to ~1 day behind):
```bash
psql -U stephanos stephanos -c "
  SELECT
    id AS lemma_id,
    review_status,
    COALESCE(corrected_greek_scan, '') AS corrected_greek_text,
    COALESCE(corrected_english_translation, '') AS corrected_english_translation,
    COALESCE(reviewed_english_translation, '') AS reviewed_english_translation,
    COALESCE(human_notes, '') AS notes,
    reviewed_at,
    COALESCE(reviewed_by, '') AS reviewer_username
  FROM assembled_lemmas
  WHERE review_status != 'not_reviewed'
  ORDER BY reviewed_at NULLS LAST, id
"
```

### Step 3: For Each Correction, Compare Side-by-Side

For each `lemma_id` with a correction (or approved translation):

1. Get the AI translation:
```bash
psql -U stephanos stephanos -t -c "SELECT translation FROM assembled_lemmas WHERE id = <lemma_id>"
```

2. Get the Greek source:
```bash
psql -U stephanos stephanos -t -c "SELECT greek_text FROM assembled_lemmas WHERE id = <lemma_id>"
```

3. Compare AI vs Human translation, noting:
   - Word choice differences
   - Transliteration conventions (k vs c, etc.)
   - Structural changes (word order, punctuation)
   - Additions/removals (parenthetical explanations, filler words)
   - Grammar corrections (antecedent errors, case handling)
   - Proper noun handling (Greek vs Latinized names)
   - Geography naming conventions (e.g. “Black Sea” vs “Pontus”)

### Step 4: Categorize Patterns

Group differences into categories:

| Category | Example Issue | Guidance to Generate |
|----------|---------------|---------------------|
| **Transliteration** | Lycia → Lykia | Use k for kappa |
| **Over-translation** | "thus was X called" → "X used to be called this" | Keep simple phrases simple |
| **Unnecessary additions** | "(kalathos)" explanations | Don't explain obvious terms |
| **Filler words** | "however", "but", "also" | Remove when redundant |
| **Grammar errors** | Wrong antecedent | Pay attention to referents |
| **Formulaic style** | "The citizen is X" → "Citizen: X" | Use telegraphic style |
| **Modern names** | Pontos → Black Sea | Use familiar modern names |

### Step 5: Generate Prompt Guidance

Output a structured guide that can be added to the translation system prompt in `translate_lemmas.py`.

Format:
```
TRANSLATION STYLE GUIDE:

TRANSLITERATION:
- [specific rules with examples]

CONCISENESS:
- [specific rules with examples]

ACCURACY:
- [specific rules with examples]

FORMATTING:
- [specific rules with examples]
```

## Output

Produce a report with:

1. **Statistics**: How many reviewed, how many corrected, acceptance rate
2. **Pattern Analysis**: Table of identified patterns with examples
3. **Detailed Comparisons**: Side-by-side AI vs Human for each correction
4. **Gabriel's Notes**: Include his explanatory notes verbatim
5. **Generated Guidance**: Ready-to-use prompt additions

## Example Analysis Entry

```
### Entry 2116 (Κάληρος)

**Greek:** Κάληρος· οὕτως ἐκαλεῖτο ἡ Ἀλωπεκόνησος...

**AI Translation:**
Kaleros: thus was Alopekonnesos (alpha 242) called, from King Kaleros...

**Gabriel's Translation:**
Kaleros: Alopekonesos (α 242) used to be called this, after King Kaleros...

**Gabriel's Note:**
οὕτως ἐκαλεῖτο translated as 'this was the former name of...': over translation.

**Patterns Identified:**
- Over-translation: "thus was X called" → simpler phrasing
- Greek letters: (alpha 242) → (α 242)
- Spelling: Alopekonnesos → Alopekonesos (single n)
```

## Integration

Translation prompts are versioned in the database. After analysis:

### Step 6: View Current Prompt
```bash
psql -U stephanos stephanos -c "
  SELECT p.name, pv.version, pv.created_at, pv.notes
  FROM translation_prompt_profiles p
  JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
  WHERE p.active = true AND pv.active = true
  ORDER BY p.name, pv.version DESC
"
```

### Step 7: Ask User About New Prompt Version

After generating guidance, ask the user:

**"Would you like to create a new translation prompt version with this guidance?"**

Options:
1. Yes - insert new prompt version
2. No - just save the analysis for later
3. Let me review and edit first

If yes, combine the current prompt with the new guidance and insert:

```bash
psql -U stephanos stephanos << 'EOF'
INSERT INTO translation_prompt_profile_versions (profile_id, version, prompt_text, notes, active)
SELECT
  p.id,
  (SELECT COALESCE(MAX(version), 0) + 1 FROM translation_prompt_profile_versions WHERE profile_id = p.id),
'You are an expert classical philologist and translator specializing in Byzantine Greek geographical texts.
You will receive Greek text from a lemma entry in Stephanos of Byzantium''s Ethnika.
Translate the Greek text into clear, scholarly English.
Preserve technical terminology and place names appropriately.

TRANSLATION STYLE GUIDE:
[Insert generated guidance here]
',
'Added guidance based on human review: [brief summary of changes]',
true
FROM translation_prompt_profiles p
WHERE p.name = 'default'
RETURNING id, profile_id, version, created_at, notes;
EOF
```

### Step 8: Verify and Report

After inserting, verify and show the user:
```bash
psql -U stephanos stephanos -c "
  SELECT p.name, pv.version, pv.created_at, pv.notes
  FROM translation_prompt_profiles p
  JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
  WHERE p.name = 'default'
  ORDER BY pv.version DESC
  LIMIT 1
"
```

Report:
- New prompt version number
- Number of entries that will be retranslated (those with older prompt versions and no human translation)

```bash
psql -U stephanos stephanos -c "
SELECT COUNT(*) as entries_to_retranslate
FROM assembled_lemmas
WHERE translated = 1
  AND (corrected_english_translation IS NULL OR corrected_english_translation = '')
  AND (reviewed_english_translation IS NULL OR reviewed_english_translation = '')
  AND COALESCE(translation_prompt_version, 0) < (
    SELECT pv.version
    FROM translation_prompt_profiles p
    JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'default' AND pv.active = TRUE
    ORDER BY pv.version DESC
    LIMIT 1
  )
"
```

Use `enqueue_translation_runs.py --profile default` to queue these, then run `translate_lemmas.py` to generate new AI variants.
