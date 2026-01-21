# Billerbeck ID Cleanup Plan

## Summary

This document outlines proposed changes to assign missing Billerbeck IDs and remove duplicate entries from the `assembled_lemmas` table.

## Current State

- **38 epitome entries** lack Billerbeck IDs
- **3 of these are duplicates** (shorter, incomplete versions of multi-page entries)
- **35 unique entries** need Billerbeck IDs assigned

## Phase 1: Remove Incomplete Duplicates

Three multi-page entries have incomplete duplicates that should be removed:

### Δωδώνη (Entry #146)

| ID | Images | Text Length | Word Count | Action |
|----|--------|-------------|------------|--------|
| 5216 | 2 | 765 chars | 104 | **DELETE** |
| 5496 | 6 | 5,481 chars | 616 | Keep |

### Δώριον (Entry #149)

| ID | Images | Text Length | Word Count | Action |
|----|--------|-------------|------------|--------|
| 5786 | 1 | 231 chars | 35 | **DELETE** |
| 6072 | 5 | 2,572 chars | 313 | Keep |

### Δώτιον (Entry #151)

| ID | Images | Text Length | Word Count | Action |
|----|--------|-------------|------------|--------|
| 6364 | 1 | 176 chars | 30 | **DELETE** |
| 6654 | 3 | 2,113 chars | 227 | Keep |

**Deletion process:**
1. Delete from `lemma_images` junction table
2. Delete from `proper_nouns` table
3. Delete from `etymologies` table
4. Delete from `proper_noun_aliases` table
5. Delete from `assembled_lemmas` table

## Phase 2: Assign Billerbeck IDs

Assign IDs to 35 entries using the formula: `[Greek letter][entry_number]`

### Billerbeck vol 2 - Epsilon entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 6658 | 3 | Ἑβραῖοι | Ε3 |
| 6659 | 4 | Ἑβρών | Ε4 |
| 6660 | 5 | Ἐγγάδα | Ε5 |
| 15968 | 43 | Ἐλένειος | Ε43 |

### Billerbeck vol 2 - Delta entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 3842 | 140 | Δύμη | Δ140 |
| 4112 | 141 | Δύνδασον | Δ141 |
| 4934 | 144 | Δυσπόντιον | Δ144 |
| 4936 | 145 | Δύστος | Δ145 |
| 5496 | 146 | Δωδώνη | Δ146 |
| 6072 | 149 | Δώριον | Δ149 |
| 6654 | 151 | Δώτιον | Δ151 |

### Billerbeck vol 3 - Gamma entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 7649 | 20 | ΓΑΘΗΙΑ | Γ20 |

### Billerbeck vol 3 - Nu entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 11895 | 63 | Νῖνος | Ν63 |
| 11896 | 64 | Νίσαια | Ν64 |
| 11897 | 65 | Νίσιβις | Ν65 |

### Billerbeck vol 3 - Kappa entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 32235 | 155 | Κόρακος πέτρα | Κ155 |
| 32236 | 156 | Κορακόνησος | Κ156 |
| 3265 | 157 | Κόραξ | Κ157 |
| 3266 | 158 | Κοραξοί | Κ158 |
| 3267 | 159 | Κόρδυλος | Κ159 |
| 3268 | 160 | Κορησσός | Κ160 |
| 3535 | 227 | Κρομύουσα | Κ227 |
| 3536 | 228 | Κρομμυών | Κ228 |
| 3537 | 229 | Κρόσσα | Κ229 |
| 3538 | 230 | Κρόταλλα | Κ230 |
| 3539 | 231 | Κρότων | Κ231 |

### Billerbeck vol 3 - Mu entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 10310 | 208 | Μονόγισσα | Μ208 |
| 10324 | 222 | Μοῦσειον | Μ222 |

### Billerbeck vol 4 - Sigma entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 32044 | 53 | Σανίνα | Σ53 |

