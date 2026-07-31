# The *Ethnika*: unasked research questions and an agenda for digital philology

**Research memo, 1 August 2026**

## Purpose and relation to the existing research

This memo follows [the survey of epitomisation theories and twenty-five leading debates](2026-07-31-ethnika-epitomisation-and-research-state.md) and [the existing stylometric options paper](2026-06-19-stylometric-fingerprinting-options.md). It asks two different questions:

1. Which questions about the *Ethnika* have not been asked, have been asked only incidentally, or have not been made testable?
2. Which digital-humanities and NLP methods could now address them, and which of those methods have not yet been applied in this project?

“Not asked” is necessarily relative. A question may have occurred in an editor's note, a study of one source, or a discussion of another Byzantine epitome without yet becoming a corpus-wide programme for Stephanos. The aim is not to claim novelty by silence. It is to identify work that the present relational corpus can make explicit, reproducible, and falsifiable.

This memo maintains the project's evidence boundary. Billerbeck's discussion, OCR, and translations are not entry-level dossier evidence. They may inform project-level historiography, but they must not leak into a specialist finding about an individual entry. No computational method licenses reconstruction of lost Greek wording.

## Executive answer

The most important unasked question is not **who epitomised the work?** but **what was the deletion rule?** Current theories name possible agents and stages, yet rarely express competing models as predictions about what an abbreviator preserves, deletes, moves, rewrites, or leaves syntactically stranded. The surviving fuller-versus-shorter pairs make a limited but unusually valuable calibration corpus for that question.

Five connected research programmes would materially change the field:

1. **A grammar of survival:** model epitomisation as selective, non-random deletion of entry components, not as undifferentiated shortening.
2. **A transmission graph:** identify passage-level relations among the direct epitome, fuller fragments, Constantine VII, Eustathios, the etymological lexica, and possible source texts without presuming a simple tree.
3. **A map of voices:** distinguish the words and scope of the cited source, Stephanos' compilation, an abbreviator's join, a gloss, a scribe, and a modern editor.
4. **A temporal geography of assertions:** represent what a source says about a place at a time, rather than collapsing every name to one modern coordinate and one timeless identity.
5. **Calibrated scholarly inference:** measure specialist and model error on cases where fuller evidence survives, require explicit alternatives, and make abstention a positive result.

The strongest immediate experiment is a manually reviewed alignment of every fuller/shorter pair, with each edit labelled by content function and operation. It would answer questions that neither whole-entry length nor unsupervised UMAP can answer.

## I. What the new study of epitomes changes

