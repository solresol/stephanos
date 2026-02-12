# Zero-Shot LLM Translation for Ancient Greek Lexicography: A Production-Grade Human-in-the-Loop Pipeline

## Abstract

We present a production-oriented pipeline for generating and reviewing English translations of ancient Greek lexicographic entries from *Stephanos of Byzantium*. The system uses off-the-shelf LLMs in zero-shot mode (no fine-tuning) and couples them with strict OCR JSON validation, database-backed provenance, prompt versioning, and human review tooling. Beyond translation, the same architecture extracts cited authors/works/fragments, people/deities/ethnic groups, aliases, etymologies, and geospatial place links; it also generates research-facing web pages and a PDF book. We focus on methodology rather than model novelty: how to make LLM translation dependable enough for large-scale scholarly workflows. We also introduce a structured comparison layer between Billerbeck-based Greek and Meineke-linked Greek, including translation-impact classification (`likely_different_translation`, `probably_same_translation`, `uncertain`). Results from operational use show that many observed textual differences are mechanical and non-translation-changing, while a smaller subset likely affects translation decisions. Finally, we outline a "Narrative Learning" loop in which recurrent human-AI correction deltas are distilled into explicit prompt updates. We release a reproducible architecture pattern for digital humanities tasks where correctness is cumulative and expert correction is mandatory.

## 1. Introduction

Large language models can generate fluent translations for historical languages, but production use in scholarship fails when systems optimize for output volume rather than correctness control. In ancient text workflows, three constraints dominate:

- OCR noise propagates quickly.
- Editorial traditions differ.
- Human correction remains essential.

Our goal is to design a system that takes these constraints as first-class requirements.

We report a deployed pipeline for the *Ethnika* corpus that:

- ingests page-linked image data,
- runs OCR with strict JSON output requirements,
- assembles lemma-level records,
- translates using zero-shot prompts,
- supports human correction and review in a dedicated interface,
- analyzes cross-edition textual differences for likely translation impact,
- derives structured scholarly metadata (sources, works, fragments, entities, aliases, etymologies, places).

The key contribution is an end-to-end operational method that makes zero-shot translation usable under expert supervision.

## 2. Task and Data Model

### 2.1 Unit of Work

The primary unit is a lemma record linked to one or more source page images. Each lemma contains:

- machine OCR Greek text,
- optional human-corrected Greek text,
- machine translation outputs (versioned),
- optional human translations,
- review metadata.

### 2.2 Provenance Requirements

Each stage writes explicit status flags and timestamps. Processing is idempotent by default: only records with `processed=0` are acted on. This minimizes accidental reprocessing and supports crash-safe reruns.

### 2.3 Editorial Alignment

The system links assembled lemmas to Meineke headword paragraphs using prioritized identifiers (`nodegoat_id`, `billerbeck_id`, `meineke_id`). This enables downstream comparison even when base working text comes from Billerbeck OCR. Each lemma also carries version metadata (e.g., `epitome`, `parisinus`, `synthetic`), which is preserved through analysis and publication layers.

## 3. System Architecture

### 3.1 Stage A: Ingestion

HTML/image registration and extraction populate image rows in PostgreSQL. Inputs remain immutable; metadata and processing fields are appended.

### 3.2 Stage B: OCR

OCR writes strict JSON to `images.lemma_json`. Failures are non-destructive:

- malformed JSON => no `processed=1` update,
- missing image => hard error,
- API failure => bubble to batch runner.

### 3.3 Stage C: Assembly

OCR JSON is normalized into lemma-level structures. Human correction fields are separate from machine fields.

### 3.4 Stage D: Translation

Translation uses zero-shot prompt templates with version tracking (`translation_prompt_version`). New prompt versions trigger targeted retranslation priority while preserving human edits.

### 3.5 Stage E: Review and Publication

A CGI review interface displays source images, Billerbeck Greek views, and cross-edition comparison status. Public/protected web pages are generated from DB snapshots for transparency and operations monitoring.

### 3.6 Stage F: Structured Enrichment Modules

After translation, additional forced-schema extraction jobs populate reusable research tables:

- proper noun extraction with explicit `role` (`source` vs `entity`) and `noun_type` (`person`, `place`, `people`, `deity`, `other`),
- source citation metadata (`citation`, `work_title`) enabling author/work/fragment indexing,
- alias extraction (Stephanos-stated aliases plus rule-based spelling variants),
- etymology extraction with controlled categories.

This design keeps all enrichment layers keyed to lemma IDs, so every derived claim remains auditable against source Greek and OCR provenance.

### 3.7 Stage G: Geospatial and Book Outputs

Place rows linked to coordinates and identifiers (Wikidata/Pleiades) are rendered into an interactive Leaflet map. A separate publishing step compiles a PDF book from database records, including indices for sources, persons, places, peoples, and deities, plus map integration.

## 4. LLM Methodology

### 4.1 Zero-Shot Constraint

No model fine-tuning is used. We intentionally test a low-assumption setup that many DH teams can replicate.

### 4.2 Prompt Governance

Prompts are stored as versioned rows. This creates:

- reproducibility across runs,
- auditable changes in translation style/coverage,
- controlled reprocessing policy.

### 4.3 Structured Difference Analysis

