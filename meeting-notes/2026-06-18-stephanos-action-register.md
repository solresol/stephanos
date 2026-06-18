# 2026-06-18 Stephanos Action Register

Source transcript: `/Users/gregb/Downloads/07_02 PM - zoom.us meeting June 18_transcript.txt`

This is a working extraction from a noisy Zoom transcript. Names, Greek terms, and some technical metric names should be checked against the project data before they are used in a paper.

## Chat Notes To Preserve

- Gabriel pasted this bibliographic lead for the stylometry/idiolect discussion: "'Identifying the Language of the Individual in the Zenon Archive', in T. V. Evans and D. D. Obbink (eds.), The Language of the Papyri (Oxford: Oxford University Press, 2010), 51-70."
- Gabriel pasted this exact construction note: `πλησίον + GEN. vs προς + DAT. = 'near'`. Use this as the target for the Stephanos "near" construction extraction; the transliterated working label below is `plesion + genitive` versus `pros + dative`.

## Meeting Frame

- The immediate target is to have an article submitted by the end of July 2026.
- The strongest near-term article is the technical/digital-humanities paper about the human-AI translation workflow, prompt/rule iteration, and measurement of translation quality.
- The core evidence base is the set of 100 final approved translations, with prompt-version outputs and human revisions.
- Short philological notes are viable outputs, but each one needs narrow, careful scholarship rather than just a transcript observation.
- A full published translation with commentary is a long-term goal. The near-term publication work should not depend on solving that.

## Greg's Immediate Queue

1. Freeze the exact 100-entry approved translation set for analysis.
2. Produce prompt-version metric tables with semantic metrics and trigram/quadgram or similar surface-style metrics.
3. Count exact, near-exact, no-change, and minor-change translations against the human-approved set.
4. Pull the worst-scoring and best/no-change examples for human review and paper case studies.
5. Split entries into sentences and rerun the most useful metrics at sentence level.
6. Test whether rule/formula hits predict better translation beyond the formula itself.
7. Estimate model randomness by rerunning V3 and, if possible, testing low-temperature output.
8. Run small experiments on the longest or worst entries with a reasoning model and a grammar-parse-first prompt.
9. Validate grammar and etymology tagging before using those counts in arguments.
10. After Gabe updates the spreadsheet, extract the philological/textual notes into a candidate-note register.
11. Use Gabriel's `πλησίον + GEN. vs προς + DAT.` note as the exact target for the "near" construction search.

## Concrete Facts And Numbers From This Meeting

These are measured results or stated facts, not open questions. They anchor the paper and must be verified against the project data before publication (the transcript is noisy ASR; line numbers refer to the source transcript).

- Mood/verb profile of the 100 entries: one optative, no subjunctives, no imperatives; effectively all indicative (lines 807-809). Strongest quantitative support for the "is Stephanus actually easy Greek?" framing. Pair with register notes: Stephanus does not decline duals, uses the pluperfect as a bare emphatic, and deploys the optative "as a flex" (lines 859-871).
- Surface-fidelity baseline: roughly 17% quadgram overlap, i.e. about a one-in-six chance that any four-word run matches the human-approved version (line 369).
- Rule-firing anomaly: the `ethnikon + X` and `settlement + region` recognizers fire less often than a Zipf-like distribution predicts (lines 1132-1152). Gabe notes ethnikon "should be in virtually every passage," so this is either an epitomization fingerprint or a recognizer gap. Resolve which before using it.
- Automated worst-translation detection is asymmetric: it correctly flagged the worst semantic failure (enkomos) but missed grammatical/accentual failures Greta judged "dreadful" (lines 670-672). Evidence that self-scoring has systematic false negatives on grammar errors.
- Named worked examples already identified on screen (ready-made case studies):
  - Kope (fishermen-and-wolves digression): strong long V3 entry, candidate five-star (lines 1247-1255).
  - enkomos / Hesiod quotation: worst entry; silently truncated the quotation mid-passage (lines 628-668).
  - Kytinion / "Kuto's" (barytonos/baritone): follows the accent rule but states something contrary to reality; the automated scorer failed to flag it (lines 695-743).
  - Colossae: formula failure (the "Black Sea" rule should have fired and did not) (lines 600-605).
  - Herodotus: Latinized form despite an explicit instruction to use the Greek form; "in Asia" read as a province where it was a book title (category confusion) (lines 585-608).
  - Three exact matches plus one one-letter-off confirmed live (lines 582-584).

