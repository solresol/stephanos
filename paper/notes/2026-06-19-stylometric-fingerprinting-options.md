# Stylometric Fingerprinting Options For Stephanos

Date: 2026-06-19

Purpose: collect methods for fingerprinting possible epitomising layers in Stephanos, using Trevor Evans's Zenon Archive work as the local papyrological model and the current Stephanos recogniser outputs as the first available feature family.

## Local Starting Point

Trevor Evans, "Identifying the Language of the Individual in the Zenon Archive," in *The Language of the Papyri* (Oxford, 2010), 51-70, was checked from `/Users/gregb/Downloads/Identifying_the_Language_of_the_Individ.pdf`.

Evans does not do black-box stylometry. The method is evidence-triangulation:

- Start from a securely bounded sub-corpus: documents attributed to one named person.
- Separate author, writer/scribe, and copyist as much as possible.
- Map linguistic features against palaeographic hands and prosopography.
- Treat a single odd feature cautiously; compare it with ordinary/non-aberrant features.
- Use corpus-relative frequencies: Amyntas' aspirated perfect is meaningful because it is concentrated in his documents relative to the wider Zenon Archive.
- Use handwriting as a control: an authorial feature appearing in both autograph and non-autograph documents may indicate dictation; absence in non-autographs may still reflect scribal normalization.

For Stephanos, the analogue is not handwriting but textual layer and transmission status: Kappa versus non-Kappa, Parisinus/non-epitomised rows, source-citation strata, formula saturation, and entry-type controls. The Evans lesson is that a graph alone is not an argument; any cluster needs a feature-level explanation and a philological control.

## Literature Found

### Directly Relevant To Post-Classical Greek And Papyri

1. Marja Vierros and Erik Henriksson, "Whose Words? Identifying Authors in Greek Papyrus Texts Using Machine Learning," in *Scribes and language use in the Graeco-Roman world* (2024), 49-77. Open copy: https://helda.helsinki.fi/server/api/core/bitstreams/0b80dfc6-46e1-4c20-b5fa-1814ea35033d/content

   - Data: short and fragmentary Hellenistic Greek documentary papyri, including Katochoi, Zenon, and Pathyris material.
   - Methods: clustering/profiling and classification; character n-grams, especially 2-5 and 7-grams; function words; orthographic variation; POS tags.
   - Result to remember: classification reached F1 0.96 with character n-grams 2-5, POS alone reached about 0.80 F1, and Zenon clustering was perfect with character 7-grams in one setup. But clustering can reflect archive or text type rather than author, especially in formulaic notarial material.
   - Stephanos implication: run char n-grams and recogniser vectors, but always control for entry type, source/document slice, and formula density.

2. Trevor Evans, "Identifying the Language of the Individual in the Zenon Archive" (2010).

   - Data: Zenon Archive letters, especially Amyntas.
   - Methods: feature frequencies plus palaeography/prosopography; single-feature case study augmented by particle/formula observations.
   - Stephanos implication: implement "microfeature dossiers" for clusters, not only model scores.

3. Trevor Evans, "Valedictory Ἔρρωσο in Zenon Archive Letters from Hierokles," *ZPE* 153 (2005), 155-158.

   - Not checked in full today, but cited by Evans 2010 and Vierros/Henriksson as a companion case.
   - Stephanos implication: formula endings/openings can be personal or layer-specific fingerprints.

4. Klaas Bentein, "The Greek Documentary Papyri as a Linguistically Heterogeneous Corpus: The Case of the Katochoi of the Sarapeion Archive," *Classical World* 108.4 (2015), 461-484.

   - Not a stylometry paper in the narrow sense, but directly relevant for register and archive heterogeneity.
   - Stephanos implication: treat the corpus as internally heterogeneous before assigning variation to an epitomiser.

5. PapyGreek Treebanks: https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.55

   - This is infrastructure rather than a fingerprinting paper.
   - Useful because it shows documentary Greek can be morphosyntactically annotated and queried; this is the route to sentence-grammar features beyond our current formula recognisers.

### Greek Morphosyntactic Stylometry

