# Paper Roadmap From 2026-06-18 Transcript

Source transcript: `/Users/gregb/Downloads/07_02 PM - zoom.us meeting June 18_transcript.txt`

This document separates the immediate article plan from the larger set of possible papers discussed in the meeting. It is based on a noisy transcript and should be treated as a planning document, not as checked prose.

## Paper 1: Immediate Technical/Digital-Humanities Article

Working title options:

- From Off-the-Shelf LLM to Reviewable Translation: Prompt Rules, Editorial Style, and Human Work in Stephanus of Byzantium
- Measuring a Human-AI Translation Workflow for an Epitomized Greek Reference Text
- When "Good Enough" Is Not the Goal: LLM Translation, Editorial Style, and Scholarly Review in Stephanus

Likely venue:

- Digital humanities / digital scholarship venue, probably around 5000 words if targeting the short DSH-style article discussed in the meeting.

Core claim:

Off-the-shelf LLM translation of an untranslated, epitomized Greek reference text is useful but untrustworthy. Prompt iteration and formula/rule guidance do not simply "improve translation quality" in one flat sense. They improve different dimensions: content reliability, editorial consistency, preservation of Stephanus' compact style, and the amount of human review needed to reach a scholarly translation.

What makes this worth publishing:

- The project confirms prior findings that LLMs can produce plausible but unreliable classical-language translations, especially when vocabulary, genre, or syntax falls outside strong training patterns.
- The project adds a workflow question: how do you push an LLM toward a specific scholarly translation goal rather than a smooth general-purpose English paraphrase?
- Stephanus is a useful stress test because the Greek is often syntactically compact and formulaic, but the text is not just "easy Greek." It contains unusual vocabulary, epitomized phrasing, book/place ambiguity, accentual and metalinguistic discussion, and dense factual information.
- The V2-to-V3 change may be more important as a human-workload and editorial-style change than as a semantic-quality change.

## Evidence Base

Use the 100 visible Kappa review rows from Gabe's final review tracker export as
the frozen reference set. Do not substitute the broader current
`human_translations` approved count when writing or regenerating paper results:
that table can include approved rows outside the Kappa tracker. The Kappa paper
corpus is anchored by `data/kappa_review/final-kappa-translation-review.rows.jsonl`
and the PostgreSQL `kappa_review_imports` / `kappa_review_rows` tables; code maps
those rows to live translations through `kappa_review_rows.source_row_id =
assembled_lemmas.entry_number` for Kappa epitome entries.

For each entry or sentence, gather:

- Greek source text.
- Human-approved English translation.
- Prompt-version outputs.
- Prompt version and model/version metadata.
- Rule hits or formula recognizer hits.
- Semantic metrics.
- N-gram or overlap metrics, especially trigram/quadgram overlap.
- Exact/no-change/near-change status.
- Human notes on whether the AI preserved meaning, style, and editorial conventions.

## Key Facts Already Established (verify before publishing)

These came out of the meeting itself and are evidence, not open questions. Transcript line numbers are given; the ASR is noisy, so re-derive each from project data.

- Mood/verb profile of the 100 entries: one optative, no subjunctives, no imperatives; effectively all indicative (807-809). This is the headline support for "Stephanus looks like the easy case but is not": you would predict Thucydidean syntax to be hard and a reference work to be trivial, yet Stephanus needs a specific workflow. Supporting register facts: no declined duals, pluperfect used as a bare emphatic, optative deployed as a learned "flex" (859-871).
- Surface-fidelity baseline: ~17% quadgram overlap with the human-approved set (about one chance in six that a four-word run matches) (369).
- Rule-firing anomaly: `ethnikon + X` and `settlement + region` fire less than a Zipf-like curve predicts (1132-1152). Since ethnikon "should be in virtually every passage," this is either an epitomization fingerprint or an incomplete recognizer — decide which before using it.
- Self-scoring is asymmetric: automated scoring nailed the worst semantic failure (enkomos) but missed grammatical/accentual failures judged "dreadful" by hand (670-672). Bears directly on whether we can trust the model to flag its own worst output.

