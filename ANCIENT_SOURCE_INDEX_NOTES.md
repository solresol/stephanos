# Ancient Source Index Notes

The PDF `Index of Ancient Sources` currently has a recurring data-quality problem:
the same source can surface under multiple English labels, and modern editors can
leak into the same index as if they were ancient authorities.

For now, `generate_pdf_book.py` applies a small manual cleanup layer that:

- suppresses a short list of obvious modern-editor labels in the PDF-only source index,
- merges a few obvious transliteration/name duplicates such as `Apollonius Rhodius`
  and `Apollonius of Rhodes`.

This is intentionally narrow and pragmatic, not a full authority-control solution.

Better follow-up options:

1. Add a curated canonical source-authority table in PostgreSQL and have the site,
   PDF, exports, and review tools all read from it.
2. Split source mentions into `ancient_author`, `ancient_work`, `modern_editor`,
   and similar roles so the PDF can exclude non-ancient material structurally.
3. Add a duplicate-lint report that groups source labels by normalized English form
   and flags likely collisions before PDF generation.
