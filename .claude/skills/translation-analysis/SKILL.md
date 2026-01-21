---
name: translation-analysis
description: Analyze differences between human-corrected translations and AI translations to identify patterns and generate prompt guidance. Use when reviewing translation quality, comparing Gabriel's corrections, or improving the translation system.
allowed-tools: Bash, Read, Grep, Write
---

# Translation Analysis Skill

Analyze human translator corrections to identify systematic differences from AI translations and generate actionable guidance for improving the translation prompt.

## Data Sources

### Review Database (SQLite on merah)
```bash
# Copy latest review database locally
scp stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/reviews.db /tmp/reviews.db
```

Schema:
- `lemma_id` - links to assembled_lemmas
- `corrected_english_translation` - Gabriel's corrected translation
- `corrected_greek_text` - Gabriel's corrected Greek
- `notes` - Gabriel's annotations explaining changes
- `review_status` - 'reviewed_ok', 'reviewed_corrections', 'not_reviewed'

### PostgreSQL Database
```bash
psql -U stephanos stephanos -c "SELECT id, lemma, greek_text, translation FROM assembled_lemmas WHERE id = <lemma_id>"
```

## Analysis Workflow

### Step 1: Get Statistics
```bash
sqlite3 /tmp/reviews.db "SELECT
  COUNT(*) as total,
  SUM(CASE WHEN review_status = 'reviewed_ok' THEN 1 ELSE 0 END) as ok,
  SUM(CASE WHEN review_status = 'reviewed_corrections' THEN 1 ELSE 0 END) as corrected,
  SUM(CASE WHEN corrected_english_translation IS NOT NULL AND length(corrected_english_translation) > 0 THEN 1 ELSE 0 END) as english_fixes
FROM reviews"
```

### Step 2: Extract Corrections with Notes
```bash
sqlite3 /tmp/reviews.db "SELECT lemma_id, corrected_english_translation, notes
FROM reviews
WHERE corrected_english_translation IS NOT NULL
AND length(corrected_english_translation) > 0"
```

### Step 3: For Each Correction, Compare Side-by-Side

For each lemma_id with a correction:

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
psql -U stephanos stephanos -c "SELECT version, created_at, notes, prompt_text FROM translation_prompts ORDER BY version DESC LIMIT 1"
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
INSERT INTO translation_prompts (prompt_text, notes)
VALUES (
'You are an expert classical philologist and translator specializing in Byzantine Greek geographical texts.
You will receive Greek text from a lemma entry in Stephanos of Byzantium''s Ethnika.
Translate the Greek text into clear, scholarly English.
Preserve technical terminology and place names appropriately.

TRANSLATION STYLE GUIDE:
[Insert generated guidance here]
',
'Added guidance based on Gabriel''s corrections: [brief summary of changes]'
);
EOF
```

### Step 8: Verify and Report

After inserting, verify and show the user:
```bash
psql -U stephanos stephanos -c "SELECT version, created_at, notes FROM translation_prompts ORDER BY version DESC LIMIT 1"
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
  AND translation_prompt_version < (SELECT MAX(version) FROM translation_prompts)
"
```

The next run of `translate_lemmas.py` will automatically prioritize these entries.
