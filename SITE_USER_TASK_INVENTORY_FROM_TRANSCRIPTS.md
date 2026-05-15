# Stephanos User Task Inventory From Transcripts

Date: 2026-05-15

Status: design discovery artifact. This is a transcript-derived task inventory, not an implementation patch.

Related artifacts:

- `SITE_DESIGN_DISCOVERY_AND_WORK_PLAN.md`
- `SITE_PAGE_INVENTORY_AND_OWNERSHIP.md`
- `output/playwright/site-design-2026-05-15/README.md`

## Purpose

This document extracts user tasks from the Stephanos meeting transcripts and transcript-derived notes. The goal is to make explicit what people are trying to do with the site and supporting tools before redesigning navigation, page families, and page ownership.

A "task" here means a user job or recurring workflow, not necessarily a single implementation ticket. Some tasks are already partly implemented. Some are research tasks that need exports or analytics rather than a polished public page. Some are operational tasks that should be kept away from public navigation.

## Sources Reviewed

This pass used the filed Stephanos transcript set, curated transcript excerpts, action-item notes, and one extra unfiled personal-room transcript found in Downloads. A wider keyword pass over Downloads found the March 26 Stephanos meeting transcript as another relevant source.

| Code | Source | Lines / scope used | Notes |
| --- | --- | --- | --- |
| S0 | `/Users/gregb/Downloads/07_02_pm_-_zoom.us_meeting_march_26_transcript.txt` | 1,057-line transcript; especially lines 391-426, 430-571, 597-679, 697-723, 850-998 | Early translation-interface, Billerbeck, source-text, and prompt-version discussion. |
| S1 | `/Users/gregb/Documents/devel/papers/stephanos/triangulated-translations-paper/2026-04-23-zoom-transcript.txt` | 1,001-line transcript; especially lines 98-177, 214-320, 619-790, 834-903 | Translation variants, guidance, whole-corpus search, backlog tasks, and triangulation-paper framing. |
| S2 | `/Users/gregb/Documents/devel/papers/stephanos/2026-04-30-meeting/feature-request-excerpts.md` | Full excerpt file, lines 7-257 | Curated feature requests from the April 30 transcript. |
| S3 | `/Users/gregb/Documents/devel/papers/stephanos/2026-04-30-meeting/new-translation-prompt-excerpts.md` | Full excerpt file, lines 7-260 | Prompt, rule, quotation, citation, and provenance tasks. |
| S4 | `/Users/gregb/Documents/devel/papers/stephanos/2026-05-07-meeting/action-items.md` | Full action-item file, lines 14-104 | Entity model, rule impacts, prompt-version, and paper/research tasks. |
| S5 | `/Users/gregb/Documents/devel/papers/stephanos/2026-05-08-greg-and-greta/sources/stephanus-conversation-excerpts.md` | Full excerpt file; especially lines 7-18, 35-180 and later Stephanos excerpts | Research design, ethics, AI translation comparison, footnotes, and public-book ideas. |
| S6 | `/Users/gregb/Documents/devel/papers/stephanos/greta_hawes's_personal_meeting_room_transcript.txt` | 1,012-line transcript; especially lines 520-880 | Translation evaluation, linked-data public interface, entity correction, commentary, and Kappa demo. |
| S7 | `/Users/gregb/Downloads/greta_hawes's_personal_meeting_room_transcript.txt` | 816-line unfiled transcript; especially lines 320-390, 520-810 | Distinct from the filed personal-room transcript; entity labels, Brady spreadsheet, slow review page, next-20 batch, source-citation export. |
| S8 | `/Users/gregb/Documents/devel/papers/stephanos/2026-05-14-meeting/action-items.md` | Full action-item file, lines 11-78 | Most recent app-work priorities, ToposText comparison, entity-model cleanup, Keesling-source precedence, review navigation, UI polish. |
| S9 | `/Users/gregb/Documents/devel/papers/stephanos-ethnika-paper/ideas-from-transcript.md` | 60-line derived note | Paper ideas and evaluation framing extracted from transcript material. |

## High-Level Task Clusters

The transcript evidence points to six major task clusters:

| Cluster | Primary users | Design meaning |
| --- | --- | --- |
| Translation review and finalization | Greta, Gabriel, Greg | Needs a protected review workbench organized by batch, status, entry, source text, translation variants, and final text. |
| Guidance and rule governance | Gabriel, Greg, Greta | Needs a protected rule workbench plus public/provenance views, with rule hits visible in review. |
| Entity curation and linked data | Brady, Greg, Greta | Needs an entity-centred queue and authority-record workspace, not only headword-centred pages. |
| Public scholarly reading | Public readers, Greta, Brady, Gabriel | Needs a polished linked text, map, source, entity, search, and commentary experience. |
| Research and publication evidence | Greg, Greta, Gabriel, Brady | Needs exports, metrics, comparison sets, paper evidence, and reproducible snapshots. |
| Operations and collaboration | Greg, future maintainers, collaborators | Needs diagnostics, freshness, queue state, access, and generated deliverables separated from public nav. |

## Translation Review And Finalization

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| TR01 | Greta, Gabriel | Select the next review slice, usually a Kappa batch of 20 or 50 entries not already finalized. | S2 lines 241-257; S7 lines 556-628; S8 lines 19-23 | Review landing page should support batch selection by letter, entry order, final status, and translation version. |
| TR02 | Greta, Gabriel | See which entries already have AI, human, reviewed, or final translations before choosing work. | S7 lines 556-628; S8 lines 19-23 | Entry selectors need visible status chips, not just headword labels. |
| TR03 | Gabriel, Greg | Translate/review with Meineke Greek, current AI translation, initial human translation, reviewed/final translation, and notes in the same working frame. | S0 lines 417-426, 569-571, 653-679 | The review page should be a comparison workbench, not a long form that forces scrolling between essential materials. |
| TR04 | Greta, Gabriel | Inspect the full history of translation variants and select or promote the canonical translation. | S1 lines 632-721 | Translation variants should be full-text, readable, and selectable; truncated controls are not enough. |
| TR05 | Greta, Gabriel | Trust that the current displayed AI translation is genuinely the intended current version, not stale V1 or Billerbeck-era output. | S1 lines 632-699; S8 lines 13-20 | Translation version/provenance labels must be prominent and unambiguous on review pages and batch pages. |
| TR06 | Greta, Gabriel | Keep a static reference point for the translation that humans reviewed, even when later AI runs happen. | S1 lines 632-679 | The UI needs immutable run IDs or version choices, not only "latest AI translation." |
| TR07 | Greta, Gabriel | Move quickly through a current letter or batch without returning to the public site. | S8 lines 22-23 | Add in-page selectors, next/previous controls, and a link from review to final workspace. |
| TR08 | Greta | Review all finished translations together, with source text and final English side by side, and edit them as a coherent body. | S2 lines 221-239; S1 lines 727-737 | Final review should be a separate workspace for scrollable corpus-level review and editing. |
| TR09 | Gabriel, Greta | Search the whole corpus to see how a word, formula, or phrase has been handled before. | S1 lines 755-765 | Corpus search belongs inside the review workflow as well as the public site. |
| TR10 | Greg, Greta, Gabriel | Turn a recurring issue into a backlog task, find all affected entries, and tick them off after review. | S1 lines 771-777; S4 lines 58-62 | Rule impacts and search-derived tasks should behave like to-do lists with open/resolved states. |
| TR11 | Greta, Gabriel | See when a new rule affects a previously finalized human translation without letting the machine overwrite the human decision. | S2 lines 174-198; S8 lines 34-35 | Human translations should be protected; new rules should create flags and acknowledgement tasks. |
| TR12 | Gabriel, Greta | View source scans and source text when needed, but avoid old OCR/debug material cluttering the translation task. | S0 lines 597-635; S8 lines 40-44 | Source evidence should be contextual and correct; OCR/debug panels belong in diagnostics, not the primary review path. |
| TR13 | Greta, Gabriel | Add minimal explanatory commentary for difficult phrases during or after final translation review. | S5 lines 610-689; S6 lines 815-834 | Commentary needs phrase-level or passage-level anchors, not just a free-floating notes field. |
| TR14 | Greta, Greg | Ask the system to generate footnotes/commentary after AI or human translation, then review the result. | S5 lines 670-689 | Footnote generation should be an explicit review action with human approval, not an automatic public output. |
| TR15 | Brady, Gabriel, Greta | Handle source quotations and poetry differently from Stephanos prose, including use of consistent source translations where appropriate. | S0 lines 487-571; S3 lines 145-162; S6 lines 656-674 | Review needs quote/source-type signals and style instructions visible near the affected passage. |
| TR16 | Greta, Greg | Diagnose and fix slow review-page loading when opening entries. | S7 lines 601-611 | Performance is part of usability; review pages need load-time checks and possibly lighter initial payloads. |