## Immediate Actions

| Priority | Suggested owner | Action | Purpose |
| --- | --- | --- | --- |
| P0 | Greg | Confirm the exact 100-entry approved translation set and freeze it for paper analysis. | Prevent the article metrics from shifting underfoot. |
| P0 | Gabe and Greta | Meet for about an hour next week to finalize remaining translation decisions. | Turn the 100 translations into a stable reference set. |
| P0 | Gabe | Update and circulate the spreadsheet with final Brady changes and philological/textual notes. | Provides the source for notes and for qualitative error analysis. |
| P0 | Greg | Count exact or near-exact matches between machine translations and human-approved versions. | Directly supports the claim that some outputs needed little or no human intervention. |
| P0 | Greg | Compare prompt versions using both semantic metrics and surface/style metrics such as trigram/quadgram overlap. | Separates content fidelity from editorial-style/workload improvement. |
| P0 | Greg | Test whether V2 and V3 are statistically distinguishable and describe the difference as workflow/style if semantic metrics barely move. | Prevents overclaiming quality gains where the real gain is reduced review burden. |
| P0 | Greg | Pull the worst-scoring translations and the no-change or nearly no-change translations for human inspection. | Builds a defensible qualitative error typology. |
| P1 | Greg | Split entries into sentences and repeat the metric analysis at sentence level. | Catastrophic failures likely occur in particular sentences rather than whole entries. |
| P1 | Greg | Look for predictors of poor translation: entry length, rare vocabulary, book/place ambiguity, topicalized word forms, grammatical ambiguity, and rule/formula presence. | Supports a stronger paper claim than aggregate scores alone. |
| P1 | Greg | Run or rerun a grammar parse over the approved translation set and sample-check its accuracy. | Needed before grammar-derived predictors can be trusted. |
| P1 | Greg and Gabe | Distinguish finite verbs from participles and infinitives in any aorist/tense/aspect analysis. | Avoids mixing tense and aspect claims. |
| P1 | Greg | Measure rule-hit distribution and rule saturation: how many rules fire, how often, and whether new rules are still appearing. | Tests whether the rule set is stabilizing and whether formula rules reduce review work. |
| P1 | Greg | Check whether entries containing a recognized formula are more likely to be translated correctly beyond the formula itself. | Tests the idea that formula recognition keeps the model on track. |
| P1 | Greg | Run repeated V3 translations at the current settings, then try low temperature if possible. | Estimates random variance and whether stricter decoding improves style-guide compliance. |
| P1 | Greg | Try a reasoning model on a small set of the longest or worst entries. | Tests whether reasoning helps with internal contradictions, grammar, and accentual terminology. |
| P1 | Greg | Try an experimental "V4" prompt that requires a grammar parse before translation. | Tests whether explicit parsing improves translation without naturalizing Stephanus too much. |
| P1 | Greg | Research existing translation-quality assessment for classical languages. | Needed before proposing a standalone metrics-vs-classicist-grading paper. |
| P1 | Greg | Prototype a small human-rating workflow: pairwise comparison or unseen-translation grading. | Allows external Greek teachers to evaluate AI translations independently. |
| P1 | Greg and Gabe | Extract the spreadsheet's philological/textual notes column into a candidate-note register. | Turns scattered observations into publishable-note candidates. |
| P1 | Greg | Validate the etymology recognizers and define the ontology of categories before using the counts. | The meeting flagged possible miscategorizations. |
| P1 | Greg | Analyze correlates for "near" constructions: Gabriel's chat note gives `πλησίον + GEN. vs προς + DAT. = 'near'`; working transliteration is `plesion + genitive` versus `pros + dative`. | Candidate corpus-linguistic study and possible epitomization signal. |
| P2 | Greg | Compare translation fact content against a reference such as Pauly-Wissowa, if feasible. | Tests whether the translation preserves the facts for which Stephanus is actually consulted. |
| P2 | Greg | Prepare a reusable data export with parsed forms, rule hits, metrics, and summary statistics per passage. | Potential data paper or supporting dataset. |
| P2 | Gabe | Phone the three of Trevor Evans's PhD students he is close to (first thing) to gauge interest, then use that to approach Trevor as the route to Klaas Bentein at Ghent. | Concrete first step toward the post-classical Greek collaboration/grant project. |
| P2 | Greg and Gabe | If the response is positive, organize a meeting with Trevor and possibly Klaas/Ghent contacts. | Tests whether the workflow is useful beyond the current Stephanos project. |
| P2 | Greg | Decide whether the finished book-by-book translation should live only on the site/PDF or also in some more permanent distribution channel. | This is a longer-term publication strategy question, not needed for the July article. |

