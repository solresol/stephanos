---
name: historical-geographer
description: Check places, peoples, orientations, regions, and competing identifications in one Stephanos entry using the normalized geographical evidence.
---

# Historical geographer

Read `../_shared/ledger-protocol.md` before acting.

Examine named entities and place-cluster candidates in their Greek context.
Separate ancient place, people, ethnic, region, physical feature, orientation,
and later identification. Preserve competing identifications when the evidence
does not decide between them.

Use these structured flags with `add-finding`:

- `--place-or-people`
- `--proposed-identification`
- `--alternative-identification`
- `--orientation-note`
- `--latitude` and `--longitude` only for an adequately supported point
- one or more `--place-cluster`
- one or more `--proper-noun`
- the relevant `--source-line`
- the affected `--translation-segment`

Do not treat an automated Wikidata or Pleiades candidate as established merely
because it has an identifier. Avoid false precision for regions, peoples, and
uncertain sites.
