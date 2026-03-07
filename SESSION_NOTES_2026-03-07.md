# Session Notes — 2026-03-07

Temporary handoff note from the March 2026 backlog review session.

## Important policy note

- Keep Billerbeck edition IDs visible on the public site.
- Do not expose Billerbeck Greek text publicly until the intellectual-property / licensing question has been resolved.
- Public Greek now prefers Meineke.

## Backlog status snapshot

- `echo TLG scan ; keep the page image but deprecate the Meineke OCR text` — treated as complete enough for now in the sense that page images remain linked and public Greek display no longer exposes the wrong edition text.
- `confirm that there aren't any [FrGrHist]` — complete enough for now; exact `FrGrHist` bracket issue appears gone.
- `lump author and title together` — done.
- `author first, punctuation then work name, then the book number then the fragment numbering system` — done enough for current production source displays.
- `should be some way of measuring the corrections done by Brady on the named entity matching` — still needs proper human-intervention / override tooling and reporting; this is the next substantial unfinished area.
- `style changes in poetry` — done.
- `add a commentary field that works at the phrase level` — done.

## Deployed state at stop point

- Public headword Greek display uses Meineke, not Billerbeck Greek.
- Translation markdown is rendered to HTML.
- Verse is shown as verse blocks on the site and in the PDF.
- `Λίβυς` PDF rendering issue is fixed.
- `Μίλητος` no longer turns the whole translation into a poetry block; only the quoted verse does.
- `status.cgi?version=1` returns build/version information.

## Next major unfinished topic

Human intervention for named entity matching / resolution:

- Human corrections should take priority over machine resolutions.
- Need to support:
  - “this was a wrong resolution; here is the corrected one”
  - “this does not need alignment”
  - “the AI missed this resolution”
- Need the usual two-layer data flow:
  - fast local SQLite for immediate edits
  - daily merge/sync back into PostgreSQL on `raksasa`
