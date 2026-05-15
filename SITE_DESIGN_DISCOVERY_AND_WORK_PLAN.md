# Stephanos Site Design Discovery and Work Plan

Date: 2026-05-15

Status: design-planning brief. This is not an implementation patch.

## Purpose

Action item 12 from the 2026-05-14 Stephanos meeting says to keep a UI polish pass on the horizon before treating Stephanos as a public example of AI-assisted research infrastructure. The comparison with ToposText was not just about data: Greta explicitly called out the value of a polished, designed scholarly interface.

This document assembles the material a designer would want before redesigning the Stephanos web experience, then lays out the design work plan step by step.

## Sources Assembled

Local project sources:

- `WEBSITE_STRUCTURE.md`: older map of generated public pages.
- `run_daily_pipeline.sh`: current generation and deployment order.
- `generate_reference_site.py`: main public reference-site generator and its global navigation.
- `generate_statistics_site.py`: statistics subsite generator.
- `generate_protected_pages.py`: scan/protected-page generator.
- `generate_translation_guidance_page.py`: public read-only guidance page.
- `review_cgi/templates.go`, `review_cgi/guidance.go`, `review_cgi/final_review.go`: protected review/editorial interfaces.
- `reference_site/`: current generated output present in the checkout.
- `progress.html`: generated progress page present at repo root.

Private meeting and ToposText sources:

- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-14-meeting/action-items.md`.
- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-14-meeting/sources/2026-05-14-zoom-transcript.txt`.
- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-14-meeting/sources/brady-email-topostext-2026-05-14.txt`.
- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-14-meeting/specs/entity-resolution-topostext-spec.md`.
- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-07-meeting/action-items.md`.
- `/Users/gregb/Documents/devel/papers/stephanos/2026-05-07-meeting/sources/2026-05-07-zoom-transcript.txt`.

External reference sources:

- ToposText public site: `https://topostext.org/`.
- ToposText Stephanos work page: `https://topostext.org/work/241`.
- ToposText project/text/map pages inspected on 2026-05-15.

## Current Product Shape

Stephanos is not one website in the product sense. It is a set of generated public pages, generated operational pages, protected scan pages, protected CGI review tools, CSV/PDF exports, and research analytics. These are all useful, but they grew from pipeline needs and meeting-driven features rather than from one user-facing information architecture.

Current local generated output contains:

- 6,322 HTML files under `reference_site/`.
- 3,576 headword pages.
- 1,732 protected scan/image wrapper pages.
- 890 author detail pages.
- 31 statistics image HTML wrappers.
- 29 top-level or special pages.
- 24 letter pages.
- 15 translation-prompt detail pages.
- 14 statistics detail pages.
- 11 protected report/index pages.

The main site navigation currently exposes a long mixed list:

- Ancient Sources
- Works Cited
- Word Index
- Lemma Index
- FGrHist Index
- People & Deities
- Ethnic Groups
- Aliases
- Places Map
- Translation Prompts
- Statistics
- Meineke vs Billerbeck
- Difference Analysis
- Clustering
- Entity Review
- Brady Review
- Processing Progress
- Pipeline Status
- Page Scans
- Human Review
- Downloads
- PDF Book

The protected CGI tools have their own navigation model:

- Translation review
- Entity resolution
- Translation guidance
- Rule impacts
- Final workspace

The statistics pages use a third navigation model, and the generated protected pages use another. Most generators carry their own inline CSS and page shells. That explains the inconsistency: there is no single site shell, no explicit hierarchy, and no shared decision about which tools are public reading surfaces, editorial workspaces, analytics, or operational diagnostics.

## Users and Jobs

The design work should start with jobs-to-be-done, because the page inventory is too large to organize by generator name.

### Greta

Primary job: review and improve translations enough for scholarly publication.

Evidence:

- Wants a polished interface, and pointed to ToposText as a beautiful digital-humanities product.
- Wants to review Kappa entries without bouncing back to the public site.
- Wants an entry selector for the current letter, ideally showing AI/human translation status.
- Wants final-review ordering to make sense by entry number/headword, with accent handling fixed if headword sorting is used.
- Wants timestamp sorts for final human translation and latest AI translation.

Design implication:

