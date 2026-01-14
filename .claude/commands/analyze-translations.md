---
description: Analyze human vs AI translation differences to generate prompt guidance
allowed-tools: Bash, Read, Grep, Write
---

# Translation Analysis Task

Analyze the differences between Gabriel's human-corrected translations and the AI-generated translations to identify patterns and generate actionable guidance for improving the translation prompt.

## Steps to Follow

1. **Sync the review database** from merah to /tmp/reviews.db

2. **Get statistics** on reviewed entries:
   - Total reviews
   - Approved ("reviewed_ok") vs corrected ("reviewed_corrections")
   - Number with English corrections
   - Number with Greek corrections

3. **For each entry with English corrections**:
   - Fetch the AI translation from PostgreSQL
   - Fetch Gabriel's corrected translation from SQLite
   - Fetch Gabriel's notes explaining the changes
   - Fetch the Greek source text
   - Compare side-by-side and identify specific differences

4. **Categorize the patterns** you find:
   - Transliteration preferences (k vs c, Greek letters, case endings)
   - Over-translation issues (elaborate phrasing for simple Greek)
   - Unnecessary additions (parenthetical explanations, expansions)
   - Filler word removal (however, but, also)
   - Grammar corrections (antecedent errors)
   - Stylistic preferences (telegraphic formulas)
   - Modern vs ancient names

5. **Generate a translation style guide** that could be added to the system prompt in `translate_lemmas.py`

## Output Format

Produce a comprehensive report with:
- Statistics summary
- Pattern analysis table with examples
- Detailed side-by-side comparisons for each correction
- Gabriel's notes verbatim
- Ready-to-use prompt guidance

$ARGUMENTS
