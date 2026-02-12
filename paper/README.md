# Paper Drafts

This directory contains manuscript drafts based on the current Stephanos pipeline work.

- `classical_review_draft.md`: Draft in a Classical Review style (philological audience).
- `computing_venue_draft.tex`: Draft in a computing-journal/conference style (NLP/HCI/DH audience), in LaTeX format.
- `Makefile`: Build targets for PDF/DOCX outputs.

Both drafts are intentionally practical and methodology-focused:

- zero-shot, off-the-shelf LLM use
- OCR-to-translation pipeline design
- human review and correction loops
- editorial-base differences (Billerbeck vs Meineke)
- source/work/fragment extraction and named-entity layers
- aliases, etymologies, and category-based statistics
- places map and PDF publication outputs
- Narrative Learning prompt-improvement loop

Build commands:

- `cd paper && make computing-pdf` to build `build/computing_venue_draft.pdf`
- `cd paper && make classical-pdf` to build `build/classical_review_draft.pdf`
- `cd paper && make classical-docx` to build `build/classical_review_draft.docx`
- `cd paper && make all` to build all outputs
