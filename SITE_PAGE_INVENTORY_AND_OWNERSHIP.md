# Stephanos Page Inventory and Ownership Map

Date: 2026-05-15

Status: design discovery artifact. This is an ownership and information-architecture map, not an implementation patch.

## Scope

This inventory is based on the current checkout and generated files under `reference_site/`, `progress.html`, `exports/`, `review_cgi/`, `public_cgi/`, and the generation/deployment order in `run_daily_pipeline.sh`. I did not regenerate the site for this inventory.

The useful unit is a page family, not each individual generated page. The current local snapshot contains 6,324 generated HTML files under `reference_site/`:

| Count | Page family |
| ---: | --- |
| 3,576 | headword pages |
| 1,732 | protected image/scan pages |
| 890 | author/source detail pages |
| 33 | statistics image wrapper pages |
| 30 | top-level or special public pages |
| 24 | letter pages |
| 14 | statistics detail pages |
| 14 | prompt detail pages |
| 11 | protected report/index pages |

There are also 820 static search-data files under `reference_site/search-data/`, review/editorial CGI tools under `/cgi-bin/`, one public canonical-translation CGI endpoint under `/public-cgi/`, CSV/PDF/TEX exports, nodegoat exports, and ad hoc review/intake reports under `exports/`.

## Ownership Terms

No formal code-owner file exists in this repo. The ownership below is therefore practical stewardship:

- Product owner: the person or user class whose workflow should drive page design decisions.
- Engineering owner: the script, CGI module, or pipeline step that owns the generated output.
- Data owner: the data source that must be correct and fresh for the page to be trustworthy.
- IA area: the proposed top-level section from the design plan: Read, Review, Entities, Guidance, Analysis, or Operations.

## Navigation Models Found

The current site does not have one navigation model.

| Nav model | Where it appears | Current links or controls | Design issue |
| --- | --- | --- | --- |
| Public flat nav | `generate_reference_site.py` public pages | Ancient Sources, Works Cited, Word Index, Lemma Index, FGrHist, People and Deities, Ethnic Groups, Aliases, Places Map, Translation Prompts, Statistics, Meineke/Billerbeck, Difference Analysis, Clustering, Entity Review, Brady Review, Processing Progress, Pipeline Status, Page Scans, Human Review, Downloads, PDF Book | Public, editorial, analysis, and operations links are mixed in one long menu. |
| Source/entity subnav | `sources.html`, `works.html`, `entities.html`, `peoples.html`, `aliases.html`, `fgrhist.html` | Sources, works, FGrHist, entities, peoples, aliases, statistics | Useful cluster, but it is not framed as one "reference objects" area. |
| Statistics nav | `statistics.html`, `statistics/*.html`, `statistics_images/*.html` | Word count, translation length, regression, etymology, Parisinus comparison, category pages, Pausanias, guidance rules | Analysis pages are independent of the public/reference shell. |
| Protected static nav | `reference_site/protected/*.html` | Page scans, human review, pipeline/status, Meineke reports, clustering, entity review | Operational diagnostics and editorial review reports sit beside scan evidence. |
| Review CGI nav | `/cgi-bin/review.cgi`, `/cgi-bin/entities.cgi` | Letter selector, previous/next, next unreviewed, entry selector, final workspace, entity resolution, guidance, rule impacts, public headword link | Closest to a real workflow, but still needs a stronger workspace landing page and status-aware batch controls. |
| Guidance CGI nav | `/cgi-bin/guidance.cgi`, `/cgi-bin/guidance_impacts.cgi`, `/cgi-bin/guidance_status.cgi` | Rule editor, rule impacts, urgent/background scan status | This is a protected rule-management workbench, not public reading content. |
| Endpoint/API nav | `/cgi-bin/save.cgi`, `/cgi-bin/status.cgi`, `/public-cgi/canonical_translation.cgi` | Form actions and JSON endpoints | Should be invisible except as supporting infrastructure. |

## Area Ownership Map

