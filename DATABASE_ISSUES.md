# Database Issues

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