## Guidance And Rule Governance

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| TG01 | Greg, Gabriel | Generate or update a translation prompt from Gabriel's comments and the current human review notes. | S3 lines 7-28; S0 lines 961-998 | Prompt-generation inputs and outputs need traceable versions and reviewer-visible summaries. |
| TG02 | Greg | Detect only the relevant formula/proper-noun/gloss guidance before translating an entry, instead of dumping every rule into a giant prompt. | S3 lines 29-49; S1 lines 269-306 | Rule matching should be a separate pipeline step with auditable outputs. |
| TG03 | Greta, Gabriel | See which formula/guidance hits fired for the translation being reviewed. | S2 lines 18-44; S3 lines 51-74 | Review pages need a compact, reviewer-facing "guidance hits" panel. |
| TG04 | Gabriel | Add or edit rules while reviewing without making translation provenance ambiguous. | S2 lines 46-69; S3 lines 76-93 | The system must record prompt version plus guidance-rule revision for every translation run. |
| TG05 | Gabriel | Browse rules in a dense spreadsheet-style table with sorting, filtering, grouping, domains, and categories. | S2 lines 71-95 | Guidance management should not be card-only; it needs table ergonomics. |
| TG06 | Gabriel, Greg | Distinguish tentative recognizers from settled translation guidance. | S2 lines 118-139; S4 lines 64-68 | Rule lifecycle labels should drive behavior: detect-only, advisory, required, replacement, inactive. |
| TG07 | Gabriel, Greg | Test a candidate formula or collocation against sampled entries and get occurrence evidence, with progress feedback. | S2 lines 96-117; S4 lines 64-68 | Formula discovery needs a long-running scan UI with status and result review. |
| TG08 | Gabriel, Greta | Express context-sensitive vocabulary bias without turning it into a hard find-and-replace rule. | S2 lines 140-172; S3 lines 95-121 | Add a rule type for advisory contextual bias, separate from proper nouns and settled formulae. |
| TG09 | Greg, Greta, Gabriel | Make rule-impact semantics clear for `replace`, `required`, and `advisory`, and handle AI-only translations differently from human-reviewed translations. | S8 lines 34-35 | Rule-impact UI should explain what action will be taken and when human confirmation is required. |
| TG10 | Gabriel, Greg | Use guidance/formula/gloss frequency as research evidence, not only as translation scaffolding. | S1 lines 214-320, 834-855; S8 lines 37-38 | Guidance pages need usage statistics and exportable evidence, ideally grouped by rule and corpus slice. |
| TG11 | Gabriel | Keep exploratory metalinguistic, prosodic, accentuation, and dialect issues visible because they are recurring weak spots for the AI. | S3 lines 217-260; S7 lines 528-537 | The rule system should support special-case warnings and examples, not only ordinary lexical glosses. |
| TG12 | Greg, Greta, Gabriel | Verify that the intended current prompt profile is visible and that current runs are producing comparable entries. | S4 lines 49-56; S8 lines 13-20 | Prompt/profile status belongs on review and operations surfaces, with clear current-vs-legacy labels. |

