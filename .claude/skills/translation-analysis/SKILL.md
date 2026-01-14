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

After analysis, the generated guidance can be added to:
- `translate_lemmas.py` TRANSLATION_SYSTEM_PROMPT constant
- A separate `TRANSLATION_GUIDE.md` file referenced by the prompt
