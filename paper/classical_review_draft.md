# A Practical Note on Zero-Shot LLM Translation for Stephanos of Byzantium

## Abstract

This paper reports a practical workflow for producing serviceable English translations of entries in *Stephanos of Byzantium, Ethnika* using zero-shot, off-the-shelf large language models (LLMs). The core claim is modest: with careful pipeline design, strict data handling, and human review, zero-shot models can produce translations useful for research navigation and first-pass interpretation, even in a difficult ancient Greek lexicographic corpus. The project does not aim to replace philological judgment. Rather, it aims to reduce mechanical bottlenecks and to make large-scale review tractable. We describe the full workflow (image extraction, OCR, lemma assembly, translation, and review), plus structured extraction of sources, works, fragments, named entities, aliases, and etymologies; geospatial linking and map generation; and PDF publication outputs. We show why idempotent processing and provenance tracking are essential, and discuss the role of editorial variation between Billerbeck and Meineke. We also propose a "Narrative Learning" loop: recurrent human-versus-AI correction patterns are summarized and turned into controlled prompt revisions. We argue that digital philology benefits most when LLM outputs are treated as revisable scholarly artifacts, not as final authority.

## 1. Scope and Claim

The present note addresses a specific question: can one obtain usable first-pass translations of the *Ethnika* by applying a modern LLM in zero-shot mode, without model fine-tuning, and still preserve a philologically responsible review process?

Our answer is yes, with qualifications.

The qualification is the important part. "Usable" here means serviceable for:

- search and triage,
- preliminary reading across large batches,
- identifying passages that require close editorial or linguistic attention.

It does not mean publication-ready translation by default. The pipeline is explicitly built around correction, provenance, and retranslation.

## 2. Materials and Editorial Context

The corpus consists of OCR-derived Greek text from image pages linked to assembled lemma records. The workflow tracks relations among:

- page images,
- OCR JSON outputs,
- assembled lemma rows,
- translation outputs,
- human corrections and review states.

Because the project works across Billerbeck and Meineke traditions, editorial variance is expected. This is not noise; it is part of the textual reality. A central methodological decision, therefore, was to compare Billerbeck-based working Greek with linked Meineke paragraphs in a structured way, including:

- deterministic normalization classes (`same`, `tone_marks_only`, `different`),
- targeted LLM analysis for "different" rows,
- explicit translation-impact labels.

This step was needed because not every textual difference implies a translation difference.

## 3. Pipeline Design

The pipeline is intentionally conservative and idempotent.

### 3.1 Ingestion and OCR

Image records are extracted from source HTML and stored in PostgreSQL with stable linkage to originating files. OCR operates only on unprocessed rows and writes strict JSON payloads back to the database. If JSON parsing fails, rows remain unprocessed.

This one design choice prevents the most common failure mode in automated philological pipelines: silent corruption by partial writes.

### 3.2 Lemma Assembly

OCR JSON is assembled into lemma-level records. Human correction fields are separated from machine-derived fields. This creates an explicit distinction between:

- raw OCR Greek,
- human-corrected Greek,
- best-available Greek for downstream translation.

### 3.3 Translation

Translation is performed in zero-shot mode with versioned prompts. Prompt versioning matters because it allows controlled retranslation and historical comparison of outputs. Human translations are never overwritten automatically.

### 3.4 Review Interface

The review system places source images, Billerbeck Greek, and comparison metadata into one operational view. In current form, it includes:

- raw OCR text,
- Billerbeck text used for comparison (if corrected),
- Meineke-vs-Billerbeck status,
- model-generated difference summaries and impact labels where available.

The review environment is therefore not merely an annotation surface; it is the project's critical quality gate.

### 3.5 Source, Work, Fragment, and Entity Extraction

After translation, a structured extraction layer identifies proper nouns with forced-schema output (`person`, `place`, `people`, `deity`, `other`) and role labels (`source` vs `entity`). This distinction is crucial: an ancient author cited as evidence is not treated as the same analytical object as a figure inside an aetiological narrative.

From the same structured data, the system generates:

- author/source pages,
- works-cited pages,
- FGrHist/fragment indices,
- entity pages for persons and deities,
- dedicated pages for ethnic groups.

In this way, citation analysis and narrative-entity analysis share one provenance model but remain analytically distinct.

### 3.6 Aliases and Etymologies

Two additional extraction passes support philological interpretation:

- alias extraction, which detects explicit renaming formulas in Greek (e.g. "was called", "is called"), and
- etymology extraction, which stores Greek evidence, English explanation, and one of six controlled categories (eponym person, morphological composition, place transfer, non-Greek borrowing, folk-narrative etymology, unclear/metalinguistic).

Aliases are also expanded with rule-based spelling variants, so users can move between Greek and Latinized naming traditions more effectively.

### 3.7 Version-Aware and Publication Outputs

