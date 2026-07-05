# Stephanos — Publish / Deploy / CGI / Feeds

Publish target: `stephanos@merah.cassia.ifost.org.au` (OpenBSD, httpd chroot
`/var/www`), vhost site `https://stephanos.symmachus.org`. Transport is
SSH/rsync throughout. The pipeline runs on the mac and/or `stephanos@raksasa`.

**Important layout fact (verified live):** the vhost document root is
`/vhosts/stephanos.symmachus.org/htdocs`. The `db/`, `cgi-bin/`, and `public-cgi/`
directories are **siblings of `htdocs`, outside the document root** — so the
review SQLite databases and the `.openai.stephanos.key` in `db/` are **not**
web-served (live `curl` of `/db/*` returns 404). `db/` must never be moved under
`htdocs`. See `ANOMALIES.md` S-03.

## A. Static site generation → `reference_site/` → `htdocs/`
All generators write into the gitignored `reference_site/` tree, deployed as one
rsync unit. Main generators: `generate_reference_site.py` (index + entry pages,
publish-gated via `canonical_variants.resolve_variant`), `generate_pipeline_progress.py`
(`pipeline.html`), `generate_statistics_site.py`, `generate_word_lemma_indexes.py`,
`generate_protected_pages.py` (behind htpasswd `/protected/*`), ~15 analysis
pages (`generate_translation_prompt_evaluation.py`, `..._quality_predictor_page.py`,
`generate_fingerprinting_page.py`, `generate_places_map.py`, entity/sources/works
pages…), `generate_pdf_book.py` (XeLaTeX → PDF), `generate_downloads_page.py`.

## B. Data exports → `exports/` → `htdocs/`
`generate_csv_export.py` (`lemmas.csv`), `export_proper_nouns_csv.py`,
`export_etymologies_csv.py`, `export_source_citation_csv.py`,
`export_for_nodegoat.py` (→ public `htdocs/nodegoat/*.csv`).

## C. Review-interface databases → vhost `db/` (outside docroot)
`export_for_review.py → review_data.sqlite` (full snapshot: **all** lemmas +
variants + Greek), `export_guidance_scan_db.py → guidance_scan_results.db`.
Protected by being outside `htdocs` (verified), not merely by an httpd rule.

## D. Review CGI (Go) → `cgi-bin/` + `public-cgi/`
`review_cgi/deploy_review_cgi.sh` rsyncs `*.go` to merah, builds static binaries,
installs to `cgi-bin/` (`review.cgi`, `entities.cgi`, `guidance.cgi`,
`final_review.cgi`, `canonical_translation.cgi`, `save.cgi`, `status.cgi`, …),
htpasswd-protected (`/cgi-bin/*` → 401 verified). It **also** installs
`canonical_translation.cgi` to `public-cgi/` — **unauthenticated and reachable**
(verified: 400 on bad input vs 401 for `cgi-bin/`), with weaker gating than the
reference site. See `ANOMALIES.md` S-04.

## E. Feeds
- **`ai-systems` status**: `generate_ai_systems_feed.py` → `reference_site/ai-systems.xml`
  + `.json` (from PG progress stats + schema-drift report). Also emitted by the
  EXIT trap on failure.
- **nodegoat bidirectional sync**: `sync_nodegoat.py --push --catch-up` (daily +
  hourly) pushes Greek/translations to the Uppsala nodegoat API (Bearer token in
  gitignored `stephanos.ini`). Distinct from the nodegoat **CSV** export.
- **ToposText**: separate `flock`-guarded pipeline; rsyncs reports to `htdocs/`.

## F. Backups
`pg_dump | gzip → backups/stephanos_DATE.sql.gz` (local, 7-day prune). Review DB
backed up on merah via `backup_review_db.sh`. The "Stop publishing dumps" change
removed the public dump upload from `run_daily_pipeline.sh`; the legacy
`setup_cron.sh` still contained it (now neutered — S-01) and the datadumps
directory on merah is **empty** (verified).

## Secrets
OpenAI key `~/.openai.stephanos.key` (raksasa) / `db/.openai.stephanos.key`
(merah, outside docroot); nodegoat token `stephanos.ini`; PG via `~/.pgpass`;
htpasswd (three drifting path references — S-05).