| IA area | Primary product owner | Supporting users | Engineering surface | Data/freshness owner | Design principle |
| --- | --- | --- | --- | --- | --- |
| Read | Public scholarly reader | Greta, Gabriel, Greg | `generate_reference_site.py`, source/work/entity/map/index generators, search assets | PostgreSQL assembled/source/entity tables; refreshed by daily pipeline | Make the public site feel like a coherent scholarly reference work. Hide operational clutter. |
| Review | Greta and Gabriel | Greg | `review_cgi/review.go`, `final_review.go`, `save.go`, `export_for_review.py`, review packets | `review_data.json`, `reviews.db`, human/final translation tables; must be current during review sessions | Treat this as a workbench for moving through a batch, not as isolated forms. |
| Entities | Brady | Greg, public readers secondarily | `review_cgi/entities.go`, entity/static report generators, map/aliases, ToposText intake scripts | `proper_nouns`, `place_clusters`, `brady_entity_tags`, authority IDs, nodegoat exports | Make review entity-centred and queue-driven. Headwords are evidence, not the organizing object. |
| Guidance | Greg | Greta and Gabriel | `generate_translation_guidance_page.py`, `review_cgi/guidance.go`, `guidance_impacts.go`, scan worker/status modules | Translation guidance tables, scan DB, prompt versions; must update when rules or scans change | Separate public explanation from protected rule editing and impact triage. |
| Analysis | Greg and paper authors | Greta, Gabriel | `generate_statistics_site.py`, Pausanias/source/statistical report generators | Derived analysis tables and exports; daily or analysis-run freshness | Curate analysis as reports with purpose, not a dump of chart files. |
| Operations | Greg | Future maintainers | `generate_progress_site.py`, `generate_pipeline_progress.py`, protected scan/report pages, deployment scripts | Pipeline state, OCR/images, logs, generated outputs, backup/deploy state | Give maintenance pages their own dashboard and keep them out of public browse paths. |

## Page Family Inventory