- The review workspace is not a page-by-page technical form. It is a workbench for progressing through a known slice of the corpus, seeing status, moving quickly, and comparing current AI and human text.

### Gabriel

Primary job: select, compare, and review the next translation batch.

Evidence:

- Manually checked which Kappa entries had AI and/or human translations while selecting the next batch.
- Wants a landing workspace from which reviewers can choose entries and jump into detailed review.
- Needs current V3/Meineke outputs to be clearly separated from stale V1/Billerbeck-era outputs.

Design implication:

- Batch selection needs visible status flags, version/provenance labels, and sorting/filtering by review state.

### Brady

Primary job: curate named entities and authority links across Stephanos, especially places.

Evidence:

- Wants to know where to start and what needs review.
- Wants all named entities, quoted authors, and identifiable works linked where possible.
- Is hand-tagging a ToposText HTML source that changes daily or weekly.
- Public ToposText lags the working Dropbox HTML by months, so the Stephanos comparison should use the Dropbox HTML, not just public ToposText.
- Needs comparison reports: entities Stephanos found but Brady missed, and disagreements between Brady's tags and AI/Wikidata choices.

Design implication:

- Entity review should be entity-centred, not headword-centred. The interface should answer "what does this ID link to across Stephanos?" and "which decisions need my attention?"

### Public Scholarly Reader

Primary job: browse, search, cite, and understand entries.

Evidence:

- The May 7 meeting framed the site as a database/search/browsing resource, not primarily a literary reading site.
- Public pages now include headwords, translations, sources, works, entities, aliases, maps, prompt versions, statistics, scans, and downloads.

Design implication:

- The public experience should foreground the text, translation, source/provenance, places/entities, and useful navigation between related entries. Operational controls should be visually and navigationally separate.

### Greg / Maintainer

Primary job: monitor the pipeline, verify generated outputs, debug live deployment, and inspect analytics.

Evidence:

- Pipeline progress, prompt-guidance status, statistics, protected scan pages, and deployment artifacts are all important.
- These pages currently sit beside public scholarly browsing pages.

Design implication:

- Operations needs a clear dashboard or admin/diagnostics area. It should not crowd the public reader's primary navigation.

## Current Pain Points

Information architecture:

- Public reading, review work, entity curation, analytics, exports, and pipeline diagnostics are mixed in one flat menu.
- Different generated pages expose different subsets of navigation.
- Some protected and operational pages are linked as if they were ordinary scholarly browsing pages.
- Important pages are hard to rediscover because names reflect implementation history rather than user tasks.

Workflow:

- Reviewers cannot easily stay within Kappa or another current work slice.
- Review pages do not yet provide a compact status-aware entry selector.
- Final-review sorting mixes entry-order, headword-order, accent-normalized order, and timestamp needs.
- Translation version/provenance must be highly visible because stale V1/Billerbeck-era output has caused confusion.

Visual system:

- Page shells, spacing, nav styling, typography, tables, status chips, and cards are inconsistent across generators.
- Statistics pages, public reference pages, progress pages, protected scan pages, and CGI pages look like separate products.
- The main index is useful but reads as a feature inventory rather than a designed scholarly entry point.

Content model:

- The site still exposes headword-centred structures in places where entity-centred structures are needed.
- ToposText/Brady material introduces temporary IDs, `zzz`, `YY`, `JJ`, ToposText IDs, Wikidata QIDs, Pleiades IDs, and RE identifiers; those states need readable labels and review flows.
- Public pages need to distinguish final/public text, AI draft text, human corrections, source text, prompt/guidance provenance, and operational diagnostics without overwhelming the reader.

## ToposText As Design Reference

ToposText should be used as a reference for product feel and scholarly task fit, not as a template to copy literally.

What ToposText appears to do well:

- It has a clear conceptual triad: places, texts, and people.
- It treats the map and the text as connected primary surfaces.
- Object pages feel purposeful: a place, work, or person is a stable node with relationships around it.
- Search and browsing are not buried; they are core affordances.
- The interface feels like a designed scholarly tool rather than a set of generated reports.
- Inline entity links are part of reading, not an afterthought.
- It separates rich content surfaces from underlying update/indexing machinery.

What not to inherit uncritically:

