# IMPROVEMENTS.md

*Analysis date: 2026-07-11*

Stephanos is a mature, active pipeline that turns Billerbeck's 2006 edition of Stephanos of Byzantium's *Ethnika* (scanned EPUB images) into a structured PostgreSQL dataset via vision-LLM extraction, then translates, entity-links (Wikidata/nodegoat/ToposText), analyzes, and publishes reference/statistics sites. It is healthy — uv-native (`pyproject.toml` + `uv.lock`), keys read from env/keyfiles (`api_keys.py`, no committed secrets), recent commits show ongoing prompt-evaluation work. The main risks are (a) ~200 scripts dumped flat in the repo root with no package structure, (b) a 16-file dirty working tree of uncommitted prompt/profile work, and (c) tests that are ad-hoc top-level files with no CI.

## Bugs & Fixes / Unfinished Work

- **Dirty working tree (16 modified files)**: `activate_legacy_scholarly_v3_prompt.py`, `seed_*_profiles.py`, `translate_lemmas.py`, `canonical_variants.py`, docs under `docs/architecture/`, etc. This looks like the in-flight "legacy scholarly v3" prompt rollout — finish, commit, and push it (owner convention: commit after every moderate chunk of work). Uncommitted seed/profile changes are especially dangerous because reruns on another machine will silently use stale prompts.
- **TODO.md open items**: whole-work PDF/book quality assessment, phrase-level footnotes + `Footnote this` workflow (see `FOOTNOTE_CAPABILITY_SPEC.md` — spec exists but implementation is pending), Billerbeck volume 5 index scan, Wikidata linking for gods/peoples, Mobbs (2020) affect-axis mapping of the length-bias vocabulary.
- **Operational footgun documented but not enforced**: TODO.md warns that on `udara` the DB is on `raksasa`, not localhost. Encode this in `db.py` / `stephanos.ini.example` (fail fast with a clear error if host resolves to localhost on udara) instead of relying on a TODO note.
- **Cruft in repo root**: `prompt-used-for-claude.md~` (editor backup), `pipeline.log`, `schema_drift_report.{json,md}`, `guidance_scan_results.db`, `review_data.sqlite`, `stephanos.db`, `meineke_only_merge_candidates.*.tsv`, `__pycache__/` — several of these are generated artifacts/databases that should be gitignored or moved to `output/`/`exports/`.

## Improvements

- **Repository structure**: ~200 top-level `.py` scripts make discovery nearly impossible. Move shared library code (`db.py`, `citation_format.py`, `translation_run_utils.py`, `canonical_translation_service.py`, `wikidata_entity_cache.py`, `model_pricing.py`, `site_navigation.py`, …) into a `stephanos/` package, and group scripts into `scripts/{extract,analyze,generate,migrate,sync}/`. Do it incrementally — start by packaging the library modules the scripts import.
- **Doc sprawl**: 30+ top-level `*_PLAN.md`/`*_DESIGN.md`/`*_STATUS.md` files, plus a `docs/` dir. Sweep completed plans (e.g. `DEPLOYMENT_COMPLETE.md`, finished cleanup plans) into `docs/archive/` and keep only living docs at root (README, CLAUDE/AGENTS, TODO).
- **Schema drift**: you already generate `schema_drift_report.md` — wire `dump_schema.sh` + drift check into the daily pipeline (`run_daily_pipeline.sh`) or CI so `stephanos_schema.sql`/`SCHEMA_BASELINE.md` can't silently diverge from raksasa.
- **Consolidate the three nodegoat sync scripts** (`sync_nodegoat.py`, `sync_to_nodegoat.py`, `sync_from_nodegoat.py`) behind `nodegoat_cli.py` subcommands; `NODEGOAT_STATUS.md` suggests this area has accreted.

## Testing

- Tests exist (`test_*.py`, ~13 files) but are top-level and there's no CI. Add a `tests/` directory, a GitHub Actions workflow running `uv run pytest` (mocking DB/OpenAI), and mark DB-dependent tests so they skip cleanly off-network.
- The highest-value untested surfaces: `db.py` config/host resolution, `translation_rendering.py` edge cases (already partially covered), and the migration scripts (`migrate_*.py`) — at minimum a dry-run smoke test against a scratch schema.

## Documentation

- README's install instructions say `uv add bs4` / `uv add openai` — stale now that `pyproject.toml`/`uv.lock` are committed; replace with `uv sync`.
- Add a top-level SCRIPT INDEX (one line per script, grouped by pipeline stage) — cheaper than restructuring and immediately useful; `SITE_PAGE_INVENTORY_AND_OWNERSHIP.md` shows you already do this for pages.

## Security

- No committed secrets found: `api_keys.py` correctly reads from env vars or `~/.openai.stephanos.key`. Good.
- Verify `stephanos.db`, `review_data.sqlite`, and `guidance_scan_results.db` (committed SQLite files) contain no API payloads or private reviewer data; prefer removing them from git history if they're regenerable.
- `public_cgi/` and `review_cgi/` deploy to merah — confirm the review CGIs enforce auth consistently (see `generate_protected_pages.py`) and that DB credentials aren't embedded in deployed CGI files.

## Housekeeping / Modernization

- Already on uv — good; keep running scripts via `uv run script.py` directly (no `requirements.txt` anywhere, as preferred).
- Add/extend `.gitignore` for `__pycache__/`, `*.log`, `*~`, generated `*.db`/`*.sqlite`, `schema_drift_report.*`, `tmp/`, `output/`, `exports/`.
- Add `ruff` (lint + format) via `uv add --dev ruff`; with this many scripts, dead-import and unused-variable detection will pay off fast.

## Quick Wins

1. Commit or stash the 16 dirty files (the v3 prompt work) and push.
2. `git rm --cached prompt-used-for-claude.md~ pipeline.log schema_drift_report.*` and gitignore them.
3. Fix README install section (`uv sync`).
4. Move `test_*.py` into `tests/` and add a minimal CI workflow.
5. Archive completed `*_PLAN.md` docs into `docs/archive/`.
