# Paper And Note Idea Bank From 2026-06-18 Transcript

Source transcript: `/Users/gregb/Downloads/07_02 PM - zoom.us meeting June 18_transcript.txt`

This is a parking lot for ideas, not a commitment to pursue all of them. Readiness labels are deliberately conservative.

## Readiness Key

- **Now**: can feed the July 2026 technical paper.
- **Next**: likely publishable with a bounded extra study.
- **Later**: probably needs more data, more collaborators, or deeper field expertise.
- **Note**: suitable for a short philological note if the textual and bibliographic work checks out.

## Main Paper Ideas

| Readiness | Idea | Core question | Needed next step |
| --- | --- | --- | --- |
| Now | Prompt/rule iteration for Stephanus translation | How do prompt versions and formula rules move output from plausible gist to reviewable scholarly translation? | Freeze the 100-entry corpus and produce prompt-version metric tables. |
| Now | Workflow improvement rather than simple quality improvement | Did V3 reduce human review burden even where semantic metrics barely changed? | Count no-change, near-change, and repeated style-guide corrections. |
| Now | Error typology for AI translation of an epitomized reference text | What does the model get wrong when the Greek is compact, metalinguistic, or fact-dense? | Pull worst-scoring examples and classify failures. |
| Now | Sentence-level translation analysis | Are catastrophic failures localized to particular sentences or structures? | Split entries into sentences and rerun metrics. |
| Now | Rule/formula effects | Does recognizing a Stephanus formula help only that phrase or the whole sentence? | Compare rule-hit and non-rule-hit sentences. |
| Now | Exact-match and no-edit cases | How often does the model produce a translation that human reviewers accept unchanged? | Count exact and near-exact matches against the approved set. |
| Next | Grammar-parse-first translation | Does requiring a grammar parse before translation reduce failures? | Test a small V4 run on longest/worst passages. |
| Next | Reasoning-model translation | Do reasoning models help with internally contradictory metalinguistic examples? | Run ten longest or ten worst entries through a reasoning model. |
| Next | Translation metric validity for classical languages | Do BLEU-like, embedding, and n-gram metrics agree with classicist grading? | Recruit external Greek teachers for small graded/ranked evaluation. |
| Next | Fact fidelity in Stephanus translation | Does the translation preserve the facts for which Stephanus is consulted? | Compare extracted facts to Pauly-Wissowa or another reference source. |
| Later | Autoethnographic account of human-AI philological work | What changed in the human work when translation became a human-AI pipeline? | Collect short reflective memos and concrete examples from reviewers. |
| Later | Data paper for parsed Stephanus outputs | Can parsed passages, rule hits, metrics, and translations be published as a reusable dataset? The rule-discovery and human-correction history is itself a candidate dataset for studying human-AI scholarly workflows. | Define export schema and validation protocol. |

## Short Notes And Philological Leads

| Readiness | Lead | Why it may matter | Needed next step |
| --- | --- | --- | --- |
| Note | Brady's emendation in early Kappa | Mentioned as a likely short note candidate. | Extract exact passage, apparatus, and bibliography. |
| Note | Genealogy corruption: son/father reversal | Mentioned as a candidate note from Greta's observation. | Confirm exact entry and compare editions. |
| Note | Lexical items absent from major lexica | Gabe estimated several words in the 100 entries may not be captured by lexica. | Pull candidates and check LSJ, supplements, and specialist resources. |
| Note | `prolambano` / "anticipated" translation issue | May involve accentuation or form analysis rather than merely English wording. | Confirm Greek form, accents, and manuscript/editorial evidence. |
| Note | Stephanus' geography across water (`paraea`-type vocabulary) | The discussion suggests culturally and politically specific terms that English flattens. | Identify exact forms and compare Strabo, inscriptions, and lexica. |
| Note | Topicalized or misaccented forms | The model sometimes "corrects" forms that are the topic of discussion. | Gather examples where accent/form is itself the subject. |
| Note | `κατά` + accusative for location across water | Gabe's Koine reading group (John Lee's) hit this construction and was confused; pairs with the peraia note. Possibly peculiar to geographical prose or post-classical Greek. | Collect Stephanus instances; compare Strabo and the reading-group example. |
| Note | `oiketēr` used for brothel residents | Stephanus applies an inhabitant term in an unexpectedly low-register way. | Confirm the entry and check whether the usage is attested elsewhere. |

## Corpus-Linguistic Leads In Stephanus

| Readiness | Lead | Why it may matter | Needed next step |
| --- | --- | --- | --- |
| Later | `πλησίον + GEN.` versus `προς + DAT.`; working label: `plesion + genitive` versus `pros + dative` | Gabriel's chat note glossed both as "near"; possible semantic, geographic, source, or epitomizer distinction. | Extract all instances and map to entry, geography, source, and book/letter. |
| Later | `ethnikon` versus `polites` versus `oiketer` | Inhabitant terms may correlate with place type and formulaic entry structure. | Run full corpus counts, then sample-check meanings. |
| Later | Epicoric versus barbaric labels | Could matter for post-classical Greek linguistics and attitudes to local forms. | Identify all formulae and validate categories with Gabe. |
| Later | Etymology categories and source types | Counts are interesting only if the categories are accurate and argumentative. | Audit recognizer accuracy and define category ontology. |
| Later | Animal etymologies and local/barbaric ethnonyms | Gabe suggested a possible collocation worth testing. | Test statistically, then inspect passages qualitatively. |
| Later | Pendant nominatives | Gabe has a specialist contact who may judge whether Stephanus' usage is normal or strange. | Extract examples from the notes spreadsheet and send a small sample. |
| Later | Formula saturation curve | The rule-accretion graph may show when the review team stopped finding new recurring formulae. | Verify rule history and interpret as workflow evidence, not corpus fact. |
| Later | Epitomizer fingerprints | Grammar or formula distributions may line up with hypothesized epitomizing layers. | Compare Kappa with Delta/Eta or known textual-history divisions. See `paper/notes/2026-06-19-stylometric-fingerprinting-options.md` for the literature scan, first recogniser-vector UMAP, and implementation plan. |
| Later | Source/fragments extraction and linked data | Aligning citations/fragments with existing databases could produce a major digital resource. | Review existing work, especially Monica Berti-style fragment extraction. |

