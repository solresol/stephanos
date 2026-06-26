# Duke DDbDP `πρός` / `πλησίον` Baseline

Date: 2026-06-20

Purpose: establish a first external documentary-Greek baseline for the Stephanos hypothesis that choosing `πλησίον` where `πρός` could be used may be a stylistic or epitomizing fingerprint.

Data source: PostgreSQL database `dukedbt` on `raksasa`, table `documents`, field `ddb_content`. The full runs `2024-08` and `2025-03` have identical source-text counts; the counts below use `run_name = '2025-03'`.

Method: direct scan of extracted Greek source text, not AI translations. Greek-script tokens were normalized by lowercasing, stripping diacritics, converting lunate sigma to sigma, and normalizing final sigma. Counts are surface-token counts. `πρός + DAT` is a high-confidence proxy where normalized `πρός` is followed by a dative article/pronoun token (`τῷ`, `τῇ`, `τοῖς`, `ταῖς`, `αὐτῷ`, etc.).

## Corpus Counts

- Documents: 8,147
- Greek-script tokens: 1,621,153
- Raw `πρός` occurrences: 4,107
- `πλησίον` occurrences: 6
- High-confidence `πρός + DAT` occurrences: 246
- Documents with raw `πρός`: 1,915
- Documents with `πλησίον`: 6
- Documents with high-confidence `πρός + DAT`: 180

## Rates

| Measure | Rate |
| --- | ---: |
| Raw `πρός` per 1,000 Greek tokens | 2.533 |
| `πλησίον` per 1,000 Greek tokens | 0.00370 |
| High-confidence `πρός + DAT` per 1,000 Greek tokens | 0.152 |
| Raw `πρός` document rate | 23.5% |
| `πλησίον` document rate | 0.074% |
| High-confidence `πρός + DAT` document rate | 2.21% |
| Raw `πρός` : `πλησίον` occurrence ratio | 684.5 : 1 |
| High-confidence `πρός + DAT` : `πλησίον` occurrence ratio | 41.0 : 1 |

## `πλησίον` Documents

Only six DDbDP documents in this extraction contain `πλησίον`:

| DDbDP ID | Greek tokens | Raw `πρός` | `πλησίον` | High-confidence `πρός + DAT` |
| --- | ---: | ---: | ---: | ---: |
| `p.genova;3;100` | 34 | 0 | 1 | 0 |
| `p.haun;2;26` | 34 | 0 | 1 | 0 |
| `p.muench;1;8` | 689 | 2 | 1 | 1 |
| `p.oxy;47;3332` | 91 | 0 | 1 | 0 |
| `p.oxy;59;3978` | 123 | 0 | 1 | 0 |
| `p.petr;2;18` | 160 | 0 | 1 | 0 |

The hits are real Greek text, not translation output or HTML chrome. They are mostly documentary locative/property contexts, for example `τὰ πεδία ὧν πλησίον ...`, `τὸ κάστρον ... τὸ πλησίον`, and `ἐν τῇ μητροπόλει πλησίον τοῦ Μενδησίου`.

## Initial Interpretation

The DDbDP baseline makes `πλησίον` look extremely rare in documentary Greek: about one occurrence per 270,000 Greek tokens in this extraction. Raw `πρός` is common, and even the stricter `πρός + DAT` proxy is much more common than `πλησίον`.

This means that a `πρός` / `πλησίον` ratio can be useful as a corpus-level contrast between Stephanos-style geographical prose and documentary papyri, but DDbDP probably does not contain enough `πλησίον` hits to test author-level style for this feature alone. It could still be one feature in a larger stylometric vector, especially if combined with other locative constructions and controlled by document type, date, place, and formulaic register.