- Brady noted that ToposText's backend update process is not integrated enough: edited text must be re-indexed and uploaded through batch steps.
- The public ToposText Stephanos text can lag Brady's current working HTML by months.
- Stephanos has stronger AI provenance, review-state, and prompt/version needs than ToposText currently exposes.

The design target is therefore: keep the confidence, navigability, and object-centred scholarly feel of ToposText, while making Stephanos' AI/human/provenance workflows explicit and operationally trustworthy.

## Proposed Information Architecture

Use a small set of top-level areas. These labels are working names.

### Read

For public scholarly browsing.

- Text and translations by letter/headword.
- Search across headwords, Greek, English, sources, and entities.
- Entry pages.
- Places map.
- Sources, works, entities, peoples, aliases.
- PDF/book/downloads as secondary actions.

### Review

For translation review and final-human-workflow tasks.

- Translation review page.
- Final workspace.
- Letter/batch selector with AI/human/final status.
- Translation version and provenance history.
- Human notes and correction state.

### Entities

For entity curation.

- Entity resolution workspace.
- Place cluster review.
- Brady/ToposText comparison.
- ToposText snapshot diffs.
- Authority-link status across Wikidata, ToposText, Pleiades, Manto, RE, and placeholders.

### Guidance

For prompt/rule systems.

- Public read-only translation guidance.
- Protected guidance editor.
- Rule impacts.
- Guidance statistics.
- Prompt versions.

### Analysis

For research/statistical outputs.

- Word count.
- Translation length.
- Regression/emphasis.
- Etymology.
- Parisinus vs epitome.
- Pausanias/source statistics.
- Formula/gloss usage.

### Operations

For Greg and pipeline maintenance.

- Pipeline status.
- Processing progress.
- Scan/page diagnostics.
- Meineke/Billerbeck comparison and difference reports.
- Export status.
- Deployment/check freshness.

This structure would reduce the public top nav to perhaps five or six items, while keeping all current pages discoverable through section landing pages.

## Key Page-Level Design Briefs

### Public Entry Page

The entry page should become the canonical object page for a headword or entry.

Required content:

- Headword, entry number, source edition/source text state.
- Greek text and public English translation, with line/paragraph clarity.
- Translation state: final human, human-reviewed, AI draft, stale/outdated where relevant.
- Source citations and quoted authors/works.
- Places/entities with authority links.
- Related entries, aliases, homonyms, and same-place clusters.
- Scan/source provenance, but not as the dominant first impression.
- Links into protected review only for authenticated/editorial users.

### Letter / Batch Workspace

This should support Greta/Gabe's current Kappa workflow.

Required controls:

- Letter selector.
- Entry selector or compact table.
- Status columns: latest AI exists, human translation exists, final translation exists, guidance complete, stale/outdated flag.
- Sorts: entry number, latest AI translation time, final human translation time.
- Filters: needs AI, needs human, has stale AI, has final, no final.
- One-click jump to review and final workspace.

### Entity Curation Workspace

This should support Brady's "where do I start?" workflow.

Required controls:

- Canonical entity or authority-ID search.
- Review queue by problem type: missed by Brady, missed by AI, authority disagreement, temporary ID, `zzz` likely-place, `YY`, `JJ`, multi-place headword, source/work unresolved.
- Entity detail page showing all mentions across Stephanos.
- Side-by-side Stephanos/AI evidence vs Brady/ToposText tag evidence.
- Clear action states: accept, reject, split, merge, needs ToposText ID, no external ID found, not an entity.

### Section Landing Pages

Each top-level area needs a landing page that tells users what they can do without presenting every generated file.

Examples:

- Read: start with search, letters, map, sources, works.
- Review: current batch, Kappa status, recent AI translations, recent final translations.
- Entities: unresolved queues, ToposText diff summary, authority coverage.
- Analysis: curated research reports, not raw chart folders.
- Operations: generation freshness, pipeline stages, deployment state.

## What A Designer Would Assemble Next

1. Screenshot audit.

   Capture representative desktop and mobile screenshots for:

   - index page
   - letter page
   - headword page
   - review CGI entry
   - final workspace
   - entity resolution
   - guidance editor
   - translation guidance public page
   - statistics overview and one statistics detail page
   - progress/pipeline page
   - protected scan page
   - ToposText Stephanos work page
   - ToposText place and map pages