## Post-Classical Greek / Collaboration Ideas

| Readiness | Idea | Why it may matter | Needed next step |
| --- | --- | --- | --- |
| Later | Apply the workflow to documentary corpora | Post-classical Greek has huge corpora and limited labor for detailed linguistic tagging. | Discuss with Trevor and/or Ghent contacts. |
| Later | Mixed aorist/perfect forms in documentary Greek | Gabe identified misspellings/confused forms as a place where advanced search could help. | Scope a pilot against DDbDP/Trismegistus-like metadata. |
| Later | Similar-passage search using embeddings | Greg's phrase embeddings may support content-based discovery beyond manual tags. | Demonstrate on a small corpus and compare with existing metadata. |
| Later | Grant proposal for post-classical Greek tools | The workflow may be fundable if framed as scalable corpus-linguistic infrastructure. | Get advice from Gabe's colleagues, Trevor, and Ghent-oriented contacts. |

## Key People And Prior Work To Cite Or Contact

Names are from a noisy transcript; verify spellings before use.

| Person / work | Relevance | Note |
| --- | --- | --- |
| Klaas Bentein (Ghent) | Most senior post-classical Greek scholar at Ghent; entirely corpus/token-counting work; presented computational-corpora methods at a Septuagint conference; "very pro" these tools. | The eventual collaboration target. Gabe has prior, slightly awkward, contact. Approach via Trevor. (ASR: "Class Bentan" / "CLA".) |
| Mark Janse; Ezra la Roi (Ghent) | Other Ghent post-classical Greek names raised in the call. | ASR: "Markiansa", "Ezra Leroy". |
| Trevor Evans (Macquarie) | Named among the top post-classical Greek scholars; open-minded about these tools; the realistic middle-man to Ghent. His Zenon-archive paper is the direct model for idiolect/fingerprint work — particles and clause-coordination, not tense. | Citation captured in the action-register chat notes and the Pausanias table below. |
| John Lee | Runs the Koine reading group; source of the "study papyri because they are autographs" rationale. | — |
| "Mark" (Gabe's colleague) | Did a PhD on pendant nominatives; the person to send a Stephanus pendant-nominative sample to. | May be the same Mark Janse — disambiguate. |
| Monica Berti | Prior work on fragment extraction from Stephanus; the starting point for any citation/fragment programme. | Already noted in the corpus-linguistic leads. |
| Galen / Zainaldin paper | The MT-evaluation paper this project effectively replicated; model and comparison point for both the metrics paper and Paper 1's confirmation claim. | Project already has Zainaldin comparison charts. |

## Related Pausanias Ideas Mentioned In The Transcript

These are not Stephanos paper items, but they may be useful in a separate planning document.

| Readiness | Idea | Caution |
| --- | --- | --- |
| Later | Aorist decline and imperfect increase across Pausanias | Must distinguish content from style and finite verbs from participles/infinitives. |
| Later | Stylometric change across a long prose work | Needs prior scholarship on Greek prose stylometry and accuracy bounds for grammar tags; Gabriel's chat citation to "'Identifying the Language of the Individual in the Zenon Archive', in T. V. Evans and D. D. Obbink (eds.), The Language of the Papyri (Oxford: Oxford University Press, 2010), 51-70" is a starting point. |
| Later | Depopulated cities and absence of alternative traditions | This already has a clear classics-style argument structure. |
| Later | Grammar-feature clustering of content types | Interesting, but must explain what the clusters mean rather than just show a graph. |

Redirect from the meeting: the aorist decline is probably a content effect (later books narrate less past action; aorists likely replaced by historical presents), not a style change. For a genuine authorial fingerprint, follow Trevor Evans's Zenon-archive method and weight particles and clause-coordinating constructions over tense frequencies (transcript lines 1588-1602). Choose test-bed corpora that remove the manuscript-tradition confound: Pausanias (one surviving manuscript) and documentary papyri (autographs) are ideal; biblical Greek is the opposite.

## Ideas To Deprioritize For Now

- Self-publishing an unreliable automated Stephanus translation for citations. The meeting leaned toward visible site/PDF outputs and book-by-book finalized releases instead.
- A broad "curious things we found" paper. The better use is a future-work section, autoethnographic reflection, or separate notes once each claim is researched.
- A pure counts paper with no argument. Counts become publishable when tied to an ontology, accuracy bounds, and a scholarly question.
- Full translation-with-commentary publication. Valuable, but too large for the current paper deadline.