6. Vanessa B. Gorman and Robert J. Gorman, "Approaching Questions of Text Reuse in Ancient Greek Using Computational Syntactic Stylometry," *Open Linguistics* 2 (2016), 500-510. DOI: https://doi.org/10.1515/opli-2016-0026

   - Data: ancient Greek dependency treebanks.
   - Methods: "syntax words" built from dependency paths; clustering and relative-frequency comparison.
   - Result: useful for text reuse, including excerpting/epitomising; Polybius excerpted material showed syntactic simplification signals.
   - Stephanos implication: this is probably the closest methodological match to epitomiser fingerprinting. We should test whether epitome-like layers simplify dependency structures, reduce embedded material, or flatten coordination.

7. Robert Gorman, "Author identification of short texts using dependency treebanks without vocabulary," *Digital Scholarship in the Humanities* 35.4 (2020), 812-825. DOI: https://doi.org/10.1093/llc/fqz070

   - Data: Ancient Greek and Latin Dependency Treebank.
   - Methods: morphosyntactic features from dependency labels and morphology of words and parents, deliberately excluding vocabulary.
   - Result: 50-token inputs reached about 84-90 percent accuracy in reported experiments; adding word-order bigram features improved one 50-token setup from 85.9 to 90.9 percent.
   - Stephanos implication: do not depend only on word/token identity. Our entries are often short, so morphosyntactic vectors are attractive if we can populate them reliably.

8. Vanessa B. Gorman and Robert J. Gorman, "A morphosyntactic authorship attribution study of the speeches of Demosthenes and Apollodorus," *Journal of Hellenic Studies* 144 (2024), 65-92. DOI: https://doi.org/10.1017/S0075426924000302

   - Classical rather than post-classical, but important because it shows the interpretability step: clustering, logistic regression, and then feature weights explained as syntactic traits.
   - Stephanos implication: any classifier should output the rules/features driving a split, not just a label.

9. Gianitsos, Bolt, Chaudhuri, and Dexter, "Stylometric Classification of Ancient Greek Literary Texts by Genre," LaTeCH-CLfL 2019. https://aclanthology.org/W19-2507/

   - Methods: more than 20 mostly syntactic custom Greek features, supervised classification.
   - Result: prose/verse classification over 97 percent accuracy/F1.
   - Stephanos implication: build custom Greek feature extractors for entry structure, not just generic n-grams.

### Hellenistic / New Testament / Jewish Greek Stylometry

10. James A. Libby, *Disentangling Authorship and Genre in the Greek New Testament: History, Method and Praxis* (PhD diss., McMaster, 2015). https://macsphere.mcmaster.ca/items/cf8bf95c-be91-4654-993a-a493dec4837b

   - Methods: multivariate stylistics with a strong focus on separating authorship from genre/register/topic.
   - Result to remember: genre can dominate authorship in Greek New Testament stylistic variation.
   - Stephanos implication: letter/book/headword/source-topic controls are not optional.

11. David L. Mealand's Greek New Testament work, especially "Hellenistic Greek and the New Testament: A Stylometric Perspective" (2012), and earlier correspondence-analysis papers on Luke/Acts, Mark, Q, and Hellenistic historians. One accessible landing page: https://journals.sagepub.com/doi/abs/10.1177/0142064x12442846

   - Methods: correspondence analysis, multivariate word/style profiles, genre comparison.
   - Stephanos implication: correspondence analysis is a simple baseline alongside UMAP; it may be easier to explain to classicists.

12. Anthony Kenny, *A Stylometric Study of the New Testament* (Oxford, 1986), and older Pauline stylometry debates (Morton, Mealand, Ledger, Neumann).

   - Older, but still useful as a cautionary history: small corpora plus disputed genre and topic can produce overconfident authorship claims.

13. "Thackeray's Assistant Hypothesis: A Stylometric Evaluation" (Josephus, *Jewish War*), search result found at Liverpool University Press: https://www.liverpooluniversitypress.co.uk/doi/pdf/10.18647/1997/JJS-1997?download=true

   - Not fully checked today. It may be relevant because it deals with Greek prose, assistant/co-author hypotheses, and a text with internal compositional questions.