Each lemma carries a version signal (e.g., epitome or Parisinus) so that statistical and interpretive analyses can be split by textual tradition rather than merged into a single average. The project also generates:

- a geocoded places map (Wikidata/Pleiades-linked where available),
- a downloadable PDF book with indices (sources, persons, places, peoples, deities) and map integration.

These outputs make the translation workflow usable as a research environment, not merely a backend process.

## 4. Why Zero-Shot Was Enough to Start

Fine-tuning was intentionally deferred. The practical reason is straightforward: for an initial corpus-scale build, engineering time was better spent on robust data flow, observability, and correction loops than on bespoke model training.

Zero-shot outputs, if embedded in a strict pipeline, already provide:

- broad lexical coverage,
- coherent sentence-level English for many entries,
- adequate baseline quality for human revision.

The major risks (hallucinated expansions, citation confusion, and overconfident paraphrase) are manageable when each output is tied to source text, tracked by version, and reviewed by a human editor.

## 5. Serviceable Translation as a Methodological Category

The phrase "serviceable translation" is used here deliberately. It is a working category between raw machine output and critical translation.

A serviceable translation should:

- preserve the basic referential content,
- avoid major semantic inversion,
- remain close enough to support philological checking against Greek,
- flag uncertainty when necessary.

In this project, serviceability is not inferred from model confidence. It is inferred from workflow behavior:

- correction frequency,
- downstream review load,
- stability across prompt versions,
- alignment with known textual variants,
- agreement with structured analytics (etymology class distributions, category-specific citation/entity patterns, and version-aware comparisons).

## 6. Billerbeck-Meineke Difference Analysis

A separate analysis stage evaluates whether switching base text would likely change translation outcomes. This stage applies forced-structure model reporting and records:

- difference type,
- mechanical patterns,
- candidate word-pair substitutions,
- translation impact class (`likely_different_translation`, `probably_same_translation`, `uncertain`).

Crucially, non-substantive artifacts are filtered before model comparison, including:

- leading entry numbers in Billerbeck,
- citation-style parentheticals.

Without this filtering, mechanical editorial markup would be mistaken for semantic divergence.

## 7. Scholarly Value

For a philological audience, the value of this method is not that it automates interpretation. Its value is that it scales editorially informed reading.

Three gains are immediate:

1. Better triage: one can prioritize entries where textual variation is likely to affect translation.
2. Better transparency: each translation can be traced to source image, OCR, assembly state, prompt version, and review status.
3. Better labor allocation: experts spend time on difficult loci, not repetitive first-pass drafting.

A fourth gain is cumulative research structure: the same pipeline yields structured datasets for sources, works, fragments, entities, aliases, etymologies, and geocoded places, all linkable back to lemma-level evidence.

This supports, rather than displaces, core philological practice.

## 8. Narrative Learning from Human Corrections

At this stage, the project can move from ad hoc prompt tuning to a repeatable feedback loop. The key idea is "Narrative Learning" in your arXiv sense: improvements are learned as explicit textual rules and examples rather than as model-weight updates.

In practical terms:

1. collect human-AI deltas from reviewed entries (especially corrected Greek-dependent mistranslations and systematic English phrasing corrections),
2. cluster recurrent difference types (e.g., ethnicon handling, citation treatment, toponym disambiguation, formulaic lexical patterns),
3. ask an LLM to produce a compact "lesson narrative" describing what repeatedly goes wrong and how to avoid it,
4. convert that narrative into a new prompt version with explicit positive/negative examples,
5. retranslate a held-out sample and compare against prior prompt versions before full rollout.

This keeps model behavior change auditable:

- each adjustment is textual and inspectable,
- each change is versioned and reversible,
- each claim of improvement is tied to concrete reviewed entries.

In other words, the system does not "learn" by hidden parameter change; it learns by accumulating and operationalizing editorial narratives.

## 9. Limits and Risks

The method has clear limits.

- LLM output can remain stylistically smooth while semantically wrong.
- OCR noise can produce plausible but false lexical anchors.
- Editorial choices (Billerbeck vs Meineke) still require human judgment.
- Prompt drift can alter translation tone or detail if not version-controlled.

For these reasons, no unreviewed output should be treated as definitive.

## 10. Conclusion

The project demonstrates a practical methodological point: zero-shot LLM translation can be productively integrated into classical philology when the system is engineered around provenance, idempotent processing, and structured human review.

The central contribution is procedural rather than theoretical. We show that one can move from page images to reviewable translations at scale, while preserving explicit editorial accountability.

If this approach is generalized to other ancient corpora, the key requirement is not a larger model. It is disciplined data architecture plus scholarly review control.

## Provisional Bibliography (to be expanded)

- Billerbeck, M. (ed.). *Stephani Byzantii Ethnica*.  
- Meineke, A. (ed.). *Stephanus Byzantinus*.  
- Recent digital philology and LLM methodology references to be inserted for final submission.
- [Your Name], "Narrative Learning" (arXiv preprint; add full citation details).
