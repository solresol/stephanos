# Verified Human Translation Greek Word Count Policy

Generated: 2026-06-12T23:44:57+10:00

Purpose: reconcile the two live counts mentioned in the June 11 meeting and pin the source-text policy for paper-facing numbers.

## Canonical Policy

- Database: live `stephanos` PostgreSQL on `DB_HOST=raksasa`, `DB_USER=stephanos`.
- Verified human translation set: distinct `human_translations.lemma_id` where:
  - `status = 'approved'`
  - `stage IN ('reviewed', 'final')`
  - `translation_text` is non-empty after trimming
- Greek source text: current public `lemma_source_text_versions.text_body`, using the shared source policy `kiesling` before `meineke`.
- Fallback only when no current public source text exists: `assembled_lemmas.human_greek_text`, then `corrected_greek_scan`, then `greek_text`.
- Greek word rule: count runs matching `[\u0370-\u03FF\u1F00-\u1FFF]+`.

## Result

- Verified passages: 90
- Version distribution: {'epitome': 90}
- Canonical Greek words: 2927
- Legacy assembled/manual Greek words: 2951
- Difference: -24 canonical minus legacy
- Canonical source distribution: {'meineke': 89, 'kiesling': 1}

The paper-safe count for the current live snapshot is therefore **2,927 Greek words across 90 verified human-translated epitome passages**.

The earlier 2,951-word count came from the legacy assembled/manual text chain rather than the current public source-text policy. The verified passage set did not change.

## Reconciliation Rows

21 entries differ between the canonical and legacy text policies.

| Lemma ID | Entry | Lemma | Source | Canonical words | Legacy words | Delta |
|---:|---:|---|---|---:|---:|---:|
| 2054 | 1 | Καβαλίς | meineke/csv_fallback | 47 | 45 | +2 |
| 2055 | 2 | Καβασσός | meineke/csv_fallback | 74 | 75 | -1 |
| 2077 | 14 | Καιρή | meineke/csv_fallback | 11 | 12 | -1 |
| 2082 | 19 | Καλάμαι | meineke/csv_fallback | 5 | 6 | -1 |
| 2083 | 20 | Καλαμένθη | kiesling/manual | 16 | 17 | -1 |
| 2087 | 24 | Καλαύρεια | meineke/csv_fallback | 20 | 21 | -1 |
| 2115 | 26 | Καλὴ ἀκτή | meineke/csv_fallback | 49 | 52 | -3 |
| 2119 | 30 | Κάλλατις | meineke/csv_fallback | 47 | 48 | -1 |
| 2342 | 48 | Κάμιρος | meineke/csv_fallback | 47 | 48 | -1 |
| 2455 | 53 | Κάναστρον | meineke/csv_fallback | 43 | 55 | -12 |
| 2465 | 63 | Κάνωπος | meineke/csv_fallback | 62 | 63 | -1 |
| 2470 | 68 | Καππαδοκία | meineke/csv_fallback | 59 | 62 | -3 |
| 2477 | 75 | Καρδαμύλη | meineke/csv_fallback | 35 | 34 | +1 |
| 2484 | 82 | Καρία | meineke/csv_fallback | 194 | 199 | -5 |
| 2602 | 102 | Καρύανδα | meineke/csv_fallback | 25 | 24 | +1 |
| 2603 | 103 | Κάρυστος | meineke/csv_fallback | 138 | 139 | -1 |
| 2625 | 125 | Κατακεκαυμένη | meineke/csv_fallback | 34 | 33 | +1 |
| 7244 | 288 | Κυρήνη | meineke/csv_fallback | 35 | 33 | +2 |
| 7249 | 293 | Κύρρος | meineke/csv_fallback | 33 | 32 | +1 |
| 7252 | 296 | Κύρτωνες | meineke/csv_fallback | 20 | 17 | +3 |
| 7259 | 303 | Κύφος | meineke/csv_fallback | 41 | 44 | -3 |

Full snippets for these rows are saved in `paper/notes/2026-06-12-verified-human-translation-word-count-diffs.csv`.

## Citable Wording

In the live June 2026 Stephanos database snapshot, the verified human-translation set contained 90 approved reviewed/final epitome passages. Counting Greek-script word runs in the current public source text for each passage, using the shared source precedence Kiesling then Meineke and falling back to manual/OCR text only when no current public source exists, gives 2,927 Greek words.

## Caveat

This is still a live-database snapshot. Rerun this script after freezing the reviewed-passage set and source-text policy for any submitted paper.