Named worked examples already chosen on screen (use as the Results-section case studies):

- Kope (fishermen-and-wolves digression): strong long V3 entry, candidate five-star (1247-1255).
- enkomos / Hesiod quotation: worst entry; silently truncated the quotation mid-passage (628-668).
- Kytinion / "Kuto's" (barytonos/baritone): obeys the accent rule but states something contrary to reality (695-743).
- Colossae: formula failure ("Black Sea" rule should have fired and did not) (600-605).
- Herodotus: Latinized form despite explicit instruction; "in Asia" read as a province where it was a book title (585-608).
- Three exact matches plus one one-letter-off, confirmed live (582-584).

## Minimal Analyses For Submission

1. Prompt-version comparison:
   - V1 to V2: expected large gain in comprehensibility and basic translation quality.
   - V2 to V3: expected smaller semantic gain but stronger editorial/style/workload gain.
   - Report whether the statistical separation is strong, weak, or absent for each metric family.

2. Exact and near-exact output analysis:
   - Count entries and sentences requiring no change.
   - Count entries requiring only punctuation or minor style changes.
   - Use examples carefully; exact matches are surprising enough to be informative, but should not be oversold.

3. Error typology:
   - Book title, place, province, and source-title category confusion.
   - Latinized names where Greek forms were requested.
   - Topicalized forms and accentual examples treated as normal word forms.
   - Misread gender/case/number despite articles providing cues.
   - Epitomized syntax expanded into smooth but less faithful English.
   - Metalinguistic or accentual terminology translated inconsistently.

4. Rule and formula analysis:
   - Show how formula/rule guidance constrains the model.
   - Measure rule-hit distribution and whether rule discovery appears to be saturating.
   - Test whether formula-bearing sentences are more likely to be translated correctly overall.

5. Sentence-level worst/best analysis:
   - Pull the worst-scoring sentences for human inspection.
   - Pull the no-change sentences.
   - Ask whether the predictors are length, rare vocabulary, formulaic structure, grammatical ambiguity, or model category mistakes.

6. Workload framing:
   - Treat the human reviewers' work as part of the pipeline, not as cleanup after a magic translation.
   - Emphasize that preserving Stephanus' literary artifact sometimes means resisting the model's instinct to produce smooth natural English.

## Proposed Article Structure

1. Introduction:
   - Problem: untranslated or undertranslated classical reference texts.
   - Why "gist translation" is insufficient for scholarly use.
   - Why Stephanus is a useful case.

2. Text and workflow:
   - OCR/source extraction.
   - Prompt versions.
   - Human review.
   - Formula/rule guidance.

3. Evaluation design:
   - Frozen 100-row Kappa sample from Gabe's final review tracker export.
   - Human-approved reference translations.
   - Metrics and why multiple metric families are needed.
   - Limitations of semantic metrics for editorial style.

4. Results:
   - Prompt-version metrics.
   - Exact/no-change rates.
   - Rule/formula effects.
   - Error typology.

5. Discussion:
   - Why Stephanus is not the easy case one might expect.
   - How rule guidance changes the human workload.
   - What "quality" means when the target is a scholarly translation rather than a fluent paraphrase.

6. Conclusion:
   - Off-the-shelf LLMs are useful but not autonomous translators for this material.
   - A constrained human-AI workflow can produce reviewable translation at scale.
   - Further work: external human grading, fact fidelity, broader Stephanus coverage, and post-classical Greek corpus studies.

## Things To Keep Out Of Paper 1 Unless Needed

- Pausanias stylometry results.
- Full translation-publication strategy.
- Long speculative discussion of Ghent/Trevor collaborations.
- All candidate philological notes, except one or two examples if they clarify why human review matters.
- A large human-grading study, unless it can be run quickly and cleanly.

## Paper 2: Classics-Facing / Autoethnographic Account

Possible framing:

What it was like for classicists and technical collaborators to spend months working with ChatGPT/GPT-style translation on Stephanus: where it helped, where it failed, and how human expertise changed the outputs.

Likely claim:

