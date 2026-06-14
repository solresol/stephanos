# Brady Placeholder Entity-Harvesting Policy

Generated: 2026-06-13T11:35:35+10:00

Purpose: turn the June 11 meeting discussion about Brady's Latin-letter placeholder names into a concrete entity-harvesting policy and live audit.

## Source

- Database: live `stephanos` PostgreSQL on `DB_HOST=raksasa`, `DB_USER=stephanos`.
- Latest ToposText snapshot: `35` (`unchanged`), fetched `2026-06-13T10:00:06.961980+10:00`.
- Snapshot path recorded in DB: `data/topostext_snapshots/20260610-000006Z/E411StephanusByzGreek.html`.
- Entries in staging: 3,664.
- Entity/tag mentions in staging: 32,302.
- Row-level audit CSV: `exports/brady_placeholder_entity_audit.csv`.

## Decision

Use Brady's Latin-letter labels and placeholder-coded tags as entity-harvesting evidence, but only as review hints. They should seed authority searches, tag/type suggestions, and work queues; they should not become canonical entity IDs or canonical labels without later human confirmation.

Translation and OCR work should not wait for Brady to finish adding these labels. The pipeline can use the labels where they already exist and fall back to the Greek text, current tags, and existing authority lookup elsewhere.

## Operational Policy

- `JJ` means Brady searched and did not find a good existing ID. Queue as `needs_new_topostext_id` and treat the Latin stem as a proposed local search label.
- `YY` means Brady did a quick pattern search but not a full authority search. Queue as `needs_deep_search`; use the Latin stem to search Wikidata, RE, Pleiades, and ToposText.
- `zzz` means unresolved inline authority markup. Queue as `needs_authority_id`; use nearby Greek context, tag type, place-type terms, region hints, and any nearby bracketed Latin label as weak search evidence.
- Bracketed Latin labels inside entry text, such as `[ Axia ]`, are local disambiguation hints. Use them to improve review queues and candidate searches, not to overwrite Greek text or automatically merge entities.
- Suggested tag changes from place-type terms, such as `PRN` to `place` or `ethnic`, should remain generated hints until reviewed.
- Any downstream canonical entity table or public export should require a confirmed authority link, a reviewed local ID decision, or an explicit unresolved status. Placeholder strings themselves are not public-safe identifiers.

## Live Placeholder Counts

| Code | Mentions | Entries | Distinct tag IDs | With RE candidates | With tag suggestion |
| --- | ---: | ---: | ---: | ---: | ---: |
| JJ | 143 | 83 | 94 | 57 | 3 |
| YY | 736 | 400 | 406 | 275 | 15 |
| ZZZ | 12,495 | 3,432 | 1 | 607 | 780 |

## Live Authority Queue Counts

| Authority class | Action status | Placeholder code | Mentions |
| --- | ---: | ---: | ---: |
| zzz | needs_authority_id | ZZZ | 12,495 |
| topostext_like | candidate_import | - | 10,635 |
| wikidata | candidate_import | - | 6,412 |
| pleiades_numeric | candidate_import | - | 847 |
| re | needs_re_subject_item | - | 766 |
| yy_placeholder | needs_deep_search | YY | 736 |
| jj_placeholder | needs_new_topostext_id | JJ | 143 |
| re | needs_re_definition_match | - | 128 |
| other | needs_authority_classification | - | 109 |
| re | re_enriched | - | 27 |
| missing | needs_markup_fix | - | 3 |
| brady_local | local_identifier_review | - | 1 |

## Bracketed Latin Labels

The staged entry text contains 192 bracketed Latin-label occurrences across 88 entries, with 102 distinct labels.

| Label | Occurrences |
| --- | ---: |
| Herakleia | 18 |
| Alexandria | 16 |
| Antiocheia | 11 |
| Apollonia | 9 |
| Nysa | 8 |
| Aigai | 7 |
| Dia | 4 |
| Arne | 3 |
| Achilleion | 3 |
| Ainos | 3 |
| Daskylion | 3 |
| Herakleion | 3 |
| Nikaia | 3 |
| Oropos | 3 |
| Pherai | 3 |
| Adana | 2 |
| Akanthos | 2 |
| Akragas | 2 |
| Alea | 2 |
| Demetrias | 2 |

