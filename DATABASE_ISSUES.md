# Database Issues

## Meineke import contamination in `assembled_lemmas`

**Discovered:** 2026-02-18 (data written 2026-02-15 and 2026-02-16)

### Problem Summary

After OCRing the *Meineke* PDF pages into `images` (`source_document='meineke'`), a large number of rows were inserted into `assembled_lemmas` that:
- have **empty `greek_text`**
- often have **NULL `entry_number`**
- include **duplicate headwords** (e.g., `Καβαλίς` appears twice)
- include **editorial/placeholder headwords** in square brackets (e.g., `[Κηφηνία ...]`)
- include **ALL-CAPS headwords** (e.g., `ΑΙΑΜΗΝΗ`) even when the actual text begins with a properly cased headword (`Αιαμηνή, ...`)

This pollution is visible in the reference site because `generate_reference_site.py` loads *all* `assembled_lemmas` rows unless they’re marked `quarantined`.

### What Happened (Root Cause)

1) **2026-02-14:** `extract_pdf_pages.py --source-document meineke` bulk-queued 835 rows (`meineke_page_014.jpg` … `meineke_page_848.jpg`) into `images`.

2) **2026-02-14:** `process_meineke_pages.py` OCR’d those images into a Meineke-specific JSON schema:
   - entries contain `main_text_lines` / `apparatus_entries`
   - entries do **not** contain `greek_text`
   - `entry_number` is optional and often absent

3) **2026-02-15 and 2026-02-16:** `assemble_lemmas.py` (at that time) selected **all** `images.processed=1` rows (no `source_document` filter) and tried to assemble them as if they were Billerbeck OCR payloads. That produced `assembled_lemmas` rows with blank `greek_text` and NULL `entry_number`.

4) **Duplicates exploded** because the uniqueness target used by `assemble_lemmas.py` is `(source_image_ids, entry_number, version)`, and PostgreSQL considers NULL values distinct in UNIQUE indexes. Re-running assembly inserted more rows for entries where `entry_number IS NULL`.

On 2026-02-16, `assemble_lemmas.py` was updated to exclude `images.source_document='meineke'`, preventing new contamination, but **existing bad rows remain**.

### Secondary Problem: Meineke end-matter/index pages overwriting `lemma_source_text_versions`

Separately from `assembled_lemmas`, we found that `assemble_meineke_texts.py` was ingesting *all* OCR’d Meineke images indiscriminately. The Meineke scan includes end-matter indices (e.g. `INDEX SCRIPTORUM`) whose OCR payloads look like “entries” but are actually lists of citations / references (often with Latin names and `123, 4`-style location markers).

Because `assemble_meineke_texts.py` falls back to mapping by `lemma` when `meineke_id`/`billerbeck_id` are absent, those index-page “entries” can match real lemmas and **insert new `lemma_source_text_versions` rows marked `is_current=TRUE`**, overwriting the real Meineke text for that lemma.

Mitigation applied on 2026-02-18:
- Deleted 130 OCR-source Meineke versions whose `notes` indicated they came from `meineke_page_739.jpg` and later, then restored a sane current version per lemma.
- “Neutered” the 110 end-matter images (`images.source_document='meineke' AND page_number > 738`) by setting `images.lemma_json` to `{"status":"apparatus_only","entries":[]}` so future runs cannot ingest them.
- Added default page cutoffs in `process_meineke_pages.py` and `assemble_meineke_texts.py` (both default to `--max-page 738`; override with `--include-end-matter`).

### Evidence (Quick Queries)

On raksasa:

```sql
-- Counts of assembled lemmas by source bucket (via lemma_images)
WITH lemma_sources AS (
  SELECT a.id,
         BOOL_OR(i.source_document='meineke') AS has_meineke,
         BOOL_OR(i.source_document='billerbeck') AS has_billerbeck
  FROM assembled_lemmas a
  LEFT JOIN lemma_images li ON li.lemma_id=a.id
  LEFT JOIN images i ON i.id=li.image_id
  GROUP BY a.id
)
SELECT
  CASE
    WHEN COALESCE(has_meineke,FALSE) AND COALESCE(has_billerbeck,FALSE) THEN 'mixed'
    WHEN COALESCE(has_meineke,FALSE) THEN 'meineke_only'
    WHEN COALESCE(has_billerbeck,FALSE) THEN 'billerbeck_only'
    ELSE 'no_images'
  END AS bucket,
  COUNT(*) AS n
FROM lemma_sources
GROUP BY 1
ORDER BY n DESC;
```

```sql
-- Massive duplicates exist only in the NULL-entry_number cohort (all Meineke-only)
WITH d AS (
  SELECT source_image_ids, lemma, version, COUNT(*) AS n
  FROM assembled_lemmas
  WHERE entry_number IS NULL
  GROUP BY 1,2,3
  HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS duplicate_groups,
       SUM(n) AS rows_in_groups,
       SUM(n-1) AS extra_rows
FROM d;
```