For lemmas where normalized Billerbeck-vs-Meineke class is `different`, we run forced-structure LLM analysis. Inputs are pre-cleaned to remove non-semantic artifacts:

- Billerbeck leading entry numbers,
- citation-heavy parenthetical wrappers.

Outputs include:

- difference level,
- mechanical pattern tags,
- word-pair substitutions,
- translation-impact class.

## 5. Evaluation Strategy

Our evaluation is workflow-centric rather than benchmark-centric.

### 5.1 What We Measure

- processing success/failure rates,
- number and category of Billerbeck-vs-Meineke differences,
- translation-impact distribution,
- human correction/review coverage,
- extraction coverage for sources/entities/aliases/etymologies,
- category-level and version-aware statistical signals.

### 5.2 Category and Version Analytics

The statistics layer computes both descriptive and model-based analyses:

- word-count distributions by lemma type and initial letter,
- ridge-regression models using proper noun features,
- per-category models (authors, historical figures, places, ethnic groups, deities),
- split analyses for Parisinus versus epitomised entries,
- etymology category distributions by version.

This framework allows us to ask not only "what was translated?" but also "what kinds of material were emphasized or compressed across textual traditions?"

### 5.3 Why This Matters

For this task, an aggregate BLEU-style metric would obscure the real risk profile. The key risk is not average lexical mismatch; it is the subset of entries where model output and textual base choices can mislead downstream scholarship.

## 6. Observed Outcomes (Operational)

From current operational runs:

- the majority of detected cross-edition differences are mechanical,
- a smaller subset is classified as likely translation-changing,
- uncertainty remains concentrated in not-yet-analyzed rows.

This validates a triage model:

- analyze all "different" rows over time,
- prioritize rows likely to change translation,
- route flagged rows to human review first.

## 7. Error Analysis

Common error classes include:

- OCR artifacts that survive token-level cleaning,
- citation-marker confusion,
- morphological drift in dense lexicographic formulae,
- over-smoothing in English rendering.

Mitigations that worked in practice:

- strict JSON validation gates,
- non-destructive failure handling,
- explicit comparison pre-cleaning,
- forced-schema LLM outputs,
- prompt version audits.

## 8. Human-in-the-Loop Design

The review interface is not an afterthought; it is the core quality mechanism. Effective elements include:

- immediate access to source images,
- side-by-side Billerbeck text states (raw OCR and comparison text),
- explicit Meineke-vs-Billerbeck status labels,
- direct edit links from analysis pages.

This reduces context-switching and speeds expert correction.

## 9. Narrative Learning Loop

We formalize prompt improvement as a data-driven narrative loop rather than parameter fine-tuning.

### 9.1 Input Signal

Primary signal is structured disagreement between:

- AI translation output,
- human-corrected or human-reviewed translation fields.

Each disagreement is linked to lemma metadata, source Greek, and review provenance.

### 9.2 Pattern Mining

At scheduled intervals, we sample reviewed deltas and ask an LLM to:

- identify recurrent error motifs,
- separate lexical/semantic issues from stylistic preference,
- propose concise correction heuristics with examples.

### 9.3 Prompt Update Protocol

Heuristics are converted into a new prompt version only after human approval. We then:

1. run targeted retranslation on a validation subset,
2. compare correction rates and reviewer effort against the prior version,
3. promote or rollback based on observed impact.

This produces a text-level learning trajectory that is interpretable and auditable. It aligns with your "Narrative Learning" framing (arXiv preprint citation to be inserted), where system improvement is encoded as explicit narrative constraints.

## 10. Operational Lessons

1. Idempotency is non-negotiable for long-running pipelines.
2. "Parse first, mark processed later" prevents silent queue loss.
3. Prompt versioning is as important as model versioning.
4. Editorial comparison should be modeled as data, not narrative notes.
5. Small UI changes in review tools can have large impact on annotation throughput.

## 11. Limitations and Threats to Validity

- No gold-standard aligned translation benchmark is yet complete.
- Human review depth may vary by entry.
- Translation-impact labels are model-assisted and still need expert confirmation.
- Results are reported from one corpus/domain and may not transfer unchanged.

## 12. Ethics and Scholarly Safety

We treat model output as provisional. The system is designed to prevent hidden automation authority:

- explicit review states,
- tracked human edits,
- no automatic overwrite of curated fields,
- public distinction between machine and human outputs.

For classical scholarship, this separation is critical.

## 13. Conclusion

A zero-shot LLM setup can support ancient Greek translation workflows at scale if embedded in a strict, provenance-rich, human-supervised architecture. Our contribution is a deployable pattern for digital humanities teams: combine conservative data engineering with targeted model usage, and treat review as a first-class system component.

## Reproducibility Notes

To replicate the method:

1. Use idempotent stage flags for each processing phase.
2. Require strict machine-readable OCR payloads.
3. Separate machine and human correction columns.
4. Version translation prompts and retranslation policy.
5. Add structured cross-edition comparison with pre-cleaning.
6. Expose review-centric pages with direct record-level edit links.

## Placeholder References

- Prior work on machine translation for historical languages.
- LLM reliability and structured output control.
- Human-in-the-loop annotation systems.
- Digital philology workflows for classical corpora.
- [Your Name], "Narrative Learning" (arXiv preprint; add full citation details).