## Entity Curation And Linked Data

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| EC01 | Brady, public readers | See separately visible, clickable entities on public headword pages. | S4 lines 22-26 | Public entry pages should treat entities as first-class linked objects. |
| EC02 | Brady | Open a single entity-editing pane/page, reachable from many contexts, with Greek/English context and highlighted evidence. | S4 lines 25-29; S6 lines 724-737 | Entity review should be entity-centred, with headwords as evidence. |
| EC03 | Brady, Greg | Correct entity type, place type, region, authority IDs, and original/JBK/final ID tracking. | S4 lines 28-29 | Authority records need structured editable fields and provenance, not just a free-text correction. |
| EC04 | Brady, Greg | Split homonymous or enumerated places into distinct entities, including multi-place headwords such as Caesarea. | S4 lines 31-35; S8 lines 28-29 | The data model and UI need one headword-to-many-entities handling. |
| EC05 | Brady, Greg | Filter Wikidata candidates by expected entity type and sanity-check suspicious matches. | S4 lines 37-41 | Candidate lists should be curated and typed; diagnostics should surface likely mismatches. |
| EC06 | Brady, Greta | See Wikidata English label/description and a clear "not found" state, not only a raw QID. | S7 lines 320-334 | Authority chips need human-readable labels, confidence, and failure states. |
| EC07 | Brady, Greg | Import Brady's spreadsheet/ToposText work as human corrections or ground truth, then review discrepancies. | S7 lines 352-384 | Imports should produce trusted corrections plus a discrepancy queue. |
| EC08 | Brady, Greg | Compare Stephanos AI/entity extraction with Brady's current Dropbox HTML rather than stale public ToposText. | S8 lines 25-26 | ToposText intake should be a repeatable protected workflow, not a one-off report. |
| EC09 | Brady, Greg | Track temporary and external authority states such as ToposText, Wikidata, Pleiades, Manto, RE, `zzz`, `YY`, and `JJ`. | S4 lines 28-29; S8 lines 25-29 | The entity UI needs stable labels for provisional, missing, inferred, and external IDs. |
| EC10 | Brady, Greta | Exchange Manto/entity exports and tagged external texts such as Zenobius/Zenobiaus. | S4 lines 75-79 | Entity workflows need import/export affordances and dated snapshots. |
| EC11 | Brady, Greg | Keep oracle and Billerbeck-derived factual cross-reference data useful while avoiding public reuse of protected text. | S4 lines 43-47 | Public pages and private data views need different disclosure rules. |
| EC12 | Brady, Greg | Export cited works/authors in CSV for external ancient-author/work Wikidata projects. | S7 lines 767-783 | Source-citation extraction needs status, CSV exports, and external-project formatting. |
| EC13 | Brady, Greta, Greg | Delay nodegoat as a primary workflow until the structured data is more settled; keep it as a later visualization/export option. | S7 lines 671-680 | Nodegoat should not drive the near-term IA; Stephanos needs its own entity workbench first. |

## Public Scholarly Reading

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| PR01 | Public readers, Brady | Read Greek and English side by side. | S6 lines 671-674, 797-813 | The canonical entry page should foreground source text and public translation together. |
| PR02 | Public readers | See places from the visible text on a connected map. | S6 lines 797-813 | Map and text should be linked primary surfaces, not disconnected pages. |
| PR03 | Public readers | Hover or click entities to reach Wikidata, Wikipedia, place pages, and other Stephanos uses. | S6 lines 797-813 | Entity links should be embedded in reading, with concise previews. |
| PR04 | Public readers | Follow cited authors, works, and passages such as Strabo references. | S6 lines 849-853; S7 lines 767-783 | Source/work pages and cited-passage links should be part of the public reading model. |
| PR05 | Public readers, Greta, Gabriel | Access phrase-level explanatory commentary without overwhelming the base translation. | S6 lines 815-834 | Commentary should be layered: hidden by default, available on hover/click or a commentary mode. |
| PR06 | Public readers, reviewers | Search headwords, Greek, English translations, entities, and formula-guidance terms. | S1 lines 755-765 | Search should be a core product affordance across Read and Review. |
| PR07 | Public readers | Understand what is final, human-reviewed, AI-draft, source-derived, or method/provenance material. | S1 lines 834-855; S8 lines 13-20 | Public status labels must be simple and conservative. |
| PR08 | Public readers, Greg | Download or cite stable outputs: PDF/book, CSV, data exports, and perhaps a public Kappa demo. | S5 lines 610-689; S6 lines 858-863 | Downloads should be framed as publication/data outputs, not pipeline leftovers. |
| PR09 | Public readers, paper reviewers | See enough method/scaffolding to understand why the translation required guidance, without crowding the reader UI. | S1 lines 834-855 | Methodology and prompt/guidance provenance should be reachable from entries but not dominate the main reading page. |
| PR10 | Greta, public readers | Experience Stephanos as a polished scholarly product comparable in confidence to ToposText. | S8 lines 46-47; S6 lines 797-813 | The public site needs a coherent visual system, object pages, map/text linkage, and restrained navigation. |

