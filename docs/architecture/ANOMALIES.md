# Stephanos — Consolidated Anomalies / Bug List

Merged and de-duplicated across the four architecture reads (job graph, data
model, ingestion, deploy). **Status** reflects live verification against merah
where done. Nothing here has been auto-fixed except the items marked
**FIXED (this branch)**; the riskier items are left as TODO for a follow-up PR.

Severity: **HIGH** (data loss, correctness, or exposure) · **MED** · **LOW/INFO**.

## Top issues (ranked)

| ID | Sev | Issue | Location | Status |
| --- | --- | --- | --- | --- |
| C-01 | HIGH | `assemble_lemmas.py --rebuild` runs unconditional `DELETE FROM assembled_lemmas`, wiping human columns (`human_greek_text`, `corrected_english_translation`, …) and CASCADE-deleting all `translation_runs`/history. No prompt/backup. | `assemble_lemmas.py:761` | **TODO** (needs a confirmation/backup guard) |
| C-02 | HIGH | `translate_lemmas` `run_index` collision: `completed_run_count` excludes `failed`, but the UNIQUE `(request_id, run_index)` counts it; re-activating a failed request reuses a taken index → unique violation, and the `except` inserts another failed row at the same index → unhandled worker crash. | `translate_lemmas.py:1895/1956/1258`, schema `:7429` | **TODO** |
| D-01 | HIGH | `translation_guidance_backlog_items` is read (`export_for_review.py`, `generate_translation_guidance_page.py`) but has **no writer anywhere** → readers always see empty; feature half-landed. | schema `:8358` + readers | **TODO** |
| C-05 | HIGH | `public_eligible` fail-open + multi-run unreliability: defaults `COALESCE(...,TRUE)`, and `lookup_public_block` runs only when `requested_runs==1`, so a multi-run request over a non-public (Billerbeck) source stores `public_eligible=TRUE` while `status='hidden'`. Any consumer trusting the boolean could leak copyright-restricted text. | `translate_lemmas.py:984/1494`, `translation_run_utils.py:18` | **TODO** |
| D-04 | HIGH | NULL `entry_number` defeats the dedupe UNIQUE `(source_image_ids, entry_number, version)` (NULLs distinct in Postgres) → the Meineke-only cohort can hold unlimited duplicate rows. Root cause of the `DATABASE_ISSUES.md` duplicate explosion. New contamination is now blocked at `assemble_lemmas.py:341/390`, but old rows persist and no constraint prevents recurrence via other paths. | schema `:4926/32/34` | **TODO** |
| C-06 | MED | OCR 50-headword allow-list forces a wrong headword: hard "MUST choose from the allowed list" with no "none-of-these" escape; if the prior page was misread or an entry falls outside the +50 window, the model is compelled to mis-assign. Assumes `images.id` order == page order. | `process_image.py:337/464/741` | **TODO** |
| C-08 | MED | `batch_process.py` OpenAI default model is the Gemini string `gemini-3.0-flash`, so `--provider openai` with no `--model` sends an invalid model name. | `batch_process.py:34/111` | **TODO** |
| C-03 | MED | In-place prompt-text overwrite breaks provenance: `seed_claude_translation_profiles.py` and `activate_legacy_scholarly_v3_prompt.py` `DO UPDATE SET prompt_text=…`; Claude imports/legacy backfills reference the prompt only by `profile_version_id` (no embedded text), so re-seeding silently rewrites the prompt historical runs are attributed to. | `seed_claude_translation_profiles.py:156`, `activate_legacy_scholarly_v3_prompt.py:113` | **TODO** |
| C-09 | MED | `link_wikidata_places.py --relink` overwrites `assembled_lemmas` geocoding with no human-authority guard (unlike `link_wikidata.py`), so a relink can clobber a manually verified place link. | `link_wikidata_places.py:549` | **TODO** |
| S-04 | MED | Public unauthenticated `public-cgi/canonical_translation.cgi` has weaker gating (omits `public_eligible`/`guidance_freshness`) than the reference site and the Python `public_cgi` variant. | `review_cgi/canonical_translation.go:122`, `deploy_review_cgi.sh:67` | **CONFIRMED LIVE** (400 unauth vs 401 for `cgi-bin/`); fix = align gating (TODO) |
| C-04 | MED | Provenance gaps: `backfill_legacy_translation_runs.py` inserts runs with no `request_payload_json` and an *assumed* model; `translate_billerbeck_german.py` stores no prompt version/payload. | resp. scripts | **TODO** |
| C-07 | MED | Model-version drift: docs say "Gemini 3.0 Flash / gpt-5.5 / responses API" but code defaults to `gemini-3-flash-preview` / `gpt-5.1` / `chat.completions`; disambiguation split `gpt-5.4-mini` vs `gpt-4o-mini`. | `process_image.py:26`, `CLAUDE.md`/`AGENTS.md` | **TODO** |

## Pipeline / orchestration (job graph)