| Page family | Example paths/routes | Generator or owner module | Current status | Product owner | Data dependencies | Current nav model | Freshness need | IA area | Design disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Public home / reference index | `reference_site/index.html` | `generate_reference_site.py` | Public | Public reader; Greg | `assembled_lemmas`, translation/review status, source/entity counts | Public flat nav | Daily after translation/import | Read | Replace feature inventory with designed entry point: search, browse by letter, map, sources, downloads. |
| Letter browse pages | `reference_site/letter_kappa.html` and 23 others | `generate_reference_site.py` | Public | Public reader; Greta/Gabriel secondarily | `assembled_lemmas`, entry order, translation/review status | Public flat nav | Daily; also after review import | Read, with Review links | Keep as public browse pages; create separate batch selector for review needs. |
| Headword/entry pages | `reference_site/headword_2054.html`; 3,576 pages | `generate_reference_site.py` | Public | Public reader | Greek/source text, public translation, human/final status, source citations, entities, prompt/provenance, scan links | Public flat nav plus contextual links | Daily; must reflect reviewed/final text promptly | Read | Make canonical object page. Order content as headword, Greek, translation, sources, entities, provenance. |
| Search UI and search data | `reference_site/search-ui.js`, `reference_site/search-data/**` | `generate_reference_site.py`, `generate_word_lemma_indexes.py` | Public supporting asset | Public reader | Headwords, Greek/English tokens, search shards | Embedded in public pages | Daily after content changes | Read | Treat as core affordance in Read landing/header. |
| Word and lemma indexes | `word_index.html`, `lemma_index.html` | `generate_word_lemma_indexes.py` | Public | Public reader; analyst secondarily | Tokenized Greek/lemma documents | Source/entity subnav | Daily after text changes | Read, Analysis secondary | Keep discoverable, but subordinate to search and browse. |
| Sources, works, FGrHist, author detail pages | `sources.html`, `works.html`, `fgrhist.html`, `author_*.html` | `generate_sources_page.py`, `generate_works_page.py`, `generate_fgrhist_page.py` | Public | Public reader | `source_citation_units`, `lemma_source_citation_mentions`, source quote/passages, headword links | Source/entity subnav | Daily after source extraction/import | Read | Group as "Sources and Works" object area. Author detail pages need shared object-page shell. |
| People/deities and ethnic groups | `entities.html`, `peoples.html` | `generate_entities_page.py`, `generate_peoples_page.py` | Public | Public reader; Brady secondarily | `proper_nouns`, roles/classes, linked headwords, Wikidata labels | Source/entity subnav | Daily after entity extraction/review | Read, Entities secondary | Public object lists should be clean; entity-review states belong elsewhere. |
| Aliases | `aliases.html` | `generate_aliases_page.py` | Public/reference | Public reader; Brady | `proper_noun_aliases`, canonical entity rows | Source/entity subnav | Daily after entity corrections | Read, Entities secondary | Keep as reference aid; link it from entity pages rather than top nav. |
| Places map | `map.html`, `places_map.pdf` | `generate_places_map.py` | Public | Public reader; Brady | `place_clusters`, Wikidata/Pleiades/ToposText IDs, coordinates | Public flat nav | Daily after entity/place updates | Read, Entities secondary | Promote map/text connection as a core public surface, ToposText-style. |
| Translation prompt overview and prompt detail pages | `prompts.html`, `prompt_*.html`, `prompts/*.html` | `generate_reference_site.py` and legacy/generated prompt pages | Public but operational | Greg; Gabriel secondarily | `translation_prompt_profiles`, `translation_prompt_profile_versions`, prompt usage | Public flat nav | After prompt changes | Guidance | Move out of public top nav. Keep a read-only provenance path from relevant entries. |
| Public translation guidance page | `translation_guidance.html` | `generate_translation_guidance_page.py` | Public/read-only | Greg; reviewers | Translation guidance rules, rule status, examples, coverage | Public flat nav | After guidance rule or scan changes | Guidance | Keep public/read-only, but label as methodology/provenance rather than main reader destination. |
| Statistics landing and detail pages | `statistics.html`, `statistics/*.html`; 14 detail pages | `generate_statistics_site.py` | Public/analysis | Greg and paper authors | Derived word counts, translation length, regression, etymology, Pausanias, categories, guidance statistics | Statistics nav | Daily or on analysis refresh | Analysis | Replace raw report index with an Analysis landing page organized by research question. |
| Statistics image wrapper pages | `statistics_images/*.html`; 33 wrappers | `generate_statistics_site.py` | Public/analysis support | Greg and paper authors | Chart HTML/Plotly outputs and generated images | Statistics nav | Same as statistics generation | Analysis | Keep as deep links only; do not expose as primary nav. |
| Pipeline status | `pipeline.html`, `pipeline.json` | `generate_pipeline_progress.py` | Public now; operational | Greg | Batch jobs, OCR/translation/guidance pipeline state | Public flat nav | Daily pipeline; should show generation time | Operations | Move under Operations. Public readers should not see it in main nav. |
| Processing progress | `progress.html` at repo root and deployed root | `generate_progress_site.py` | Public now; operational/back-compat | Greg | OCR/translation/image processing counts and token usage | Linked from public flat nav | Daily pipeline | Operations | Keep URL for compatibility; present through Operations landing page. |
| Protected scan/image wrappers | `protected/image_849.html`; 1,732 pages | `generate_protected_pages.py` | Protected/static | Greg; reviewers secondarily | `images`, OCR JSON, `lemma_images`, assembled lemmas, source image files | Protected static nav | Daily after OCR/assembly | Operations, Review support | Treat as evidence/diagnostic pages. Link contextually from entry/review, not public top nav. |
| Protected scan index | `protected/index.html` | `generate_protected_pages.py` | Protected/static | Greg | Same as protected image pages | Protected static nav | Daily after OCR/assembly | Operations | Operations dashboard card, not a public page. |
| Meineke/Billerbeck comparison | `protected/meineke_comparison.html` | `generate_reference_site.py` | Protected/static | Greg; reviewers | Meineke/Billerbeck source text links, image/page coverage | Protected static nav | Daily after source-text changes | Operations, Review support | Keep as diagnostic evidence; surface specific diffs in review context. |
| Meineke difference and impact reports | `protected/meineke_difference_analysis.html`, `meineke_impact_*.html` | `generate_meineke_difference_analysis_page.py` | Protected/static | Greg; Gabriel | `meineke_text_differences`, source variants, translation impact classifications | Protected static nav | Daily after source-text/translation updates | Analysis, Review support | Make a curated Analysis/Review report, not a public nav item. |
| Meineke holes reports | `protected/meineke_holes_report.html`, JSON reports | `generate_meineke_holes_report.py` and related source-coverage scripts | Protected/static | Greg | Meineke headwords/source coverage queues | Protected static nav | Daily or source-import run | Operations | Operations diagnostic. |
| Translation risk report | `protected/translation_risk_report.html` | `generate_translation_risk_report.py` | Protected/static | Gabriel; Greg | Translation review/risk heuristics | Protected static nav | Daily after translation/review changes | Review, Analysis secondary | Convert to review queue or batch-selection input. |
| Headword clustering | `protected/clustering.html` | `generate_headword_clustering_page.py` | Protected/static | Greg; Gabriel | Embeddings, lemma distances, review URLs | Protected static nav | On embedding/analysis run | Analysis, Operations | Analysis tool; do not mix with core public browse. |
| Static entity resolution report | `protected/entity_resolution_review.html` | `generate_entity_resolution_review_page.py` | Protected/static | Brady; Greg | Human vs machine entity corrections, Wikidata labels | Protected static nav | Daily after entity review/import | Entities | Keep as report, but build primary entity workflow in CGI/entity queue. |
| Static Brady-vs-AI entity review report | `protected/brady_entity_review.html` | `generate_brady_entity_review_page.py` | Protected/static | Brady | `brady_entity_tags`, AI entity suggestions, Wikidata/ToposText/Pleiades/RE IDs | Protected static nav | Daily after ToposText/Brady import | Entities | Make this a queue summary and link into entity-centred review. |
| Translation review CGI | `/cgi-bin/review.cgi`, `/cgi-bin/save.cgi` | `review_cgi/review.go`, `save.go`, `templates.go` | Protected/authenticated CGI | Greta and Gabriel | `review_data.json`, `reviews.db`, source images, guidance hits, translation variants | Review CGI nav | Must be current during review; export before deploy | Review | Main review workbench. Needs landing/status table and clearer version/provenance hierarchy. |
| Final review workspace | `/cgi-bin/final_review.cgi` | `review_cgi/final_review.go` | Protected/authenticated CGI | Greta; Gabriel | `review_data.json`, `reviews.db`, human/final translation variants | Review CGI nav | Must be current during review | Review | Should be tied to letter/batch workflow with sort by entry, headword, latest AI time, final human time. |
| Entity resolution CGI | `/cgi-bin/entities.cgi` | `review_cgi/entities.go`, `save.go` | Protected/authenticated CGI | Brady | Place clusters, proper nouns, authority candidates, reviewer overrides | Review CGI nav | Must be current during entity review | Entities | Primary entity workbench until a richer entity-centred queue exists. |
| Guidance editor CGI | `/cgi-bin/guidance.cgi` | `review_cgi/guidance.go`, `guidance_common.go` | Protected/authenticated CGI | Greg | Translation guidance rules, examples, statuses, scan requests | Guidance CGI nav | Immediate after edits | Guidance | Protected rule-management workbench. Needs its own shell and links from rule impacts/review hits. |
| Guidance impacts and status CGI | `/cgi-bin/guidance_impacts.cgi`, `/cgi-bin/guidance_status.cgi` | `review_cgi/guidance_impacts.go`, `guidance_status.go`, urgent worker modules | Protected/authenticated CGI | Greg; reviewers affected | Guidance impact records, scan DB, urgent/background jobs | Guidance CGI nav | Near-live during scans | Guidance, Operations secondary | Keep protected; expose review-impact queues, not implementation details. |
| Review status endpoint | `/cgi-bin/status.cgi` | `review_cgi/status.go` | Protected/support endpoint | Greg | `review_data.json`, `reviews.db` | Endpoint/API | Near-live | Operations support | Supporting endpoint only. |
| Public canonical translation endpoint | `/public-cgi/canonical_translation.cgi` | `public_cgi/canonical_translation.cgi` | Public GET; authenticated/local POST expected | Greg; public entry pages | `review_data.json`, `reviews.db`, canonical action log | Endpoint/API | Near-live for review changes | Read support, Review support | Invisible API supporting canonical/final text selection. |
| Downloads page and public exports | `downloads.html`, `exports/lemmas.csv`, `proper_nouns.csv`, `etymologies.csv`, source-citation CSVs, `nodegoat/**` | `generate_downloads_page.py`, export scripts | Public/export | Greg; public data users | Export scripts and database snapshots | Public flat nav | Daily pipeline | Read, Operations secondary | Keep public, but make downloads a secondary action under Read/Data. |
| PDF/TEX book export | `stephanos_ethnika_translations.pdf`, `.tex` | `generate_pdf_book.py` | Public/export | Public reader; Greg | Assembled/public translations, formatting pipeline | Downloads/nav link | Daily or on explicit export run | Read | Treat as publication/export artifact. |
| Article review packets | `exports/article_review_packets/*.html`, `.pdf` | `generate_translation_review_packets.py` | Export/review artifact | Gabriel; Greta | AI/human/latest translation comparison data | Not part of public nav | On demand | Review | Keep as review deliverable; do not fold into public nav. |
| ToposText intake report | `exports/topostext_intake_report.html`, CSV/JSON sidecars | `generate_topostext_intake_report.py` | Export/ad hoc report | Brady; Greg | ToposText/Brady source snapshots, entity mentions, authority IDs | Not part of public nav | After ToposText source refresh | Entities | Important comparator input. Promote summary into entity dashboard once stable. |