## Research And Publication Evidence

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| RP01 | Greg, Greta | Generate multiple AI translations and use human-translated Stephanos entries as gold data. | S5 lines 66-100 | Review/export tools should preserve comparison sets and human-gold references. |
| RP02 | Greg, Greta | Test whether multiple translations help professional translators or non-experts identify translation issues. | S5 lines 81-100, 200-210 | Research-facing exports need participant materials, anonymizable examples, and version labels. |
| RP03 | Greg, Greta | Prepare human-research ethics, opt-out language, and tutorial recruitment logistics. | S5 lines 109-180 | This is outside the public site, but the tool must support controlled packets and consent-safe workflows. |
| RP04 | Greta, Gabriel, Greg | Compare successive rounds of 20 translations and measure whether prompt/rule improvements reduce errors. | S6 lines 526-550; S7 lines 623-628 | Translation runs need comparable snapshots by round and entry set. |
| RP05 | Gabriel, Greta, Greg | Classify edits by style, reader comprehension, and necessary semantic correction; possibly use an independent rater. | S6 lines 557-641 | Review notes and final edits should be exportable into a coding/evaluation table. |
| RP06 | Greta, Gabriel, Greg | Track Billerbeck/German leakage and triangulated translation evidence. | S0 lines 430-571, 697-760; S3 lines 164-215; S5 lines 515-541 | The system should preserve suspicious examples, source variants, and notes as paper evidence. |
| RP07 | Gabriel, Greg | Use formula/guidance distributions as philological evidence about Stephanos, epitomizers, or lexical domains. | S1 lines 214-320; S8 lines 68-69 | Guidance analytics should be exportable and organized by rule, entry, source, and corpus slice. |
| RP08 | Greg, Greta | Analyze translation length/wordiness and compare Greek source length to English output. | S5 lines 900-981; S8 lines 40-41, 77-78 | Length analytics must verify source mappings before becoming paper evidence. |
| RP09 | Brady, Greg | Measure linked-data/entity extraction accuracy against Brady's corrections. | S6 lines 671-718, 724-737 | Entity correction UI should log machine proposal, human correction, and error category. |
| RP10 | Greg, Greta, Gabriel | Write an infrastructure/process paper about iterative AI-assisted scholarly translation and quality control. | S4 lines 89-90; S6 lines 526-656 | The product should generate method evidence, not only finished translations. |
| RP11 | Gabriel, Greta, Greg | Present Kappa or another bounded slice as a demonstrator of the whole workflow and public interface. | S6 lines 858-863; S8 lines 19-23 | Kappa should become a coherent demo path: public read view, review history, entities, guidance, and exports. |
| RP12 | Greta, Gabriel | Classify mythology, foundation stories, animal motifs, landscape effects, or other research domains in entries. | S4 lines 95-96; S5 lines 719-724 | Research tagging may need lightweight corpus-classification fields or exportable derived reports. |
| RP13 | Greg, Brady, Greta | Share concrete outputs with external communities such as Perseus/Greg Crane, Monica Berti's Wikidata project, or Manto. | S5 lines 720-766; S7 lines 767-810 | External-facing exports should be stable, documented, and decoupled from internal diagnostics. |

## Operations And Collaboration

| ID | Primary users | User task | Evidence | Design consequence |
| --- | --- | --- | --- | --- |
| OP01 | Greg | Monitor translation, OCR, entity, guidance, and structured source-citation progress with fresh counts and ETA. | S7 lines 767-783; S8 lines 37-44 | Operations pages need one dashboard with freshness and queue state. |
| OP02 | Greg | Apply source precedence rules correctly, especially Keesling before Meineke where available. | S8 lines 31-32 | Source selection should be transparent in review payloads and public provenance. |
| OP03 | Greg, reviewers | Ensure review pages show the correct source scan/page and do not derive images from mismatched printed page numbers. | S8 lines 40-44 | Scan lookup must be a tested source-evidence service, not ad hoc filename inference. |
| OP04 | Greg | Keep review data, reviews database, guidance state, generated site, and deployment outputs aligned. | S4 lines 49-56; S8 lines 13-23 | Review/export/deploy pipelines need status checks before meetings and public releases. |
| OP05 | Greg, Gabriel | Generate review packets, batch lists, and email links so collaborators can start work without rediscovering entries. | S6 lines 781-782; S8 lines 51-55 | Batch actions should produce sharable links and dated review sets. |
| OP06 | Greg | Give collaborators such as Amelia accounts or read/edit access for targeted Greek/place questions. | S1 lines 777-790 | Access management needs roles: reviewer, entity curator, read-only helper, maintainer. |
| OP07 | Greg | Speed long-running structured source-citation extraction when it blocks external sharing. | S7 lines 767-783 | Operations should expose tunable throughput and expected completion. |
| OP08 | Greg, public readers | Keep operational diagnostics out of the public reader's primary navigation. | Derived from current page inventory plus S8 lines 46-47 | Operations needs its own authenticated or clearly separate area. |
| OP09 | Greg | File and de-duplicate transcript sources so design and research evidence can be traced later. | This pass found S7 and S0 outside the filed meeting tree | Transcript evidence should have canonical storage, dates, and links to derived action/task artifacts. |