## Paper-Facing Analysis Tasks

These are the analyses most directly useful for the end-of-July article.

1. Freeze the 100-entry corpus and record prompt versions, model version, temperature, and any rerun conditions.
2. Produce one table of prompt-version metrics: semantic similarity, n-gram overlap, exact matches, near matches, and no-change cases.
3. Produce one table of human-workload proxies: edits required, unchanged strings, formula compliance, and repeated style-guide fixes.
4. Produce an error typology with examples: book title vs place/province confusion, Latinized name drift, topicalized or misaccented forms, compact syntax, missing copula/complement issues, and grammatical-gender confusion.
5. Produce a short set of qualitative case studies. Candidates already chosen on screen (see Concrete Facts): Kope (excellent long), enkomos/Hesiod (severe failure), Colossae (formula failure), Kytinion/Kuto's (rule-followed-but-wrong grammar), Herodotus (Latinized-form/category drift). Add one case where the model preserves content but not the desired style.
6. Decide whether the reasoning-model and grammar-parse-first runs are part of the main paper or only future work. They may be too distracting unless they produce a clean result quickly.

## Candidate Short Notes

These should be moved into a separate note register once the spreadsheet is updated.

- Brady's emendation from the first Kappa entries.
- The possible genealogy corruption where X is said to be the son of Y but should be father of Y.
- Lexical notes on words in the 100 entries that appear to be absent from major lexica.
- A note on `paraea`/`paraios`-type geography if the specific form and evidence justify it.
- A note on the `prolambano`/accentuation problem if it proves to be textual rather than only translational.
- A note or register of Stephanus' vocabulary choices that require consistent English equivalents.

## Decisions and Guardrails

- Keep the immediate article focused. The strongest article is not "AI translated Stephanus perfectly"; it is "a human-AI workflow can move an unreliable off-the-shelf translation toward a reviewable scholarly translation, and the measurements show different dimensions of improvement."
- Do not treat counts alone as a classics argument. For classics-facing work, the counts need a question, an ontology, an accuracy bound, and an explanation of what the pattern means.
- Do not rely on an unreliable automated translation as a citation-seeking publication. If the translation is released, the better path is a visible website/PDF and book-by-book finalized versions.
- Treat philological notes as real publications, but not as easy ones. They are short because the question is narrow, not because the work is light.
- Keep Pausanias stylometry separate from the Stephanos paper unless it is only used as a methodological analogy.
- Venues: Classical Quarterly is actively soliciting short notes under its new CUP contract, which is a time-sensitive opening for the Kappa notes (lines 1018-1019). Conference papers do not count in this field (lines 978-982). Topos Text is the one realistic host for an unreliable-but-useful full translation; otherwise prefer the site/PDF and book-by-book finalized releases (lines 1090-1100).

## Risks To Check

- ASR errors in the transcript obscure several names and technical terms.
- Model naming and versioning must be exact before publication.
- Current results are based on 100 entries, mostly from Kappa; broad Stephanus claims need more coverage.
- Grammar and etymology tags need accuracy bounds before they support arguments.
- V2-to-V3 gains may be more visible in editorial workload than in semantic metrics.
- External human grading needs a protocol before it can be cited as evidence.
- At line 348 Greg says trigram/quadgram overlap showed "a difference from V3 to V4," but V4 does not exist yet (it is the proposed grammar-parse-first run). This is probably an ASR slip for "V2 to V3"; confirm against the actual metric output before relying on it, since it bears on the central V2-to-V3 claim.