## Example JJ Rows

| Entry | Tag | ID | Surface | Queue | Suggested tag | Type term | Region hint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 241:A101.1 | place | AntissaJJ | Ἄντισσα | needs_new_topostext_id | - | πόλις | Λέσβου |
| 241:A101.1 | place | AntissJJ | Ἄντισσα | needs_new_topostext_id | - | - | - |
| 241:A110.19 | place | ArbanionJJ | Arbanion | needs_new_topostext_id | - | πόλις | Πόντῳ |
| 241:A110.19 | place | ArbanionJJ | Ἀρβάνιον | needs_new_topostext_id | - | πόλις | Πόντῳ |
| 241:A118.4 | ethnic | ArianoiJJ | Arianoi | needs_new_topostext_id | - | ἔθνος | προσεχὲς |
| 241:A122.6 | place | HarmataJJ | Ἅρματα | needs_new_topostext_id | - | - | - |
| 241:A127.4 | place | ArtaiaJJ | Artaia | needs_new_topostext_id | - | χώρα | ἣν |
| 241:A137.14 | prn | OlbiaJJ | Ὀλβίας | needs_new_topostext_id | - | - | - |

## Example YY Rows

| Entry | Tag | ID | Surface | Queue | Suggested tag | Type term | Region hint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 241:A101.11 | prn | AntronYY | Antron | needs_deep_search | place | ἄντρον | σπήλαιον |
| 241:A105.17 | place | ApokopaYY | Apokopa | needs_deep_search | - | κόλπος | Βαρβαρικῷ |
| 241:A105.17 | place | ApokopaYY | Ἀπόκοπα | needs_deep_search | - | κόλπος | Βαρβαρικῷ |
| 241:A105.20 | prn | PhrygiaYY | Phrygia | needs_deep_search | - | - | - |
| 241:A105.20 | prn | ApollonioYY | Apollonion | needs_deep_search | - | - | - |
| 241:A108.13 | prn | ArazusYY | Ἀράζου | needs_deep_search | - | - | - |
| 241:A112.18 | place | ArgosYY | Ἄργος Ὀρέστιον | needs_deep_search | - | πεδίον | θάλασσαν |
| 241:A115.12 | place | ArgyrosYY | Argyros | needs_deep_search | - | πόλις | Φίλιστος |

## Example ZZZ Rows

| Entry | Tag | ID | Surface | Queue | Suggested tag | Type term | Region hint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 241:3,1.190 | prn | zzz | Κρητική | needs_authority_id | place | πόλις | Κρητική |
| 241:A100.15 | prn | zzz | Ἀντωνίου | needs_authority_id | - | - | - |
| 241:A100.15 | prn | zzz | Ἀντιπατρίτης | needs_authority_id | - | - | - |
| 241:A100.17 | prn | zzz | Δατηνῶν | needs_authority_id | place | ἐπίνειον | Δατηνῶν |
| 241:A100.17 | prn | zzz | Τισάρη | needs_authority_id | - | - | - |
| 241:A100.17 | prn | zzz | Ἀντισαρεύς | needs_authority_id | - | - | - |
| 241:A100.17 | prn | zzz | Ἀντικυρεύς | needs_authority_id | - | - | - |
| 241:A100.17 | prn | zzz | Ἀντικύρας | needs_authority_id | - | - | - |

## Implemented Engineering Step

Implemented on 2026-06-13: the ToposText intake pipeline now classifies `JJ`, `YY`, and `zzz`, generates place/type hints, and stores RE candidates and bracketed Latin labels in typed tables rather than JSONB hint payloads. The review exports keep bracketed Latin labels visibly marked as weak hints.

## Meeting Link

This resolves the June 11 task: use Brady's Greek-text labels where the pattern already exists, but do not make translation wait for complete coverage.
