# Stephanos — Jobs & Orchestration

Three orchestration definitions exist; **only one should be live**.

1. `run_daily_pipeline.sh` (~970 lines) — the current daily DAG. Run from the
   mac and/or `stephanos@raksasa`; driven by the external "Stephanos cron
   control" Codex automation (daily 22:15), which consumes the pipeline's
   cron-mail / `ai-systems` status feed. **This is the intended production path**
   (`CRON_SETUP.md`, `CLAUDE.md`, `AGENTS.md`).
2. `run_topostext_pipeline.sh` — a separate Brady/ToposText lane, timed after
   Brady's Greek workday, `flock`-guarded.
3. `setup_cron.sh` — a **legacy** granular crontab installer that never calls
   `run_daily_pipeline.sh`. It is deprecated and neutered on this branch (it
   contained the latent public-dump-upload and `rsync --delete` exposures — see
   `ANOMALIES.md` P-03/S-01/S-02). Do not install it.

Whole-body `set -e` + `set -o pipefail` are active in `run_daily_pipeline.sh`, so
**a stage aborts the run unless it ends in `|| echo "Warning…"`**. An `EXIT` trap
(`pipeline_exit_report`) emits the `ai-systems` status feed + cron mail on a
non-zero exit, so failures are observable — but the run still stops at the
failing step, skipping deploy and backup (see `ANOMALIES.md` P-04).

## Daily pipeline (ordered)

Execution follows file position, not the step labels (5r runs before 5; 4e2
after 5) — a known maintenance trap. Guard column: **U** = unguarded (a failure
aborts the whole run), **G** = guarded (`|| echo`, failure swallowed).

| Step | Script | Inputs → Outputs | Guard |
| --- | --- | --- | --- |
| 0 | `git pull` | working tree → updated code (**skipped if tree dirty**) | G |
| 0a0/0a0b | `detect_footnotes.py`/`analyze_vocabulary_signatures.py --ensure-schema` | → schema | U |
| 0a | `dump_schema.sh` → `check_db_schema.py --fail-on-extra` | live PG → `tmp/schema_preflight/*`; **hard gate** (`SCHEMA_PREFLIGHT=0` bypass) | U |
| 1/2/3 | (echo "Skipping") | retired EPUB ingest/image/OCR no-ops | — |
| 2a/2a1 | `fetch_topostext_html.py`/`import_topostext_intake.py` | Brady HTML → topostext staging (default **off**) | G |
| 2b/3b | `enqueue_meineke_holes.py`/`process_meineke_pages.py` | `pdf_pages_meineke/` → OCR JSON | U |
| 3c/3d | `enqueue/process_billerbeck_german_pdf_pages.py` | `pdf_pages_billerbeck_german/` → OCR | G |
| 4 | `assemble_lemmas.py` | OCR JSON (`images.lemma_json`) → `assembled_lemmas` (central input downstream) | U |
| 4b | `assemble_meineke_texts.py` | Meineke OCR → source text versions | U |
| 4d…4d3a | `seed_translation_*`, `backfill_legacy_translation_runs`, `mark_billerbeck_translation_runs_nonpublic` | seeds/compat → prompt profiles, runs | G |
| 4d5/4d6 | `sync_review_db.sh` / `import_reviews.py` | merah `reviews.db` → human corrections in PG (**closed loop**) | G / U |
| 4d6a…4e | guidance-freshness → scans → `enqueue_translation_runs.py` | guidance-first chain → run requests | G |
| 5r | `translate_lemmas.py --api-mode responses` | run requests → translations (runs before Step 5) | G |
| 5 | `translate_lemmas.py --batch` | run requests → `translation_runs` (**main translation; batch-wait timeout 0 = infinite**) | U |
| 5a/5b/5c… | `count_words`, `extract_proper_nouns`, `extract_etymologies`, `extract_aliases`, `generate_spelling_variants`, `analyze_meineke_differences`, `lemmatize_meineke_words` | `assembled_lemmas` → analytics tables | U |
| 5d/5d2 | `link_wikidata.py`, `link_wikidata_places.py` | proper nouns/places → Wikidata links, geocoding | U |
| 5l | `sync_nodegoat.py --push --catch-up` | PG → nodegoat REST (Uppsala) | G |
| 7…7c | ~25 `generate_*` site/page generators | PG → `reference_site/` HTML | mostly U |
| 8…8a5 | `generate_csv_export`, `export_*`, `export_for_nodegoat`, `generate_pdf_book`, `generate_downloads_page` | PG → `exports/`, PDF | U |
| 8a6 | `emit_ai_systems_status_report 0` | → `ai-systems.xml/.json` | — |
| 8b | `export_for_review.py`, `export_guidance_scan_db.py` | PG → `review_data.sqlite`, `guidance_scan_results.db` (feed review CGI) | U |
| 9 | `run_rsync`/ssh + `review_cgi/deploy_review_cgi.sh` | site + exports + review DBs → merah; rebuild Go CGIs (`rsync -az`, **no `--delete`**) | G/optional |
| 10 | `dump_postgres_backup` + merah `backup_review_db.sh` + `find backups -mtime +7 -delete` | PG → `backups/stephanos_$DATE.sql.gz` (7-day) | **U (pg backup); skipped if any prior step aborts**|

### ToposText lane (`run_topostext_pipeline.sh`)
`flock -n` single-instance. `git pull --ff-only` (skip if dirty) → fetch → import
intake → refresh canonical authority → generate 4 topostext pages → rsync to
merah → optional email. Sets `DB_HOST=raksasa`.

### Hourly nodegoat (`nodegoat_hourly_sync.sh`)
`sync_nodegoat.py --push --catch-up --limit 50 --batch-size 50`. **No lock.**

### Out-of-band (not called by any orchestrator)
`apply_migrations.sh` (schema migrations — **manual only**, though Step 0a's
preflight *aborts* the run on any drift), `dump_schema.sh`.