The recent comparative study of Greek and Byzantine epitomising argues for treating an epitome as a written artefact with agency, technique, audience, function, and institutional setting—not solely as an inferior indirect witness. Mallan's working definition allows condensation by rewording, excision, excerption, or a mixture of these operations. The collected case studies locate epitomes in courts, classrooms, law schools, hospitals, monasteries, and professional practice; show that multiple divergent abridgements can coexist with their sources; and demonstrate that an epitomator can select, transpose, editorialise, supplement, or reorganise rather than merely cut. Philip Rance's review also stresses two unresolved comparative problems: why epitomes cluster in some subjects and periods but not others, and how material book costs and format affected their production. Geography is explicitly identified as an underexplored case in which abridgement can turn a coordinate system into verbal summary. See [Rance's review of Mallan 2025](https://www.plekos.uni-muenchen.de/2026/r-mallan.pdf) and the [publisher record](https://www.degruyterbrill.com/document/isbn/9789004734487/html).

This wider research makes several assumptions unsafe:

- “shorter” is not a sufficient operational definition of “epitomised”;
- fidelity is not the only or always the best measure of an epitome;
- one surviving short text need not descend through one uniform operation;
- an epitome can reveal the priorities of a new intellectual setting, but only when selection is compared against a defensible source state;
- practical access, teaching, reference, patronage, salvage, copying economy, and editorial argument are competing or overlapping functions, not interchangeable explanations.

The *Ethnika* is an especially difficult case because the source state usually does not survive. The project must therefore separate observable edit operations from inferred agency and motive.

## II. Research questions that are not yet being asked sharply enough

### A. Epitomisation as an observable process

#### 1. What is the survival probability of each entry component?

Do headword classification, geographic location, ethnic form, derivational rule, cited authority, direct quotation, mythology, history, famous citizens, mirabilia, and cross-reference have measurably different chances of survival? This should be estimated from aligned fuller/shorter pairs, with uncertainty, rather than inferred from the thin text alone.

#### 2. What is the unit of deletion?

Does abbreviation normally remove a whole source block, a sentence, a clause, a quotation while retaining its attribution, an attribution while retaining its claim, or selected tokens inside a formula? Different units imply different editorial techniques and produce different textual symptoms.

#### 3. Does the abbreviation preserve beginnings and endings preferentially?

The surviving text may reflect positional selection: keep the identifying opening and grammatical payoff, delete the middle dossier. That prediction can be tested in fuller pairs and source parallels. It is more precise than saying that “cultural information was removed.”

#### 4. Which deletions create stranded grammar?

Can abrupt particles, unsupported pronouns, orphaned source names, unexplained alternatives, or sudden construction changes be mapped to known deletion sites in fuller pairs? This would produce an empirical redaction-symptom vocabulary and a false-positive rate for the `$stephanos-specialist`.

#### 5. Does an epitomator rewrite joins after deleting material?

Some abridgements may be clean excisions; others may add a connective, change case, replace a noun with a pronoun, or recast a quotation as indirect speech. Those small repairs could be more diagnostic of an editorial hand than entry length.

#### 6. Are there multiple deletion regimes?

After controlling for letter, source, topic, entry type, length, physical lacunae, and witness coverage, do the operation profiles require one regime or several? A multi-stage theory should predict distinct, recurring edit distributions or sequential change points; otherwise “several epitomators” remains an explanation that can absorb any unevenness.

#### 7. Where, if anywhere, do deletion regimes change in sequence?

Entries occur in an inherited alphabetic order. That order should be analysed as a sequence, not only as a cloud of independent vectors. Contiguous shifts are more compatible with exemplar or production changes than scattered topical clusters.

#### 8. Can Bouiron's H1/H2/H3 model be falsified?

For each proposed stage, specify expected retained proportions by component, expected witness relations, predicted chronological terminus, and passages that should or should not agree. A model without discriminatory predictions is a narrative reconstruction, not yet a testable stemma.

#### 9. How much negative evidence is a missing item worth?

If the calibration pairs show that named sources survive 70 per cent of the time but mythological explanations only 10 per cent, absence has different evidential weight in the two categories. The aim is not to reconstruct lost content but to say when “not preserved” carries information and when it does not.

#### 10. What did an abbreviator misunderstand?

Errors can reveal procedure: a source name retained with the wrong scope, a grammatical example detached from its rule, a pronoun without antecedent, or an ethnic form separated from its place. An error typology may reveal training and priorities more reliably than speculative biography.

### B. Composition and source architecture

#### 11. What was Stephanos' actual unit of compilation?

Was the work assembled entry by entry, author dossier by author dossier, geographical region by region before alphabetisation, or grammatical rule by grammatical rule? Runs of citation order, shared wording, and correlated errors may distinguish these workflows.

#### 12. Can source relays be inferred rather than merely listed?

A named ancient author may have reached Stephanos directly, through a geographic epitome, a grammatical lexicon, scholia, an author-specific collection, or a chain of these. The research object should be a passage-level relay graph with uncertainty, not a flat list of “sources used.”

#### 13. Where does a cited authority's scope begin and end?

Does “as X says” support the place name, the historical statement, the whole following sentence, a quotation only, or an ethnic form supplied by Stephanos? Scope errors are a major source of false fragment attribution and translation overconfidence.

#### 14. Which uncited prose is inherited?

Recurring unattributed wording may be a source fingerprint, a Stephanean connective layer, or formulaic lexicographic language. Passage retrieval plus manual adjudication can find source blocks that citation counting misses.

#### 15. Did Stephanos copy, paraphrase, harmonise, or argue with sources?

Where source texts survive, align them locally and classify the integration operation. The result would distinguish a collector of excerpts from a grammarian who actively normalised, combined, and evaluated evidence.

#### 16. Can the lost theoretical opening be approached through distributed rules?

The question should not be “what did the lost *protechnologemata* say?” but whether surviving rule statements form a coherent dependency network: definitions, exceptions, analogies, preferred suffixes, dialect constraints, and cross-references. Coherence may support a lost systematic treatment without licensing verbal reconstruction.

#### 17. What does the internal cross-reference graph reveal about vanished architecture?

Cross-references that point to absent arguments are fossils of a fuller work. Their direction, target type, and failure pattern may show which material was systematically removed and whether cross-reference creation preceded alphabetic assembly.

#### 18. Which “fragments” are independent evidence?

Modern fragment collections can become circular if an Ethnika passage is used to reconstruct a lost source and that reconstructed source is then used to emend or explain Stephanos. A source graph should flag dependencies and distinguish independent parallels from descendants of the same lexicographic tradition.

### C. Recensions, readers, and uses

#### 19. What text did each Byzantine reader actually have?

Constantine VII, the *Suda*, Eustathios, Tzetzes, and the etymological lexica should each receive a recension profile based on shared additions, omissions, word order, source scope, and errors. “Used Stephanos” is too coarse.

#### 20. Are richer indirect witnesses one recension or several?

Extra material in Eustathios need not come from the same state as Constantinian excerpts or fuller lexicographic parallels. Contamination-aware networks are preferable to forcing all witnesses into a single branching tree.

#### 21. Did readers supplement an epitome from elsewhere?

A richer passage may preserve an older Stephanean state, but it may also combine the epitome with another source. Testing for vocabulary and sequence imported from known lexica or commentaries is essential before calling every addition “full Stephanos.”

#### 22. What practical task did each surviving form serve?

Was it a grammatical reference work, a quarry of quotations, a geographic index, a school text, a courtly encyclopaedia, a writing aid, or a compact substitute for an unavailable original? The answer may vary by recension and period. Evidence must come from selection patterns, format, annotations, ownership, and reuse—not presumed from brevity.

#### 23. How did material book constraints shape the text?

Could page, quire, hand, or planned-volume constraints explain some compression boundaries? The economics of copying and the move from a multi-book original to a portable codex should be studied alongside intellectual motives.

#### 24. How does the *Ethnika* compare with other epitomes of technical or reference literature?

Comparison with Athenaeus, legal and medical epitomes, grammatical manuals, and geographic abridgements can test whether source stripping, decontextualised quotation, rule retention, or catalogue form are genre-specific or broadly Byzantine. The 2025 comparative turn makes this a tractable programme.

#### 25. What became of the work outside direct Greek transmission?

Have Arabic, Syriac, Armenian, or Latin geographical and lexicographical traditions preserved translated, adapted, or second-hand Stephanean matter? Search must allow semantic and cross-lingual resemblance, not only Greek string identity.

### D. Knowledge, geography, and identity

#### 26. What kinds of entities does the *Ethnika* believe can generate belonging?

City, people, region, island, mountain, river, shrine, political unit, and mythical place are not one ontology. Which can produce an ethnic, local, possessive, or gendered derivative, and where does Stephanos explicitly resist the ordinary rule?

#### 27. Whose time does a geographic assertion describe?

Every classification and orientation should be capable of carrying at least a source date, referent date, Stephanos date, and witness date. “X is a city” may describe an archaic poem, a Hellenistic polity, a Roman province, or Justinianic knowledge.

#### 28. What is the geography of Stephanos' knowledge rather than of the ancient world?

Map source density, confidence, quotation length, number of names, and type of information—not merely places. Regional abundance may reflect source survival, imperial interests, grammatical difficulty, or epitomatorial selection.

#### 29. How are renaming and polyonymy used to organise historical change?

Metonomasia, endonym/exonym, Homeric name, colonial renaming, imperial refoundation, and simple homonymy should be separated. Their temporal and political patterns may reveal how the work reconciles inherited literary geography with Roman-period realities.

#### 30. How does grammatical norm interact with local self-description?

When does Stephanos report an attested local form, prescribe an analogical form, cite a literary form, or reject common usage? This is a history of linguistic authority as well as morphology.

#### 31. What information was least likely to survive, and whose worlds disappear with it?

If abbreviation preferentially removed local cult, women, minor peoples, non-Greek names, everyday practice, or unattributed oral/local knowledge, the epitome's map is not merely thinner but systematically biased. This can be tested only in categories for which fuller comparanda exist.

#### 32. Do Christianising or contemporary notices form one intervention profile?

Rather than deciding from content alone that a phrase is “late,” compare syntax, formulae, manuscript distribution, placement, and relation to surrounding entry components. Several different Christian or Byzantine interventions may otherwise be collapsed into one layer.

### E. The history and epistemology of scholarship

#### 33. How much of the modern text is a Renaissance or editorial construction?

Humanist correction, contamination among manuscripts, Aldine normalisation, and modern conjecture should be represented as distinct operations. A plausible Greek sentence may belong to an editor rather than any medieval witness.

#### 34. Which modern research claims depend on the epitome as if it were the original?

A claim audit across fragment editions, historical geography, and lexicography could identify where “Stephanos says” silently means “the late direct epitome transmits.” This is a correctable provenance problem.

#### 35. What can the surviving evidence never discriminate?

The field needs explicit identifiability limits. Entry-level evidence will often detect a deletion symptom but cannot name Hermolaos, date a reduction, or distinguish two historically remote processes with the same textual output. Recording non-identifiability prevents confidence from increasing merely through repeated citation.

#### 36. How reliable are the project's own specialist judgements?

Use blinded duplicates, fuller-pair holdouts, inter-rater agreement, adjudication logs, and false-positive analysis. A relational workflow is itself a scholarly instrument and should be calibrated like one.

## III. Digital-humanities and NLP methods not yet applied to the *Ethnika* project

The distinction in the final column is important:

- **Implemented** means present in current project code.
- **Proposed locally** means described in the June stylometry paper but not implemented in the current generator.
- **Not yet applied** means no project implementation was found in the current repository.

| Method | Stephanos research use | First defensible experiment | Project status |
|---|---|---|---|
| Function-word, particle, character n-gram, Burrows' Delta, cosine, Jensen–Shannon, and correspondence-analysis baselines | Establish interpretable style baselines less dependent on recognised formulas | Re-run Kappa/non-Kappa and fuller/epitome comparisons with coverage-balanced, topic-matched samples | Proposed locally; not in the current formula-vector generator |
| Dependency-based syntactic stylometry | Compare very short Greek texts without relying on headwords and topical vocabulary | Parse only adequately formed clauses; use dependency relation and “syntax word” features with manual error audit | Proposed locally; not implemented |
| Open-set authorship verification / General Impostors | Ask whether a passage is compatible with a reference profile without forcing it into one of several clusters | Treat fuller Stephanean prose, quoted-source prose, and likely joins as verification tests with genre-compatible impostors | Not yet applied |
| Graph-based multi-witness collation | Represent variants and transpositions without selecting one base text as truth | Collate a small manuscript family and one indirect witness in CollateX; inspect TEI and variant-graph output manually | Not yet applied |
| Contamination-aware phylogenetic networks and Bayesian stemmatics | Model mixture, block switching, and uncertainty in witness ancestry | Begin only after a reviewed variant matrix exists; compare tree and reticulate models on held-out readings | Not yet applied |
| Edit-operation induction | Learn whether shorter texts keep, delete, replace, move, or join source spans | Align every fuller/shorter pair; label operations and content functions; publish the gold table before training | Not yet applied |
| Selective-deletion / survival modelling | Estimate what information survives epitomisation and quantify category-specific negative evidence | Hierarchical logistic or discrete-time survival model with entry and witness effects; report posterior intervals | Not yet applied |
| Sequential change-point or hidden-state modelling | Test whether deletion/style regimes occur in contiguous alphabetic stretches | Fit one- versus multi-state models with letter, source, topic, and lacuna covariates; use posterior predictive checks | Not yet applied |
| Passage-level fuzzy text-reuse detection | Find direct copying and near-verbatim relay passages across large Greek corpora | Evaluate Passim/TRACER-style retrieval on known citations and deliberately withheld parallels before discovery use | Not yet applied |
| Ancient Greek sentence embeddings and semantic retrieval | Find paraphrased or cross-lingual source parallels that lexical matching misses | Use SPhilBERTa-style embeddings to retrieve candidates from licensed Greek/Latin/English corpora; require philological verification | Not yet applied |
| Domain-adapted Ancient/Byzantine Greek transformers | Identify people, places, groups, formula boundaries, voice, and entry components | Fine-tune a token/span classifier on 200–500 manually marked entries; retain an out-of-domain test set | Not yet applied |
| Weak supervision / data programming | Combine recognisers, gazetteers, formulae, source lists, and expert rules without pretending they are gold labels | Define abstaining labelling functions and test their correlations against a small gold set | Not yet applied |
| Active learning | Spend expert time on examples that most improve a component or voice classifier | Review disagreement/uncertainty cases in batches, with random controls to detect selection bias | Not yet applied |
| Conformal prediction or calibrated prediction sets | Let an NLP system return several admissible labels or abstain with an empirical coverage target | Calibrate on held-out manual annotations; expose prediction sets, not uncalibrated confidence scores | Not yet applied |
| Claim-level provenance knowledge graph | Track each assertion, witness span, source chain, model/skill version, verdict, and revision | Export the relational ledger to a PROV-O-compatible graph while keeping PostgreSQL authoritative | Partly present relationally; interoperable claim graph not applied |
| Temporal and uncertain gazetteering | Represent alternative places, time-bounded names, regions, fuzzy extents, and sourced attestations | Add source/date-qualified place assertions and polygons/regions; reconcile through Pleiades and WHG without overwriting alternatives | Basic place linking exists; temporal/fuzzy model not applied |
| HTR plus Byzantine-Greek error detection | Re-collate manuscripts from images and find errors inherited from editions or OCR | Pilot a few pages from one digitised epitome manuscript; preserve image coordinates and compare HTR with diplomatic transcription | Not yet applied to manuscript witnesses |
| Formula/construction discovery beyond hand recognisers | Discover recurring lexical-syntactic templates and their variants without using existing rule names as labels | Mine skip-grams and dependency subgraphs, then have experts name or reject clusters | Current rule recognisers and UMAP exist; unsupervised construction discovery not applied |
| Source and cross-reference graph anomaly detection | Find missing targets, suspicious attributions, relay hubs, and blocks likely assembled together | Build a typed graph; use simple motifs and link prediction only to rank dossiers, never to create findings | Some source/reference pages exist; inference layer not applied |
| Matched and hierarchical causal-style comparisons | Separate suspected layer effects from letter, source, topic, entry type, and length | Pre-register matched comparisons and multilevel models; report sensitivity to unobserved confounding | Not yet applied |

### Why these methods are now practical

Several technical developments remove obstacles that existed even five years ago:

- [Ancient Greek BERT](https://aclanthology.org/2021.latechclfl-1.15/) showed useful morphological analysis across Ancient and Byzantine Greek.
- [Ancient Greek NER studies](https://aclanthology.org/2024.ml4al-1.16/) now combine transformer models, gazetteers, domain knowledge, and out-of-domain testing, while also showing that random real-world samples remain difficult. A second [2024 NER study](https://aclanthology.org/2024.lt4hala-1.11/) emphasises the continuing scarcity of coherent high-quality annotation.
- A [2024 comparison of Ancient Greek parsers and lemmatisers](https://arxiv.org/abs/2410.12055) evaluates GreBERTa, PhilBERTa, GreTA, and PhilTa, while the [Universal Dependencies Greek inventory](https://universaldependencies.org/grc/) exposes several reusable treebanks. These are enabling resources, not proof that an out-of-domain Stephanos parse is correct.
- [SPhilBERTa](https://aclanthology.org/2023.alp-1.2/) supplies cross-lingual sentence embeddings for Ancient Greek, Latin, and English; a [2026 parallel-sentence benchmark](https://aclanthology.org/volumes/2026.nlp4dh-1/) reports substantial improvement from whitening, knowledge distillation, and fine-tuning. This makes cross-lingual candidate retrieval realistic, although synthetic benchmark performance cannot be transferred directly to fragmentary lexicographic prose.
- [Weakly supervised NER for historical texts](https://aclanthology.org/2026.latechclfl-1.6/) reports retaining more than 80 per cent of fully supervised F1 with 10 per cent of the annotations in its test setting. The result supports a pilot, not an expected Stephanos score. [Snorkel's data-programming model](https://www.vldb.org/pvldb/vol11/p269-ratner.pdf) provides the general machinery for learning from correlated, abstaining rules.
- [Conformal prediction for API-only language models](https://aclanthology.org/2024.findings-emnlp.54/) provides a route to coverage-controlled prediction sets without logits. This is relevant to a scholarly workflow in which “uncertain between two layers” is preferable to a forced label.
- [CollateX](https://collatex.net/doc/) can output TEI apparatus and variant graphs from configurable tokenisation; this is suitable for a manuscript pilot once diplomatic transcriptions exist.
- Recent [Bayesian phylogenetic stemmatics](https://academic.oup.com/dsh/article/39/1/258/7477852) explicitly discusses contamination and reticulate alternatives. The older warning remains essential: a textual tradition and a manuscript tradition are not identical, and computer-generated stemmata must be interpreted as models rather than recovered history ([Bordalejo 2016](https://academic.oup.com/dsh/article/31/3/563/2340401)).
- [Passim at scale](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2023.1249469/full) demonstrates fuzzy reuse detection under moderate OCR noise, while [Tesserae](https://edizionicafoscari.unive.it/en/edizioni/libri/978-88-6969-183-6/the-tesserae-project/) supports Greek and Latin lexical, semantic, and sound-based intertext search. A Stephanos application would need its own benchmark because short formulaic entries create many false parallels.
- [Seq2Edits](https://aclanthology.org/2020.emnlp-main.418/) shows how high-overlap text transformations can be represented as human-readable span edits, and [work on sentence deletion in simplification](https://ojs.aaai.org/index.php/AAAI/article/view/6520) shows that deletion is predictable from discourse factors. These are analogies for designing a transparent epitomisation model, not historical models of Byzantine practice.
- [Ancient Greek syntactic authorship work](https://academic.oup.com/dsh/article/35/4/812/5606771) demonstrates vocabulary-independent dependency features for short passages. [A study of copied historical fragments](https://aclanthology.org/2022.lrec-1.631/) also warns that author-independent styles and paraphrase can mask individual style—precisely the risk in formulaic lexicography.
- [World Historical Gazetteer](https://www.whgazetteer.org/) models sourced attestations and temporal place data rather than timeless “facts”; its API supports fuzzy containment and temporal filters. This is a better conceptual fit than reducing uncertain ancient regions to point coordinates. [Pelagios](https://pelagios.org/linked-open-data) supplies the linked-open-data ecosystem for shared place identifiers.
- [eScriptorium](https://escriptorium.eu/about/) and Kraken support complex manuscript layouts and Greek HTR. A [Byzantine Greek error-detection study](https://aclanthology.org/2023.findings-emnlp.524/) shows that an Ancient- and Modern-Greek-pretrained classifier can reduce harmful post-correction, but it also demonstrates why automatic correction must not overwrite diplomatic evidence.
- [CTS URNs](https://cite-architecture.github.io/ctsurn_spec/) can identify passages across work/version hierarchies; [TEI stand-off annotation](https://guidelines.tei-c.de/en/html/index.html) can keep overlapping scholarly analyses separate from the text; and [W3C PROV-O](https://www.w3.org/TR/prov-o/) can exchange provenance for claims and processes. The present relational ledger already has much of the needed substance but not an interoperable expression.

## IV. What should be built first

### Pilot 1: the epitomisation gold set

**Research question:** What does abbreviation actually do?

1. Enumerate every admissible fuller/shorter pair and indirect parallel.
2. Preserve witness text and alignment separately; do not silently normalise either side.
3. Align spans with CollateX or a simple edit aligner, then review every alignment manually.
4. Label content component (`classification`, `location`, `ethnic`, `rule`, `source`, `quotation`, `history`, `myth`, `cross_reference`, `other`) and operation (`keep`, `delete`, `replace`, `move`, `join`, `add`, `uncertain`).
5. Reserve whole pairs as blind test cases.
6. Estimate survival rates and the precision of proposed redaction symptoms.

This should precede any claim about H1/H2/H3 classification. It produces both a scholarly dataset and a calibration set for the revised skills.

### Pilot 2: component, voice, and citation-scope annotation

**Research question:** Who or what is responsible for each proposition in an entry?

Create stand-off span annotations for entry component, discourse voice, source scope, quotation status, and confidence. Begin with manually diverse entries rather than alphabetic convenience samples. Compare rules, Ancient Greek transformers, and weak supervision; use active learning only after a random baseline set exists. The model proposes spans for review and must be allowed to abstain.

### Pilot 3: a source-relay retrieval benchmark

**Research question:** Which named and unnamed passages derive directly or indirectly from which sources?

Construct a benchmark from known direct parallels, known mediated cases, hard lexical false positives, and formulaic negatives. Compare lemma overlap, character n-grams, Passim-style fuzzy matching, dependency features, and SPhilBERTa embeddings. Report recall at a reviewable candidate count, not only aggregate accuracy. The output is a ranked dossier queue, not an automated source finding.

### Pilot 4: recension fingerprints across indirect witnesses

**Research question:** What form of the *Ethnika* did each later reader use?

Represent passage agreement as a network with typed operations and uncertainty. Cluster only after controlling for the possibility that a later author supplemented Stephanos. Use contamination-aware models and inspect block-level switching. This is the most promising route to testing whether the “richer epitome” was one stable recension.

### Pilot 5: temporal-uncertain geography

**Research question:** What assertion about which place is made by which source for which time?

Replace a single resolved-place claim with sourced attestations carrying alternative IDs, time ranges, feature types, names, and uncertain geometry. Map confidence and disagreement. This would make the `$historical-geographer`'s source-date/referent-date distinction computable while preserving alternatives.

### Pilot 6: manuscript-image collation

**Research question:** Which apparent anomalies belong to the transmitted epitome, and which to editions or OCR?

Select a short, textually consequential stretch from one openly digitised manuscript, such as [Pal. gr. 57](https://doi.org/10.11588/diglit.38231). Produce line-level HTR with image coordinates, correct it diplomatically, and collate against other witnesses and editions. Do not begin with a whole-manuscript transcription. The pilot's success measure is variant recovery and error characterisation, not low aggregate character error alone.

## V. Evaluation rules for all computational work

1. **Prediction is not evidence.** A model can rank a dossier or propose an annotation; the finding must cite the witness or external parallel.
2. **Preserve the layer.** Never train on modern editorial supplements as if they were manuscript text.
3. **Prevent leakage.** Split by entry family, source block, or witness pair where ordinary random splitting would put near-duplicates in train and test.
4. **Control the confounders.** Letter, headword morphology, source author, topic, entry length, coverage, physical lacuna, and quoted material can all mimic a layer signal.
5. **Use out-of-domain tests.** Formula-heavy entries and random continuous stretches should both appear in evaluation.
6. **Report uncertainty and abstention.** Accuracy without coverage is misleading in a system that can decline to decide.
7. **Prefer interpretable edits and features.** A span deletion, source-scope error, or dependency pattern is more useful than a visually attractive embedding cluster.
8. **Test against stronger ordinary alternatives.** Scribal corruption, physical loss, inherited source compression, and formulaic genre must be evaluated before invoking epitomisation.
9. **Pre-register global hypotheses.** Especially for proposed stages, specify expected observations before examining clusters.
10. **Do not generate lost wording.** A deletion model estimates classes and probabilities; it must not fill the lacuna with fluent pseudo-Stephanos.

## VI. How the seven skills have been refocused

The corresponding skill revisions make the research agenda operational at entry level:

| Skill | New focus |
|---|---|
| `$textual-critic` | Names the witness layer; distinguishes conjecture, corruption, physical loss, interpolation/contamination, and redactional seam; records ordinary alternatives; never reconstructs lost wording. |
| `$lexicographer` | Separates attested, local, analogical, normative, and merely reported forms; treats derivational families and source voice as units; scopes rarity claims to the available corpus. |
| `$source-critic` | Tests the scope and mediation of every authority; distinguishes direct, mediated, parallel, traditional, and unattributed material; rejects circular fragment reconstruction. |
| `$historical-geographer` | Separates source date, referent date, and Stephanos date; types entity and name relations; keeps uncertain regions and alternatives instead of forcing coordinates. |
| `$stephanos-specialist` | Analyses entry architecture and redaction symptoms; requires a local symptom, claimed layer, and strongest non-redactional alternative for every epitomisation finding; does not name stages or agents without typed evidence. |
| `$translation-critic` | Translates the supplied witness rather than a silently reconstructed original; preserves telegraphic joins, source scope, and reported/normative distinctions; bounds supplied words. |
| `$scholarly-verifier` | Checks proposition, layer, source scope, alternative mechanism, and translation consequence independently; rejects unjustified stage/agent/date assignments; distinguishes an accepted observation from a required translation revision. |

The structured finding schema does not yet have dedicated `claim_target_layer` or `alternative_mechanism` fields. Until a deliberate schema migration is designed, the revised skills require these in the atomic statement and `--interpretation` or verdict rationale, while preserving all existing CLI flags. The skill hashes will cause the normal `bootstrap-kappa` process to create current relational jobs on the next workflow run.

## VII. Recommended order of investment

If the project can fund only three additions, the order should be:

1. **Gold aligned fuller/shorter pairs and deletion taxonomy.** This changes what can be known.
2. **Passage-level source retrieval with a hard benchmark.** This expands the evidence available to source criticism and recension study.
3. **Component/voice/source-scope annotation with calibrated abstention.** This lets every specialist ask better-bounded questions.

Manuscript HTR, phylogenetic networks, and sophisticated sequence models come after these foundations. They require diplomatic witness data and gold annotations; applying them earlier would produce precise-looking answers to poorly defined questions.

## Final assessment

Research on the *Ethnika* has been rich in editing, individual sources, grammatical phenomena, historical geography, and global narratives of transmission. It has been much less developed in **explicit models of selection**, **passage-level relay**, **reader-specific recensions**, **temporal uncertainty**, and **measured scholarly error**.

The digital opportunity is not to ask a language model to reconstruct the lost work. It is to make the surviving evidence more discriminating:

- convert “epitomised” into a typed edit history;
- convert “Stephanos cites X” into a scoped and possibly mediated relation;
- convert “this is place Y” into a sourced, time-bounded, alternative-aware assertion;
- convert “the style changes here” into a controlled sequential hypothesis;
- convert specialist confidence into calibrated decisions that can remain unresolved.

That programme would test current theories rather than decorate them, and it would make the relational scholarly workflow a source of publishable methodological evidence in its own right.