### Recommended Actions

**Short-term (safe):**
1) Delete “empty duplicate rows” (Meineke-only + no source text versions + no downstream derived rows).
2) Normalize ALL-CAPS headwords from the start of the current Meineke `text_body`.
3) Quarantine obviously broken editorial headwords with extremely short Meineke texts (e.g., `[Κηφηνία ...]` whose `text_body` is only that placeholder).

Script: `cleanup_meineke_import_artifacts.py` (dry-run by default).

**Long-term:**
- Keep Billerbeck assembly and Meineke OCR pipelines separate; only attach Meineke text via `lemma_source_text_versions` when it can be mapped to canonical lemma IDs (billerbeck_id/meineke_id/nodegoat_id), rather than creating ad-hoc lemma rows from OCR headwords.

## Duplicate Entries in assembled_lemmas

**Discovered:** 2025-12-22

### Problem Summary

Several entries in the `assembled_lemmas` table have duplicate rows that violate the intended uniqueness constraint on `(source_image_ids, entry_number, version)`. These appear to have been created when pages were processed multiple times - once for just the first page, then again for the complete multi-page range.

### Affected Entries

#### Delta Entries with Multiple Parisinus/Epitome Versions

Each of the following entries has **4 database rows** instead of 2:
- 2 Parisinus versions (one short/incomplete, one complete with full page range)
- 2 epitome versions (one short/incomplete, one complete with full page range)

**Entry 146: Δωδώνη**
- ID 5215: parisinus, 599 words, pages 119+121+123+125+127+129 (complete)
- ID 6939: parisinus, NULL words, page 119 only (incomplete)
- ID 5216: epitome, 104 words, pages 119+121 (incomplete)
- ID 5496: epitome, 616 words, pages 119+121+123+125+127+129 (complete)

**Entry 149: Δώριον**
- ID 5785: parisinus, 336 words, pages 133+135+137+139+141 (complete)
- ID 6945: parisinus, NULL words, page 133 only (incomplete)
- ID 5786: epitome, 35 words, page 133 only (incomplete)
- ID 6072: epitome, 313 words, pages 133+135+137+139+141 (complete)

**Entry 150: Δῶρος**
- ID 6073: parisinus, 304 words, pages 143+145+147 (complete)
- ID 6947: parisinus, NULL words, page 143 only (incomplete)
- ID 6074: epitome, 20 words, page 143 only (incomplete)
- ID 6362: epitome, 205 words, pages 143+145+147 (complete)

**Entry 151: Δώτιον**
- ID 6363: parisinus, 280 words, pages 149+151+153 (complete)
- ID 6949: parisinus, NULL words, page 149 only (incomplete)
- ID 6364: epitome, 30 words, page 149 only (incomplete)
- ID 6654: epitome, 227 words, pages 149+151+153 (complete)

#### Entry 143: Multiple Lemmas with Same Entry Number

Entry 143 has **TWO different lemmas**:

**Κάψα:**
- ID 6802: NULL version, NULL word_count
- ID 3088: epitome, 13 words

**Δυρράχιον:**
- ID 4657: parisinus, 245 words (complete)
- ID 6933: parisinus, NULL words (incomplete)
- ID 4658: epitome, 84 words (incomplete)
- ID 4932: epitome, 292 words (complete)

This suggests an entry numbering problem - two different lemmas should not share the same entry_number.

#### Κάπαι: Legitimate Duplicate or Error?

**Entry 65 and 111: Κάπαι**
- ID 2467: entry 65, epitome
- ID 2611: entry 111, epitome

This appears in the earlier analysis as having 2 copies with DIFFERENT entry numbers but both epitome version. Need to verify if this is:
- The same place mentioned twice by Stephanos (legitimate)
- An extraction error (should be deduplicated)

### Recommended Actions

**DO NOT automatically delete duplicates** without manual review. These options should be considered:

1. **Manual Review**: Check source images to determine which version is correct
2. **Keep Complete Versions**: For entries with short/complete pairs, the complete versions (with full page ranges and higher word counts) are likely correct
3. **Fix Entry Numbering**: Entry 143 needs investigation - determine correct entry numbers for Κάψα vs Δυρράχιον
4. **Add Unique Constraint**: After cleanup, add `UNIQUE (source_image_ids, entry_number, version)` constraint to prevent future duplicates

### Root Cause

Likely caused by:
1. Initial processing of dual-column pages extracted only first page
2. Later reprocessing with full page ranges created additional entries
3. No uniqueness constraint prevented duplicates from being inserted

### Related Files

- `assemble_lemmas.py` - Script that creates entries in assembled_lemmas
- `batch_process.py` - Image processing that may have been run multiple times
- Database schema in migration files

### Status

- **Identified:** 2025-12-22
- **Impact:** Moderate - causes duplicate display on website (now mitigated by showing all versions)
- **Priority:** Medium - does not break functionality but should be cleaned up
- **Assigned:** Pending manual review