2. Page inventory and ownership map.

   For each generated page family, record:

   - generator script
   - output path
   - intended audience
   - current nav links
   - data dependency
   - public/protected status
   - freshness requirement
   - whether it belongs under Read, Review, Entities, Guidance, Analysis, or Operations.

3. Task inventory from transcripts.

   Extract user tasks from the May 7 and May 14 transcripts, especially:

   - translation review
   - Kappa batch selection
   - entity review
   - ToposText comparison
   - prompt/guidance review
   - public browsing/search
   - paper/statistics work

4. Lightweight user interviews.

   2026-05-15 scope update: skip this for now. The transcript record is enough for the next design pass.

   If email is enough, send short questions rather than broad "what do you want?" prompts.

   Greta:

   - When you sit down to review translations, what is the first page you want to see?
   - What makes ToposText feel beautiful or trustworthy to you: layout, typography, map/text connection, link behavior, visual restraint, speed, or something else?
   - Which information must be visible while deciding whether a translation is ready?
   - What slows you down most in the current review/final workspace flow?

   Gabriel:

   - How do you choose the next 20 entries to review?
   - Which status flags would remove manual checking?
   - What comparison view do you need for AI vs human vs previous versions?
   - Which sorts/filters do you use repeatedly?

   Brady:

   - What are the top three entity-review queues you would actually work through?
   - What would make a Brady/ToposText disagreement easy to judge?
   - Which temporary states need first-class labels: `zzz`, `YY`, `JJ`, QID, Pleiades, RE, ToposText ID?
   - Do you prefer reviewing by entity, by entry, by changed ToposText paragraph, or by problem type?

5. Competitive/comparator review.

   2026-05-15 scope update: skip this for now. There are not enough useful comparators for the Stephanos review/provenance workflow.

   Keep this focused:

   - ToposText for designed scholarly browsing and map/text connection.
   - Pleiades for place authority pages and citation/reference density.
   - Perseus/Scaife for source-text reading and passage addressing.
   - Current Stephanos for AI provenance and human-review workflow, where the comparators are weaker.

6. Content model sketch.

   Draw the object model the UI should teach:

   - entry/headword
   - source text version
   - translation run
   - human/final translation
   - source citation
   - entity mention
   - canonical entity
   - authority link
   - guidance rule
   - review action
   - pipeline/output artifact

7. Navigation model and site map.

   Produce a sitemap that groups pages by user task, not generator script.

8. Wireframes.

   Low-fidelity wireframes first:

   - public entry page
   - public search/browse page
   - review batch workspace
   - entity curation queue
   - analysis landing page
   - operations dashboard

9. Visual design system.

   Establish:

   - typography for Greek, English, metadata, tables, and dense review controls
   - color roles for public/final, AI draft, stale/outdated, human-reviewed, warning, operational
   - status chips
   - compact tables
   - breadcrumbs
   - section nav
   - form controls
   - side-by-side comparison blocks
   - provenance disclosures
   - responsive breakpoints

10. Prototype and test.

   Build clickable static prototypes for the most important flows before refactoring all generators.

## Step-By-Step Work Plan

### Phase 1: Discovery Pack

Deliverable: `SITE_DESIGN_DISCOVERY_AND_WORK_PLAN.md` plus screenshots and a current page inventory.

Steps:

1. Freeze the current generated page inventory.
2. Capture screenshots for representative pages.
3. Extract transcript-backed tasks from May 7 and May 14.
4. Summarize ToposText design patterns.
5. Identify audiences and top jobs.
6. Mark every page family as public reader, reviewer, entity curator, analyst, or maintainer.

Exit criteria:

- We can explain who each page is for.
- We can say which pages are public product surface and which are workbench/operations.
- We have enough evidence to sketch a new sitemap.

### Phase 2: Information Architecture

Deliverable: proposed sitemap and navigation matrix.

Steps:

1. Collapse the flat menu into the six working sections: Read, Review, Entities, Guidance, Analysis, Operations.
2. Assign each current generated page family to a section.
3. Define global navigation, section navigation, breadcrumbs, and contextual links.
4. Decide what authenticated-only links should look like on public pages.
5. Decide which old URLs must remain stable.

Exit criteria:

- No page family is orphaned.
- The public nav no longer exposes operational clutter.
- Review/entity workflows are reachable without going through public browse pages.

### Phase 3: Core User Flows

Deliverable: task-flow diagrams and low-fidelity wireframes.

Steps:

1. Public reader opens a headword, follows a place/source/entity, returns to related entries.
2. Greta reviews Kappa entries from a status-aware selector.
3. Gabriel selects a true V3 batch and sees provenance clearly.
4. Brady opens an entity problem queue and resolves a disagreement.
5. Greg checks whether the pipeline/deploy outputs are fresh.

Exit criteria:

- Each flow has a start page, primary action, secondary actions, and success state.
- Each flow avoids unnecessary returns to the public index.

### Phase 4: Visual Direction

Deliverable: visual design direction plus reusable components.

Steps:

1. Choose a restrained scholarly visual direction, using ToposText as a quality benchmark.
2. Define page density: public reading pages should breathe; review/admin pages should be compact and scannable.
3. Define typography and Greek text treatment.
4. Define status colors and labels for translation/provenance states.
5. Define tables, filters, tabs, cards, callouts, and comparison panels.
6. Produce desktop and mobile mockups for the public entry page and review batch workspace.

Exit criteria:

- The interface feels intentionally designed rather than assembled from independent reports.
- Dense workflows remain efficient.
- Status/provenance is readable without dominating the page.

### Phase 5: Prototype Review

Deliverable: clickable prototype or static HTML prototype.

Steps:

1. Prototype the public entry page.
2. Prototype the Kappa review workspace.
3. Prototype the entity curation queue.
4. Run short task-based reviews with Greta, Gabe, and Brady.
5. Record what they try to click, what they cannot find, and what labels confuse them.

Exit criteria:

- Greta can move through Kappa review without returning to public browse.
- Gabriel can identify the next review batch from visible status.
- Brady can find a useful entity-review starting point.
- A public reader can understand an entry page without needing pipeline context.

### Phase 6: Implementation Plan

Deliverable: engineering backlog with page/template ownership.

Recommended implementation order:

1. Create a shared site shell for generated public pages: header, nav, breadcrumbs, footer, CSS.
2. Create section landing pages for Read, Analysis, and Operations.
3. Reduce public top nav to the new information architecture.
4. Redesign the public entry/headword page.
5. Redesign letter pages and search results around browsing tasks.
6. Add the Kappa/current-letter selector and status table to review/final workspaces.
7. Add a shared protected/editorial shell for CGI pages.
8. Build the entity curation queue around ToposText/Brady comparison states.
9. Move operations pages behind an Operations landing page.
10. Consolidate statistics into an Analysis landing page with clear report descriptions.
11. Add visual regression screenshots for representative public and protected pages.
12. Only then polish secondary report pages.

Exit criteria:

- The current pages still generate and deploy through `run_daily_pipeline.sh`.
- Existing stable URLs either continue to work or redirect.
- The main public site, review workspaces, and operations pages share a coherent visual language.
- Reviewers can complete the Kappa workflow faster than in the current site.

## Immediate Engineering Risks

- Many pages are generated by separate scripts with inline CSS; a real redesign will need shared template helpers rather than copy-pasted style edits.
- `reference_site/` is generated and may not be committed, so screenshots and inventory should record build time/freshness.
- Local generation often needs `DB_HOST=raksasa DB_USER=stephanos`; do not treat a local static snapshot as proof of current live state.
- Public and protected URLs have existing external value. Keep redirects/backward compatibility in the plan.
- Entity redesign overlaps with the ToposText intake/canonical entity schema work; do not design a beautiful entity UI on top of a headword-centred model that is already known to be wrong.

## Success Criteria For The Redesign

- A first-time scholarly reader can identify what Stephanos offers within one screen.
- The public top navigation has a small number of meaningful sections.
- Headword pages present Greek, translation, sources, entities, and provenance in a stable order.
- Greta/Gabe can review a letter batch from inside the review workspace using status-aware navigation.
- Brady can work from an entity-centred queue rather than hunting through headwords.
- Prompt/guidance/provenance states are visible where they affect trust, and hidden where they only distract.
- Analytics and operations are discoverable without crowding the public reading path.
- The site can still be regenerated and deployed by the existing pipeline.
