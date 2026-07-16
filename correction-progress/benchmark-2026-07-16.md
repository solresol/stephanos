# Stephanos benchmark corrections - 16 July 2026

## Metadata

- Generated at: `2026-07-16T11:42:20.110552+00:00`
- Annotated PDF: `/Users/gregb/Downloads/stephanos_llm_translation_benchmark_draft-corrections16jul2026.pdf`
- Annotated PDF SHA-256: `39adfdc6aaa30358f2e94e6b5044029f0570157dfe46640aeb6abba1456d676d`
- Annotated PDF pages: `19`
- Annotated PDF file size: `621246 bytes`
- Base PDF: `/Users/gregb/Documents/devel/stephanos/output/pdf/stephanos_llm_translation_benchmark_draft.pdf`
- Base PDF SHA-256: `b377a12dc8a78055ddcf308770a973da598e67cd91dc848be2acf9b9fa5bb62f`
- Base PDF pages: `19`
- Base PDF file size: `274080 bytes`
- Preserved base copy: `/Users/gregb/.codex/document-correction-bases/stephanos/stephanos-llm-translation-benchmark-draft-corrections16jul2026/stephanos_llm_translation_benchmark_draft.pdf`
- Rendered work directory: `/Users/gregb/Documents/devel/stephanos/scratch/stephanos-llm-translation-benchmark-draft-corrections16jul2026`
- Base-versus-annotated diff: `scratch/stephanos-llm-translation-benchmark-draft-corrections16jul2026/annotation-diff.json`
- Added-annotation candidate pages: `1-5, 7-8, 10-12`
- Simple blue detector false positives: pages `7, 9, 18, 19` contain blue chart marks; base differencing showed no added ink on pages `9, 18, 19`

## Repository baseline

- Annotated-source baseline branch: `codex/benchmark-corrections-2026-07-16-baseline`
- Baseline PR: https://github.com/solresol/stephanos/pull/9
- Status: merged; remote branch deleted
- Verification: Python sources compiled; the checksummed 19-page base PDF was built from this source

## Correction inventory

Every coherent annotation instruction has one PR. The separately requested Metaculus addition also has its own PR.

1. Page 1 title replacement - PR: #10 - `codex/benchmark-2026-07-16-p001-title`
2. Page 1 abstract rewrite - PR: #11 - `codex/benchmark-2026-07-16-p001-abstract`
3. Page 2 automation rationale - PR: #12 - `codex/benchmark-2026-07-16-p002-automation-rationale`
4. Page 2 introduction framing - PR: #13 - `codex/benchmark-2026-07-16-p002-introduction-framing`
5. Page 2 corpus description - PR: #14 - `codex/benchmark-2026-07-16-p002-corpus-description`
6. Page 3 remove source/provenance section - PR: #15 - `codex/benchmark-2026-07-16-p003-remove-provenance`
7. Page 3 show exact v1 prompt and recogniser examples - PR: #16 - `codex/benchmark-2026-07-16-p003-prompt-examples`
8. Page 3 disclose prompt-development/test overlap - PR: #17 - `codex/benchmark-2026-07-16-p003-development-overlap`
9. Page 4 introduce Claude comparison directly - PR: #18 - `codex/benchmark-2026-07-16-p004-claude-intro`
10. Page 4 remove run-identifier footnote - PR: #19 - `codex/benchmark-2026-07-16-p004-remove-footnote`
11. Page 4 describe six metrics concisely - PR: #20 - `codex/benchmark-2026-07-16-p004-six-metrics`
12. Page 5 remove length-slope gloss - PR: #21 - `codex/benchmark-2026-07-16-p005-remove-slope-gloss`
13. Page 5 define the 90% projection as human-level agreement - PR: #22 - `codex/benchmark-2026-07-16-p005-human-agreement-projection`
14. Page 5 clarify Table 1 averaging - PR: #23 - `codex/benchmark-2026-07-16-p005-table-description`
15. Page 7 qualify the learned-metric interpretation - PR: #24 - `codex/benchmark-2026-07-16-p007-learned-metric-interpretation`
16. Page 8 shorten the Claude-results heading - PR: #25 - `codex/benchmark-2026-07-16-p008-claude-heading`
17. Pages 8 and 10 retain three qualitative samples - PR: #26 - `codex/benchmark-2026-07-16-p008-three-samples`
18. Page 10 focus the prompt-discussion heading - PR: #27 - `codex/benchmark-2026-07-16-p010-discussion-heading`
19. Page 10 state the human-plus-AI workflow finding - PR: #28 - `codex/benchmark-2026-07-16-p010-workflow-finding`
20. Page 11 add the headline forecast - PR: #29 - `codex/benchmark-2026-07-16-p011-headline-forecast`
21. Page 11 simplify the model-progress discussion - PR: #30 - `codex/benchmark-2026-07-16-p011-model-progress`
22. Page 11 condense the human-quality-date section - PR: #31 - `codex/benchmark-2026-07-16-p011-human-quality-date`
23. Page 11 remove the generic limitations opener - PR: #32 - `codex/benchmark-2026-07-16-p011-limitations-opening`
24. Page 12 remove the conclusion - PR: #33 - `codex/benchmark-2026-07-16-p012-remove-conclusion`
25. Page 12 remove data/code availability - PR: #34 - `codex/benchmark-2026-07-16-p012-remove-data-availability`
26. Separate requested Metaculus comparison - PR: #35 - `codex/benchmark-2026-07-16-metaculus-comparison`