### Broader Ancient Greek Computational Stylometry

14. Grant Storey, "Like Two Pis in a Pod: Author Similarity Across Time in the Ancient Greek Corpus," *Journal of Cultural Analytics* 5.2 (2020). https://culturalanalytics.org/article/id/688/

   - Methods: high-frequency word distributions and Jensen-Shannon divergence across Ancient Greek authors.
   - Stephanos implication: JSD over most-frequent tokens is an interpretable baseline for similarity graphs.

15. Thomas Koentges, "The Un-Platonic Menexenus: A Stylometric Analysis with More Data," *Greek, Roman, and Byzantine Studies* 60 (2020), 211-241. https://grbs.library.duke.edu/index.php/grbs/article/download/16197/7290/20627

   - Methods: most-frequent word and character n-gram style checks, visualisations such as t-SNE, outlier analysis.
   - Stephanos implication: treat individual entries or groups as outlier candidates, but validate feature reasons.

16. John Pavlopoulos and Maria Konstantinidou, "Computational authorship analysis of the Homeric poems," *International Journal of Digital Humanities* 5.1 (2023), 45-64. DOI: https://doi.org/10.1007/s42803-022-00046-7

   - Not post-classical, but useful for comparing Greek-specific authorship workflows.

## Current Stephanos Data Snapshot

Source: live PostgreSQL via `DB_HOST=raksasa`, checked 2026-06-19.

- Corpus rows: 3,551 epitome rows and 19 Parisinus/non-epitomised rows, all currently usable and with Greek text.
- Active guidance rules: 32 formula, 70 gloss, 75 proper-noun rules.
- Guidance scan evidence under `translation_guidance_scan_v4`:
  - Formula: 37,074 scan rows; 1,090 lemmas checked; 1,039 lemmas with at least one formula hit.
  - Gloss: 34,407 scan rows; 3,570 lemmas checked; 680 lemmas with at least one gloss hit.
  - Proper noun: only 57 scan rows over 1 lemma, so not yet useful for stylometry.
- Sentence grammar tables exist but are embryonic and were still moving during this check: they grew from 1 run / 8 evaluations / 43 tokens early in the run to at least 3 runs / 44 evaluations / 207 tokens in the regenerated status pages.

First UMAP experiment:

- Broad formula-vector slice: entries with at least 21 of 32 formula rules checked. This gives 1,089 entries: 320 Kappa and 13 Parisinus.
- Complete formula-vector slice: entries with all 32 formula rules checked. This gives 370 entries: 320 Kappa and only 1 Parisinus.
- Logistic Kappa/non-Kappa separation on the broad slice gives about 0.753 balanced accuracy, but this is confounded by coverage and scan history.
- The same separation on the complete slice drops to about 0.532 balanced accuracy. That is near baseline and argues against a robust current Kappa fingerprint from formula hits alone.
- KMeans silhouette scores on these formula vectors are low (around 0.08-0.11 depending on threshold), so clusters should be treated as exploratory worklists, not natural classes.

## Feature Families To Implement

1. Current recogniser-vector features
   - Binary hit for each rule revision.
   - `log1p` occurrence count capped at a small value.
   - Separate formula, gloss, contextual-bias, proper-noun, and future grammar recogniser matrices.
   - Always include a coverage mask; never silently treat unscanned rules as clean non-hits.

2. Trevor-style microfeatures
   - Particle complexes: `men...de`, `de`, `gar`, `oun`, `ge`, `te`, `kai`.
   - Clause coordinators and subordination markers.
   - Formula openings and endings: `polis`, `chorion`, `ethnos`, `to ethnikon`, `estin kai alle`, source-citation formulae.
   - Rare orthographic or grammatical alternatives where the edition preserves them.

3. Character and token n-grams
   - Character 2-7 grams on normalized Greek.
   - Most-frequent word/token features with Burrows Delta, cosine, and Jensen-Shannon distance.
   - Word/lemma n-grams once a reliable lemmatized source text is available.