| ID | Sev | Issue | Status |
| --- | --- | --- | --- |
| P-01 | HIGH | Two divergent orchestration definitions — `setup_cron.sh` installs a granular path that never calls `run_daily_pipeline.sh` (no schema preflight, no guidance/nodegoat/topostext, different backup + `--delete` deploy). | **FIXED (this branch)**: `setup_cron.sh` now refuses to run and points at `run_daily_pipeline.sh` |
| P-02 | HIGH | No `flock` single-instance lock on `run_daily_pipeline.sh`; Step 5 batch-wait timeout defaults to `0` (infinite) → overlapping cron runs collide (concurrent `git pull`, DB writes, deploy). | **TODO** — snippet in `run_daily_pipeline-hardening.md` (deferred: file carries user WIP) |
| P-03 | HIGH | Unguarded stages abort the whole run and skip Step 9 deploy **and** Step 10 backup — one transient OpenAI/DB error = no site deploy and **no DB backup that day**. | **TODO** — snippet in hardening doc (run backup from EXIT trap) |
| P-04 | MED | Swallowed failures on data-integrity stages (nodegoat push, canonical authority refresh, guidance freshness) let partial/stale data deploy with only a warning line. | TODO |
| P-05 | MED | Step 0 skips `git pull` whenever the tree is dirty — **currently dirty**, so scheduled runs silently stop self-updating. | **partial FIX (this branch)**: hardening snippet makes the skip emit a visible WARNING (deferred edit — file carries WIP) |
| P-06 | MED | Schema preflight is a hard abort-gate but the pipeline never applies migrations (`apply_migrations.sh` manual-only). | TODO |
| P-07 | LOW | Non-monotonic step labels vs execution order (5r before 5, 4e2 after 5). | doc'd in `JOBS.md` |

## Deploy / exposure (with live verification)

| ID | Sev | Issue | Status |
| --- | --- | --- | --- |
| S-01 | ~~HIGH~~→LATENT | Legacy `setup_cron.sh:38` rsynced the full PG dump to a **public** docroot (`datadumps.ifost.org.au/htdocs/stephanos/`). | **NOT LIVE** (datadumps dir empty on merah) + **FIXED (this branch)**: line removed and `setup_cron.sh` neutered |
| S-02 | ~~HIGH~~→LATENT | `setup_cron.sh:29` `rsync -avz --delete` can wipe separately-deployed `htdocs/` content (CSVs, nodegoat/, PDF). Daily path uses no `--delete` (safe). | **NOT LIVE** + **FIXED (this branch)**: `--delete` removed from the neutered legacy file |
| S-03 | ~~HIGH~~→INFO | Claim that only an httpd `/db/*` block protects the OpenAI key + review SQLite DBs. | **FALSE / NOT EXPOSED**: `db/` is a sibling of `htdocs`, outside the docroot; live `curl` of `/db/.openai.stephanos.key`, `/db/reviews.db`, `/db/review_data.sqlite` all 404. Keep `db/` outside `htdocs`. |
| S-05 | MED | htpasswd path drift across 3 files; `setup_reviewers.sh` written for RedHat/Apache, not OpenBSD httpd → reviewer file may not match the auth directive. | TODO |
| S-06 | MED | `export_for_nodegoat.py` public CSV bulk-publishes Greek + canonical translation; gating only as strong as `select_pointer_variant` (a Billerbeck pointer would expose restricted Greek as a scrapable CSV). | TODO |
| S-07 | LOW | `.secrets/review_bot_password.txt` was mode 0644 (world-readable on the workstation). | **FIXED (this branch)**: chmod 600 (perms only; file is gitignored) |
| P-08 | MED | Divergent deploy semantics / unverified deploys — `run_optional_rsync_logged` + `|| echo` let deploy/backup fail while the `ai-systems` feed still reports `ok`; no post-deploy HTTP/checksum check. | TODO |

## Data model (schema hygiene)

| ID | Sev | Issue | Status |
| --- | --- | --- | --- |
| D-02 | MED | Missing FKs on `assembled_lemmas.translation_prompt_version → translation_prompts.version` and `translation_risk_flags.evidence_difference_id`; several polymorphic pointers cannot have FKs (invariant risk). | TODO |
| D-03 | MED | Duplicate/overlapping models: legacy vs normalized translation storage (both live), diff layers, prompt storage, place resolution, `source_image_ids` vs `lemma_images`. | doc'd in `DATA_MODEL.md` |
| D-05 | MED | Dead sinks: `oracle_references`, `entity_change_events`, the 9-table `sentence_grammar_*` subsystem, and rarity analytics are written but have no static reader. | TODO |
| D-06 | LOW | Orphaned column `assembled_lemmas.corrected_greek_scan` (no writer); `images.lemma_json` stores two incompatible OCR shapes in one TEXT column. | TODO |
| D-07 | LOW | `status='blocked'` is counted/filtered in code but not permitted by `translation_runs_status_check` → such a row can never exist. | TODO |

## Ingestion robustness (lower severity)

C-10 (LOW) raw model output not logged on OCR/JSON failure; C-11 (LOW)
`process_meineke_pages.py` fail-fast halts the whole queue; C-12 (LOW) silent
truncation of prompt guidance/evidence context with no flag; C-13 (LOW) fragile
external-file idempotency keyed on absolute path + no retry on Dropbox fetch;
C-14 (LOW) assembly dedup keys on the deprecated `source_image_ids`.

## Positive controls worth preserving
OCR JSON-validate-before-mark keeps failed pages in-queue; `human_greek_text` /
`human_resolution_status` are consistently protected from machine overwrite;
`project_legacy_translation` won't clobber human/newer translations; the OpenAI
Batch layer is restart-safe (unique `custom_id`); ToposText intake is walled off
to staging tables; Claude import defaults `public_eligible=False` and refuses
silent overwrites; `db/` is outside the web docroot.