The interesting result is not that the model replaced philological work, but that it changed where the work happened: prompt design, style-rule negotiation, error detection, and systematic capture of recurring linguistic problems.

Needed evidence:

- Short reflective memos from Greg, Greta, Gabe, and possibly Brady.
- A typology of repeated human interventions.
- Examples of translation decisions that were not simply "correct vs incorrect" but about what kind of Stephanus the English should represent.

Status:

Good second paper. Do not let it distract from the July technical article.

## Paper 3: Translation Metrics Versus Classicist Judgments

Research question:

Do modern machine-translation metrics agree with how classicists judge translations from ancient Greek?

Proposed method:

- Select a small set of passages and prompt-version translations.
- Ask active Greek teachers to grade them as unseen translations or rank pairs.
- Compare human judgments with BLEU-like, embedding/semantic, and n-gram overlap metrics.
- Separate content accuracy, style, syntax, and editorial conformity.

Why it matters:

Modern metrics are mostly tuned for modern-language translation and may miss things that matter in classical-language pedagogy and scholarship.

Prior work to anchor against:

The Galen/Zainaldin paper is the model and the comparison point. It used a roughly three-level human quality scheme (fail / low pass / high pass) and noted that the statistical analysis surfaced things the human evaluation did not (transcript lines 1211-1259, 1258-1259). Our own evidence that automated scoring catches semantic disasters but misses grammatical ones (see Key Facts) is directly relevant: it suggests human grading and metrics disagree in patterned, not random, ways.

Status:

Strong standalone paper, but it needs a clean external-evaluator protocol.

## Paper 4: Fact Fidelity In Stephanus

Research question:

Since Stephanus is read for facts, pseudo-facts, spellings, and source claims rather than pleasure, how well does an AI-assisted translation preserve the facts?

Possible experiment:

- Extract factual claims from the Greek and/or human translation.
- Compare them mechanically against a reference such as Pauly-Wissowa where possible.
- Measure where AI outputs preserve, distort, omit, or invent facts.

Status:

Promising, but probably not for the immediate July paper unless there is already tooling close to this.

## Data Paper / Dataset Output

Possible output:

A reusable dataset of Stephanus passages with parsed grammar, rule hits, translation versions, human-approved translations, metrics, and summary statistics.

Value:

This fits computing/data-publication norms better than traditional classics norms. It could support later work by others without requiring everyone to rerun expensive parsing and translation workflows.

Required before release:

- Stable export format.
- Accuracy audit or explicit confidence fields.
- Clear license and citation instructions.
- Zenodo or similar deposit if desired.

## Corpus-Linguistic / Post-Classical Greek Studies

Ideas that may interest post-classical Greek specialists:

- Distribution of Gabriel's exact "near" construction note, `πλησίον + GEN. vs προς + DAT. = 'near'`, with working transliteration `plesion + genitive` versus `pros + dative`; test whether the choice correlates with geography, source, or epitomizer.
- `ethnikon`, `polites`, `oiketer`, and related inhabitant terms by place type.
- Etymology categories, especially if animal-related stories correlate with local/barbaric ethnonym discussion.
- Stephanus' use of epicoric versus barbaric descriptions.
- Pendant nominatives in Stephanus, with samples for specialists who have studied the construction.
- Stylometric or grammar-feature signals that might distinguish source material, content type, or epitomizing layers.

Bibliographic lead from Gabriel's chat for the stylometry/idiolect angle:

- "'Identifying the Language of the Individual in the Zenon Archive', in T. V. Evans and D. D. Obbink (eds.), The Language of the Papyri (Oxford: Oxford University Press, 2010), 51-70."

Status:

High-value but needs either more Stephanus coverage or a collaborator already fluent in the relevant scholarship.

## Short Philological Notes

Candidate notes:

- Brady's emendation in the first Kappa entries.
- The genealogy/father-son corruption.
- Lexical or hapax items missing from major lexica.
- Possible accentuation or form-analysis issue around `prolambano`.
- Specific Stephanus geography vocabulary where standard English hides an ancient conceptual distinction.

Important constraint:

Notes are legitimate publications, but they need careful bibliography, textual comparison, and narrow claims.