## Ownership By Workflow

### Public Reading

Owned by the public scholarly reader's task, with Greg as site maintainer. Pages in scope:

- `index.html`
- `letter_*.html`
- `headword_*.html`
- `search-ui.js` and `search-data/**`
- `sources.html`, `works.html`, `fgrhist.html`, `author_*.html`
- `entities.html`, `peoples.html`, `aliases.html`
- `map.html`
- `downloads.html` and PDF/TEX/CSV exports

Design responsibility: make the product comprehensible, searchable, and citable. Operational pages should not appear in the public primary nav.

### Translation Review

Owned by Greta/Gabriel's review workflow. Pages and routes in scope:

- `/cgi-bin/review.cgi`
- `/cgi-bin/final_review.cgi`
- `/cgi-bin/save.cgi`
- `protected/translation_risk_report.html`
- `exports/article_review_packets/*`
- contextual links from `headword_*.html` and `letter_*.html`

Design responsibility: support batch selection, fast movement through a letter, visible AI/human/final status, and provenance clarity.

### Entity Curation

Owned by Brady's entity/authority workflow. Pages and routes in scope:

- `/cgi-bin/entities.cgi`
- `protected/entity_resolution_review.html`
- `protected/brady_entity_review.html`
- `entities.html`, `peoples.html`, `aliases.html`, `map.html`
- `exports/topostext_intake_report.*`
- nodegoat exports