4. Function-word and particle profiles
   - Articles, prepositions, conjunctions, particles, pronouns.
   - Rates per 100 tokens and compositional proportions.
   - Separate normalized and accent-preserving versions.

5. Morphosyntactic vectors
   - POS/morphology frequencies: case, number, gender, tense/aspect, mood, voice.
   - Dependency/syntax-word features if parser output becomes reliable enough.
   - Word-order bigrams and dependency-parent relation features, following Gorman.
   - Sentence and clause length, participle density, genitive absolute candidates, predicate/attribute relation frequencies.

6. Formulaic-language and epitome-compression features
   - Counts of recognized formulae per entry.
   - Formula sequence order within entries.
   - Ratio of formula words to non-formula words.
   - Simplification measures: fewer subordinate structures, fewer source quotations, shorter citation formulae, more `estin kai` secondary entries.

7. Source and topic controls
   - Headword letter, entry number, entry length, place type, cited author/work, geographic region, source text version.
   - Use residualized features or stratified tests before attributing variation to epitomiser layers.

8. Text reuse and source-alignment features
   - Compare direct quotations and source-citation fragments against entry prose.
   - Measure quoted-source preservation versus epitomiser connective prose.
   - Pair Parisinus and epitome rows where available.

## Implementation Plan

1. Keep the new `statistics/fingerprinting.html` page as the status surface.
   - Regenerate nightly from `generate_fingerprinting_page.py`.
   - Show coverage, UMAP, clustering, and caveats.
   - Mirror a concise row on `progress.html`.

2. Export reproducible matrices.
   - `exports/fingerprinting_guidance_features.csv`: one row per lemma and one column per rule hit/count.
   - `exports/fingerprinting_guidance_coverage.csv`: one row per lemma/rule with checked/missing status.
   - Include detector version and source text version IDs.

3. Add baseline stylometry scripts.
   - `compute_fingerprinting_text_features.py` for char n-grams, MFW/JSD/Delta, particles, entry-length features.
   - Normalize Greek with a documented accent policy; preserve a second accent-sensitive matrix for orthographic tests.

4. Compare clustering methods deliberately.
   - Keep KMeans as a simple repeatable baseline.
   - Add agglomerative clustering over cosine/Jensen-Shannon distance, HDBSCAN/DBSCAN for density checks, and graph community detection on a k-nearest-neighbor graph.
   - Evaluate cluster stability under bootstrap resampling and under matched coverage/letter/source strata before interpreting any cluster.

5. Add grammar features only after validation.
   - Populate sentence grammar tables over a balanced sample.
   - Run parser accuracy checks before treating grammar features as evidence.
   - Separate parser confidence from the feature value.

6. Design controls before making claims.
   - Compare Kappa versus non-Kappa only within matched coverage bands.
   - Do permutation tests by shuffling labels within headword-letter/source strata.
   - Compare formula vectors against length, place-type, and source-author baselines.
   - Treat Parisinus rows as qualitative controls until the non-epitomised sample is larger.

7. Interpret clusters philologically.
   - For each stable cluster, generate a short dossier: top discriminating features, 10 representative entries, 10 nearest counterexamples, and source/letter/length distribution.
   - Ask Gabe/Trevor-facing questions from those dossiers, not from UMAP shape alone.

8. Publish the evidence incrementally.
   - Public page: status, plots, and caveats.
   - Paper notes: method decisions and literature.
   - Later: downloadable feature matrices for peer review.

## Immediate Conclusions

- The current recogniser vectors are useful enough for exploration, especially formula and gloss hits.
- They are not yet a secure epitomiser fingerprint. The Kappa signal weakens sharply once complete formula coverage is required.
- The non-epitomised control set is currently too small for statistics; use it for close-reading checks.
- The best next technical step is a coverage-balanced feature matrix plus simple baselines: character n-grams, function words/particles, and recogniser-hit vectors.
- The best next scholarly step is to define what an "epitomiser fingerprint" would mean: simplification, formula preference, source-handling, grammar distribution, or a combination.