## Design Priorities Implied By The Tasks

1. Build a real Review landing page before polishing isolated review forms. The most repeated pain point is not one missing field; it is moving through a batch with reliable status, version, source, and finalization context.

2. Treat translation version/provenance as a primary UI element. Stale AI output, Billerbeck-era output, prompt versions, human precedence, and canonical translation selection are central to trust.

3. Separate public reading from editorial and operational work. Public readers need text, translation, source, entities, map, search, commentary, and downloads. Reviewers need work queues and version history. Maintainers need freshness and pipeline state.

4. Make Guidance a workbench, not just a public page. Gabriel's tasks require dense rule browsing, rule lifecycle, usage statistics, formula discovery, and impact acknowledgement.

5. Make Entities entity-centred. Brady's tasks are about authority records and linked-data correction across the corpus. Headwords are evidence and contexts, not the right top-level object for curation.

6. Use ToposText as a design reference for confidence, object pages, map/text linking, and scholarly polish. Do not copy its backend assumptions; Stephanos has stronger AI provenance and review-state needs.

7. Keep research outputs as first-class artifacts. The project needs comparison sets, notes, coding tables, exports, analytics, and demos. These are not incidental to the UI; they are part of why the UI exists.

## Candidate Page / Workspace Set

The task inventory supports this working page set:

| Workspace | Primary task coverage | Owner |
| --- | --- | --- |
| Public entry page | PR01-PR07, EC01, RP11 | Public reader |
| Public map/text page | PR02-PR04, EC01 | Public reader / Brady |
| Public sources and works pages | PR04, EC12, RP13 | Public reader / Brady |
| Review landing and batch selector | TR01-TR07, OP05 | Greta / Gabriel |
| Entry review workbench | TR03-TR07, TR11-TR15, TG03 | Greta / Gabriel |
| Final translation workspace | TR08-TR10, TR13-TR14 | Greta |
| Guidance rules workbench | TG01-TG12 | Gabriel / Greg |
| Rule impacts to-do list | TR10-TR11, TG09 | Greta / Gabriel / Greg |
| Entity curation dashboard | EC02-EC09, RP09 | Brady |
| ToposText / Brady intake report | EC07-EC09 | Brady / Greg |
| Research analysis landing | RP04-RP12, TG10 | Greg / paper authors |
| Operations dashboard | OP01-OP09 | Greg |

## Useful Interview Questions

If emailing people for design clarification, ask only targeted questions that the transcripts do not already answer.

| Person | Question |
| --- | --- |
| Greta | When you open Stephanos for review, do you want to start from a batch, a headword, a final-translation list, or a search? |
| Greta | Which status labels would you trust on a public page: AI draft, human reviewed, final, stale, needs review, source uncertain? |
| Gabriel | What are the minimum columns needed in the dense guidance/rule table for real work? |
| Gabriel | When a search finds previous occurrences of a term/formula, what makes a result actionable rather than noise? |
| Brady | Which authority states must be visible to you during review, and which should be hidden from public readers until resolved? |
| Brady | What is the smallest useful comparison report between Stephanos entities and your current ToposText/Dropbox HTML? |
| Amelia / future helpers | What would you need to safely answer one targeted Greek/place question without learning the whole system? |

## Remaining Transcript Work

This pass covered the obvious Stephanos transcript set plus a wider keyword search over local Downloads. It did not manually read every unrelated transcript in Downloads. The next transcript pass should:

1. File the unfiled March 26 transcript and the distinct unfiled personal-room transcript if they are project records.
2. Build a source register with date, participants, canonical path, duplicate hashes, and derived artifact links.
3. Code each task mention with user, object, pain point, current workaround, desired outcome, and page/workspace affected.
4. Count task frequency across transcripts after the coding scheme is stable.
5. Feed only the high-frequency and high-risk tasks into wireframes; keep low-frequency research ideas in the Analysis backlog.