Design responsibility: shift from headword-centred review to entity-centred queues, with clear authority-state labels for Wikidata, ToposText, Pleiades, Manto, RE, `zzz`, `YY`, and `JJ`.

### Translation Guidance

Owned by Greg's prompt/rule system, with Greta/Gabriel as downstream users. Pages and routes in scope:

- `translation_guidance.html`
- `prompts.html`, `prompt_*.html`, `prompts/*.html`
- `/cgi-bin/guidance.cgi`
- `/cgi-bin/guidance_impacts.cgi`
- `/cgi-bin/guidance_status.cgi`
- guidance-rule statistics under `statistics/`

Design responsibility: separate public methodology/provenance from protected rule editing, impact triage, and scan-job monitoring.

### Research Analysis

Owned by Greg/paper authors. Pages in scope:

- `statistics.html`
- `statistics/*.html`
- `statistics_images/*.html`
- `protected/meineke_difference_analysis.html`
- `protected/meineke_impact_*.html`
- `protected/clustering.html`

Design responsibility: group reports by research question and explain what a chart/report is for. Keep implementation diagnostics out of reader-facing nav.

### Operations And Evidence

Owned by Greg/maintainers. Pages and routes in scope:

- `pipeline.html`, `pipeline.json`
- `progress.html`
- `protected/index.html`
- `protected/image_*.html`
- `protected/meineke_comparison.html`
- `protected/meineke_holes_report.html` and JSON reports
- `/cgi-bin/status.cgi`
- deployment and backup outputs from `run_daily_pipeline.sh`

Design responsibility: make freshness, failures, source evidence, and deploy state easy to inspect without crowding public scholarly browsing.

## Immediate IA Moves

1. Public top nav should become: Read, Map, Sources, Entities, Analysis, Downloads. Review/Operations links can appear only for authenticated/editorial contexts.
2. Add section landing pages for Review, Entities, Guidance, Analysis, and Operations before redesigning every individual generated page.
3. Keep existing URLs stable, but change how users discover them.
4. Make `headword_*.html` the public object-page template and `/cgi-bin/review.cgi?id=*` the editorial object-page template.
5. Treat `protected/image_*.html` as evidence pages, not a product section.
6. Treat `statistics_images/*.html` as chart deep links, not pages a user should browse from the top level.
7. Fold ToposText/Brady intake results into the Entities landing page once the entity comparison workflow stabilizes.
8. Build shared public and protected shells before touching individual generator CSS.

## Open Ownership Questions

These need decisions before implementation:

- Who decides whether Translation Prompts and Translation Guidance are publicly prominent methodology pages or only provenance drill-downs from entries?
- Should public entity pages expose unresolved/temporary authority states, or should those states be protected-only until reviewed?
- Which review status is public-safe: AI draft, human initial, reviewed, final, stale, blocked?
- Should Operations require authentication everywhere, or is public pipeline transparency desirable?
- Are article review packets temporary exports, or should they become a persistent Review workspace view?
- Should ToposText intake reports remain exports, or become first-class protected entity queues?