## Page ledger

### Page 001

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: title replacement (#10); abstract rewrite and requested forecast/easy-improvement summary (#11)
- Verification: both branches rebuilt successfully
- Unresolved questions: none

### Page 002

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: automation sentence (#12); introduction framing (#13); corpus description (#14)
- Verification: all three branches rebuilt successfully
- Unresolved questions: none

### Page 003

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: remove provenance section (#15); show exact live v1 prompt and live recogniser examples (#16); disclose twenty-item overlap (#17)
- Verification: all three branches rebuilt successfully; prompt and examples checked against the live PostgreSQL database
- Unresolved questions: none

### Page 004

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: Claude introduction (#18); remove footnote (#19); six-metric description (#20)
- Verification: all three branches rebuilt successfully
- Unresolved questions: none

### Page 005

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: remove slope gloss (#21); human-agreement projection wording (#22); Table 1 averaging wording (#23)
- Verification: all three branches rebuilt successfully
- Unresolved questions: none

### Page 006

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base-versus-annotated comparison

### Page 007

- Status: all annotations have a PR
- Source: `paper/benchmark_translation_draft.md`
- Changes: learned-metric heading, opening, and naive-interpretation qualifier (#24)
- Verification: branch rebuilt successfully
- Unresolved questions: none

### Page 008

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: Claude heading (#25); rename sample section and retain three examples (#26)
- Verification: both branches rebuilt successfully
- Unresolved questions: none

### Page 009

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: blue marks are part of the base charts; no added marks in base differencing

### Page 010

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: delete fourth sample (#26); simplify discussion heading and v1 wording (#27); replace struck paragraph with workflow finding (#28)
- Verification: all branches rebuilt successfully
- Unresolved questions: none

### Page 011

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: headline forecast (#29); model-progress wording (#30); human-quality date condensation (#31); limitations opener (#32)
- Verification: all four branches rebuilt successfully
- Unresolved questions: none

### Page 012

- Status: all annotations have PRs
- Source: `paper/benchmark_translation_draft.md`
- Changes: remove conclusion (#33); remove data/code availability (#34)
- Verification: both branches rebuilt successfully
- Unresolved questions: none

### Page 013

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base differencing

### Page 014

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base differencing

### Page 015

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base differencing

### Page 016

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base differencing

### Page 017

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: no added marks in base differencing

### Page 018

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: blue marks are part of the base charts; no added marks in base differencing

### Page 019

- Status: visually reviewed; no annotations
- Branch: N/A
- PR: N/A
- Verification: blue marks are part of the base charts; no added marks in base differencing

## Progress document

- Branch: `codex/benchmark-2026-07-16-progress`
- PR: https://github.com/solresol/stephanos/pull/36
- Commit/push: committed and pushed

## Audit conclusion

- Annotated pages: `10 / 19`
- Coherent annotated corrections: `25`
- Separately requested additions: `1`
- Correction/change PRs: `26`
- Annotated corrections without a PR: `0`
- Blocked or ambiguous corrections: `0`