### Billerbeck vol 4 - Pi entries

| ID | Entry# | Lemma | Billerbeck ID |
|----|--------|-------|---------------|
| 30135 | 280 | Πύλος | Π280 |
| 30136 | 281 | Πύξις | Π281 |
| 30137 | 282 | Πυξοϋς | Π282 |
| 30138 | 283 | Πυραία | Π283 |
| 30139 | 284 | Πυραμίδες | Π284 |
| 30140 | 285 | Πύραμος | Π285 |

## Verification

After execution, verify:
1. No entries remain with NULL/empty `billerbeck_id` (except Parisinus entries)
2. No duplicate entries for the same `entry_number` + `lemma` + `version`
3. All Billerbeck IDs follow the `[Letter][Number]` format

## SQL Commands

```sql
-- Phase 1: Delete incomplete duplicates
DELETE FROM lemma_images WHERE lemma_id IN (5216, 5786, 6364);
DELETE FROM proper_nouns WHERE lemma_id IN (5216, 5786, 6364);
DELETE FROM etymologies WHERE lemma_id IN (5216, 5786, 6364);
DELETE FROM proper_noun_aliases WHERE source_lemma_id IN (5216, 5786, 6364);
DELETE FROM assembled_lemmas WHERE id IN (5216, 5786, 6364);

-- Phase 2: Assign Billerbeck IDs
UPDATE assembled_lemmas SET billerbeck_id = 'Ε3' WHERE id = 6658;
UPDATE assembled_lemmas SET billerbeck_id = 'Ε4' WHERE id = 6659;
UPDATE assembled_lemmas SET billerbeck_id = 'Ε5' WHERE id = 6660;
UPDATE assembled_lemmas SET billerbeck_id = 'Ε43' WHERE id = 15968;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ140' WHERE id = 3842;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ141' WHERE id = 4112;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ144' WHERE id = 4934;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ145' WHERE id = 4936;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ146' WHERE id = 5496;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ149' WHERE id = 6072;
UPDATE assembled_lemmas SET billerbeck_id = 'Δ151' WHERE id = 6654;
UPDATE assembled_lemmas SET billerbeck_id = 'Γ20' WHERE id = 7649;
UPDATE assembled_lemmas SET billerbeck_id = 'Ν63' WHERE id = 11895;
UPDATE assembled_lemmas SET billerbeck_id = 'Ν64' WHERE id = 11896;
UPDATE assembled_lemmas SET billerbeck_id = 'Ν65' WHERE id = 11897;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ155' WHERE id = 32235;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ156' WHERE id = 32236;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ157' WHERE id = 3265;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ158' WHERE id = 3266;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ159' WHERE id = 3267;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ160' WHERE id = 3268;
UPDATE assembled_lemmas SET billerbeck_id = 'Μ208' WHERE id = 10310;
UPDATE assembled_lemmas SET billerbeck_id = 'Μ222' WHERE id = 10324;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ227' WHERE id = 3535;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ228' WHERE id = 3536;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ229' WHERE id = 3537;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ230' WHERE id = 3538;
UPDATE assembled_lemmas SET billerbeck_id = 'Κ231' WHERE id = 3539;
UPDATE assembled_lemmas SET billerbeck_id = 'Σ53' WHERE id = 32044;
UPDATE assembled_lemmas SET billerbeck_id = 'Π280' WHERE id = 30135;
UPDATE assembled_lemmas SET billerbeck_id = 'Π281' WHERE id = 30136;
UPDATE assembled_lemmas SET billerbeck_id = 'Π282' WHERE id = 30137;
UPDATE assembled_lemmas SET billerbeck_id = 'Π283' WHERE id = 30138;
UPDATE assembled_lemmas SET billerbeck_id = 'Π284' WHERE id = 30139;
UPDATE assembled_lemmas SET billerbeck_id = 'Π285' WHERE id = 30140;
```

## Date

Plan created: 2026-01-19
