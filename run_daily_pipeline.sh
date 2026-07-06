#!/bin/bash
#
# Daily pipeline script for Stephanos processing
# Run this via cron to automate the entire workflow
#

set -e
set -o pipefail

# Change to project directory
cd "$(dirname "$0")"

# Log file
LOGFILE="pipeline.log"

# Single-instance lock: exit early if another daily pipeline run holds the lock.
# Guarded so manual runs on hosts without flock (e.g. macOS) still proceed.
LOCKFILE="${PIPELINE_LOCKFILE:-daily_pipeline.lock}"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        echo "Daily pipeline already running; exiting at $(date)" | tee -a "$LOGFILE"
        exit 0
    fi
fi

DATE=$(date +%Y%m%d)
STEPHANOS_SITE_URL="${STEPHANOS_SITE_URL:-https://stephanos.symmachus.org}"
AI_SYSTEMS_FEED_PATH="${AI_SYSTEMS_FEED_PATH:-reference_site/ai-systems.xml}"
AI_SYSTEMS_STATUS_PATH="${AI_SYSTEMS_STATUS_PATH:-reference_site/ai-systems.json}"
AI_SYSTEMS_STATUS_EMITTED=0
RSYNC_IO_TIMEOUT="${RSYNC_IO_TIMEOUT:-60}"
RSYNC_WALL_TIMEOUT="${RSYNC_WALL_TIMEOUT:-600}"
REVIEW_CGI_DEPLOY_TIMEOUT="${REVIEW_CGI_DEPLOY_TIMEOUT:-600}"

run_rsync() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$RSYNC_WALL_TIMEOUT" rsync -az --timeout="$RSYNC_IO_TIMEOUT" "$@"
  else
    rsync -az --timeout="$RSYNC_IO_TIMEOUT" "$@"
  fi
}

run_rsync_logged() {
  run_rsync "$@" 2>&1 | tee -a "$LOGFILE"
}

run_optional_rsync_logged() {
  local label="$1"
  shift

  if ! run_rsync "$@" 2>&1 | tee -a "$LOGFILE"; then
    echo "  Warning: $label rsync failed or timed out; continuing with later deploy/backup steps" | tee -a "$LOGFILE"
  fi
}

run_review_cgi_deploy_logged() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$REVIEW_CGI_DEPLOY_TIMEOUT" ./review_cgi/deploy_review_cgi.sh 2>&1 | tee -a "$LOGFILE"
  else
    ./review_cgi/deploy_review_cgi.sh 2>&1 | tee -a "$LOGFILE"
  fi
}

emit_ai_systems_status_report() {
  local exit_status="$1"
  local schema_report="${SCHEMA_REPORT_JSON:-tmp/schema_preflight/schema_drift_report.json}"

  uv run generate_ai_systems_feed.py \
    --output "$AI_SYSTEMS_FEED_PATH" \
    --json-output "$AI_SYSTEMS_STATUS_PATH" \
    --site-url "$STEPHANOS_SITE_URL" \
    --schema-report-file "$schema_report" \
    --pipeline-exit-status "$exit_status" \
    --status-report
}

pipeline_exit_report() {
  local exit_status="$?"
  if [ "$exit_status" -ne 0 ] && [ "$AI_SYSTEMS_STATUS_EMITTED" -eq 0 ]; then
    set +e
    echo "Step final: Generating short AI systems status after failure..." | tee -a "$LOGFILE"
    emit_ai_systems_status_report "$exit_status" 2>&1 | tee -a "$LOGFILE" || \
      echo "  Warning: Failed to generate AI systems status report" | tee -a "$LOGFILE"
  fi
  if [ "${DAILY_BACKUP_DONE:-0}" -eq 0 ]; then
    set +e
    echo "Step final: ensuring PostgreSQL backup ran (pipeline exited before Step 10)..." | tee -a "$LOGFILE"
    mkdir -p backups
    dump_postgres_backup "backups/stephanos_${DATE}.sql.gz" 2>&1 | tee -a "$LOGFILE" \
      || echo "  Warning: fallback PostgreSQL backup failed" | tee -a "$LOGFILE"
  fi
  exit "$exit_status"
}

trap pipeline_exit_report EXIT

find_pg_dump() {
  if command -v pg_dump >/dev/null 2>&1; then
    command -v pg_dump
    return 0
  fi

  local candidates=(
    "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump"
    "/Applications/Postgres/Contents/Versions/latest/bin/pg_dump"
    "/Applications/Postgres/bin/pg_dump"
  )

  local path
  for path in "${candidates[@]}"; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done

  shopt -s nullglob
  for path in /Applications/Postgres.app/Contents/Versions/*/bin/pg_dump /Applications/Postgres/Contents/Versions/*/bin/pg_dump /Applications/Postgres/*/bin/pg_dump; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done
  shopt -u nullglob

  return 1
}

dump_postgres_backup() {
  local output_file="$1"
  local db_name="${DB_NAME:-${PGDATABASE:-stephanos}}"
  local db_host="${DB_HOST:-${PGHOST:-}}"
  local db_port="${DB_PORT:-${PGPORT:-5432}}"
  local db_user="${DB_USER:-${PGUSER:-stephanos}}"
  local ssh_host="${SCHEMA_SSH_HOST:-stephanos@raksasa}"
  local pg_dump_bin
  local err_file

  pg_dump_bin="$(find_pg_dump || true)"
  err_file="$(mktemp)"
  trap 'rm -f "$err_file"' RETURN

  if [[ -n "$pg_dump_bin" ]]; then
    local cmd=("$pg_dump_bin")
    if [[ -n "$db_host" ]]; then
      cmd+=("-h" "$db_host")
    fi
    if [[ -n "$db_port" ]]; then
      cmd+=("-p" "$db_port")
    fi
    if [[ -n "$db_user" ]]; then
      cmd+=("-U" "$db_user")
    fi
    cmd+=("$db_name")

    if "${cmd[@]}" 2>"$err_file" | gzip > "$output_file"; then
      echo "  PostgreSQL backup written with: $pg_dump_bin" | tee -a "$LOGFILE"
      return 0
    fi

    if ! grep -q "server version mismatch" "$err_file"; then
      cat "$err_file" >&2
      return 1
    fi

    echo "  Local pg_dump version mismatch; falling back to remote pg_dump over SSH" | tee -a "$LOGFILE"
  else
    echo "  Local pg_dump not found; falling back to remote pg_dump over SSH" | tee -a "$LOGFILE"
  fi

  if [[ -z "$ssh_host" ]]; then
    echo "No SSH host configured for remote pg_dump fallback." >&2
    return 1
  fi

  local remote_cmd=(pg_dump)
  if [[ -n "$db_user" ]]; then
    remote_cmd+=("-U" "$db_user")
  fi
  remote_cmd+=("$db_name")

  local remote_cmd_escaped
  remote_cmd_escaped="$(printf '%q ' "${remote_cmd[@]}")"
  ssh "$ssh_host" "$remote_cmd_escaped" | gzip > "$output_file"
}

echo "========================================" | tee -a "$LOGFILE"
echo "Pipeline run: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# Step 0: Git pull to get latest instructions/code
echo "Step 0: Pulling latest changes from git..." | tee -a "$LOGFILE"
if git diff --quiet && git diff --cached --quiet; then
    git pull 2>&1 | tee -a "$LOGFILE" || echo "Git pull failed (continuing anyway)" | tee -a "$LOGFILE"
else
    echo "WARNING: git working tree is DIRTY; skipping git pull — the pipeline is" \
         "NOT self-updating. Commit or stash local changes to resume auto-update." \
         | tee -a "$LOGFILE"
    echo "  dirty paths:" | tee -a "$LOGFILE"
    git status --short | tee -a "$LOGFILE"
fi

# Step 0a0: Ensure low-priority AI footnote schema before strict preflight
echo "Step 0a0: Ensuring AI footnote schema..." | tee -a "$LOGFILE"
uv run detect_footnotes.py --ensure-schema --limit 0 2>&1 | tee -a "$LOGFILE"

# Step 0a0b: Ensure vocabulary signature schema before strict preflight
echo "Step 0a0b: Ensuring vocabulary signature schema..." | tee -a "$LOGFILE"
uv run analyze_vocabulary_signatures.py --ensure-schema-only 2>&1 | tee -a "$LOGFILE"

	# Step 0a: Schema preflight gate (strict by default)
	# Set SCHEMA_PREFLIGHT=0 to bypass in emergencies.
	SCHEMA_PREFLIGHT="${SCHEMA_PREFLIGHT:-1}"
	if [ "$SCHEMA_PREFLIGHT" -eq 1 ]; then
	    echo "Step 0a: Running schema preflight gate..." | tee -a "$LOGFILE"
	    if [ -z "${SCHEMA_DB_HOST:-}" ]; then
	        if [ -n "${DB_HOST:-}" ]; then
	            SCHEMA_DB_HOST="$DB_HOST"
	        elif [ -d /var/run/postgresql ]; then
	            # Prefer local socket auth on the DB host to avoid password prompts.
	            SCHEMA_DB_HOST="/var/run/postgresql"
	        elif [ -d /run/postgresql ]; then
	            SCHEMA_DB_HOST="/run/postgresql"
	        else
	            SCHEMA_DB_HOST="raksasa"
	        fi
	    fi
	    SCHEMA_DB_USER="${SCHEMA_DB_USER:-${DB_USER:-stephanos}}"
	    SCHEMA_DB_NAME="${SCHEMA_DB_NAME:-${DB_NAME:-stephanos}}"
	    SCHEMA_DB_PORT="${SCHEMA_DB_PORT:-${DB_PORT:-5432}}"
	    SCHEMA_SSH_HOST="${SCHEMA_SSH_HOST:-stephanos@raksasa}"
	    SCHEMA_PREFLIGHT_DIR="${SCHEMA_PREFLIGHT_DIR:-tmp/schema_preflight}"
	    SCHEMA_LIVE_SQL="${SCHEMA_PREFLIGHT_DIR}/stephanos_schema.live.sql"
	    SCHEMA_REPORT_MD="${SCHEMA_PREFLIGHT_DIR}/schema_drift_report.md"
	    SCHEMA_REPORT_JSON="${SCHEMA_PREFLIGHT_DIR}/schema_drift_report.json"
	    mkdir -p "$SCHEMA_PREFLIGHT_DIR"

    # Keep a live snapshot for audit/debugging each pipeline run.
    ./dump_schema.sh \
        --host "$SCHEMA_DB_HOST" \
        --port "$SCHEMA_DB_PORT" \
        --user "$SCHEMA_DB_USER" \
        --db-name "$SCHEMA_DB_NAME" \
        --output "$SCHEMA_LIVE_SQL" \
        --ssh-host "$SCHEMA_SSH_HOST" \
        2>&1 | tee -a "$LOGFILE"

    DB_HOST="$SCHEMA_DB_HOST" \
    DB_PORT="$SCHEMA_DB_PORT" \
    DB_NAME="$SCHEMA_DB_NAME" \
    DB_USER="$SCHEMA_DB_USER" \
    uv run check_db_schema.py \
        --schema-file "stephanos_schema.sql" \
        --report-file "$SCHEMA_REPORT_MD" \
        --json-report-file "$SCHEMA_REPORT_JSON" \
        --fail-on-extra \
        2>&1 | tee -a "$LOGFILE"
else
    echo "Step 0a: Schema preflight skipped (SCHEMA_PREFLIGHT=0)" | tee -a "$LOGFILE"
fi

# Step 1: Retire finished Billerbeck OCR ingestion steps
echo "Step 1: Skipping Billerbeck EPUB ingestion (OCR corpus complete)." | tee -a "$LOGFILE"

# Step 2: Retire finished Billerbeck image extraction steps
echo "Step 2: Skipping Billerbeck image extraction (OCR corpus complete)." | tee -a "$LOGFILE"

TOPOSTEXT_PAULY_WORKBOOK="${TOPOSTEXT_PAULY_WORKBOOK:-data/pauly/PaulyHeadwordstoWikidata from Margherita scrape.xlsx}"

# Step 2a: Fetch Brady's current ToposText HTML snapshot.
# The production cron path for this is run_topostext_pipeline.sh, timed for
# Brady's Greece workday. Set this to 1 only for manual full-pipeline runs.
TOPOSTEXT_HTML_FETCH="${TOPOSTEXT_HTML_FETCH:-0}"
if [ "$TOPOSTEXT_HTML_FETCH" -gt 0 ]; then
    echo "Step 2a: Fetching ToposText HTML snapshot..." | tee -a "$LOGFILE"
    uv run fetch_topostext_html.py --output-dir data/topostext_snapshots \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText HTML fetch failed" | tee -a "$LOGFILE"
fi

# Step 2a1: Import ToposText snapshot into review staging tables.
TOPOSTEXT_INTAKE_IMPORT="${TOPOSTEXT_INTAKE_IMPORT:-0}"
if [ "$TOPOSTEXT_INTAKE_IMPORT" -gt 0 ]; then
    echo "Step 2a1: Importing ToposText intake staging rows..." | tee -a "$LOGFILE"
    topostext_import_args=(uv run import_topostext_intake.py)
    if [ -f "$TOPOSTEXT_PAULY_WORKBOOK" ]; then
        topostext_import_args+=(--pauly-workbook "$TOPOSTEXT_PAULY_WORKBOOK")
    else
        echo "  Warning: PaulyHeadwords workbook not found at $TOPOSTEXT_PAULY_WORKBOOK; importing without RE enrichment" | tee -a "$LOGFILE"
    fi
    "${topostext_import_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText intake import failed" | tee -a "$LOGFILE"
fi

# Step 2b: Queue missing Meineke page scans based on headword hole detection
echo "Step 2b: Queueing missing Meineke hole pages..." | tee -a "$LOGFILE"
uv run enqueue_meineke_holes.py --image-dir pdf_pages_meineke 2>&1 | tee -a "$LOGFILE"

# Step 3: Retire finished Billerbeck OCR step
echo "Step 3: Skipping Billerbeck OCR (OCR corpus complete)." | tee -a "$LOGFILE"

# Step 3b: Process queued Meineke images with line/apparatus OCR
echo "Step 3b: Processing Meineke images..." | tee -a "$LOGFILE"
uv run process_meineke_pages.py --delay 1 2>&1 | tee -a "$LOGFILE"

# Step 3c: Queue alternate-parity Billerbeck PDF pages for the German reference lane
BILLERBECK_GERMAN_QUEUE_LIMIT="${BILLERBECK_GERMAN_QUEUE_LIMIT:-3}"
if [ "$BILLERBECK_GERMAN_QUEUE_LIMIT" -gt 0 ]; then
    echo "Step 3c: Queueing Billerbeck German PDF pages..." | tee -a "$LOGFILE"
    uv run enqueue_billerbeck_german_pdf_pages.py --limit "$BILLERBECK_GERMAN_QUEUE_LIMIT" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: Billerbeck German PDF enqueue step failed" | tee -a "$LOGFILE"
fi

# Step 3d: Slowly OCR Billerbeck German reference pages from the existing image corpus
BILLERBECK_GERMAN_OCR_LIMIT="${BILLERBECK_GERMAN_OCR_LIMIT:-3}"
if [ "$BILLERBECK_GERMAN_OCR_LIMIT" -gt 0 ]; then
    echo "Step 3d: Processing Billerbeck German pages..." | tee -a "$LOGFILE"
    uv run process_billerbeck_german_pages.py --limit "$BILLERBECK_GERMAN_OCR_LIMIT" --delay 1 \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: Billerbeck German OCR step failed" | tee -a "$LOGFILE"
fi

# Step 4: Assemble lemmas across pages (handles continuations and human overrides)
echo "Step 4: Assembling lemmas..." | tee -a "$LOGFILE"
uv run assemble_lemmas.py 2>&1 | tee -a "$LOGFILE"

# Step 4a: Assemble Billerbeck German OCR into per-lemma reference rows
echo "Step 4a: Assembling Billerbeck German references..." | tee -a "$LOGFILE"
uv run assemble_billerbeck_german.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Billerbeck German assembly step failed" | tee -a "$LOGFILE"

# Step 4b: Assemble Meineke source text versions (OCR + CSV fallback)
echo "Step 4b: Assembling Meineke source texts..." | tee -a "$LOGFILE"
uv run assemble_meineke_texts.py 2>&1 | tee -a "$LOGFILE"

# Step 4b2: Report holes in Meineke OCR coverage up to current max processed page
echo "Step 4b2: Generating Meineke holes report..." | tee -a "$LOGFILE"
uv run generate_meineke_holes_report.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Meineke holes report step failed" | tee -a "$LOGFILE"

# Step 4c: Backfill canonical source text versions from legacy fields
echo "Step 4c: Backfilling source text versions..." | tee -a "$LOGFILE"
uv run backfill_source_text_versions.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: source text backfill failed" | tee -a "$LOGFILE"

# Step 4d: Seed prompt profiles from legacy translation prompts (idempotent)
echo "Step 4d: Seeding translation prompt profiles..." | tee -a "$LOGFILE"
uv run seed_translation_profiles.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: profile seed failed" | tee -a "$LOGFILE"

# Step 4d2: Seed curated translation styles (idempotent)
echo "Step 4d2: Seeding curated translation styles..." | tee -a "$LOGFILE"
uv run seed_translation_styles.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: style seed failed" | tee -a "$LOGFILE"

# Step 4d2a: Seed approved-human translation experiment profiles (idempotent)
echo "Step 4d2a: Seeding translation experiment profiles..." | tee -a "$LOGFILE"
uv run seed_translation_experiment_profiles.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: experiment profile seed failed" | tee -a "$LOGFILE"

# Step 4d3: Backfill authoritative translation runs from compatibility columns
echo "Step 4d3: Backfilling authoritative translation runs..." | tee -a "$LOGFILE"
uv run backfill_legacy_translation_runs.py --source-document meineke 2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation backfill failed" | tee -a "$LOGFILE"

# Step 4d3a: Ensure Billerbeck-sourced AI translations stay hidden/non-public
echo "Step 4d3a: Hiding Billerbeck-sourced AI translation runs..." | tee -a "$LOGFILE"
uv run mark_billerbeck_translation_runs_nonpublic.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Billerbeck translation visibility update failed" | tee -a "$LOGFILE"

# Step 4d4: Resolve already-detected Homeric citations into source-passage prompt context
HOMERIC_SOURCE_RESOLVE_LIMIT="${HOMERIC_SOURCE_RESOLVE_LIMIT:-25}"
HOMERIC_SOURCE_RESOLVE_DELAY="${HOMERIC_SOURCE_RESOLVE_DELAY:-0.25}"
if [ "$HOMERIC_SOURCE_RESOLVE_LIMIT" -gt 0 ]; then
    echo "Step 4d4: Resolving Homeric source passages..." | tee -a "$LOGFILE"
    uv run resolve_homeric_source_passages.py \
        --source-document meineke \
        --limit "$HOMERIC_SOURCE_RESOLVE_LIMIT" \
        --delay "$HOMERIC_SOURCE_RESOLVE_DELAY" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: Homeric source passage resolution failed" | tee -a "$LOGFILE"
fi

# Step 4d5: Sync review database from merah before guidance/translation
echo "Step 4d5: Syncing review database from merah..." | tee -a "$LOGFILE"
./sync_review_db.sh 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to sync review database" | tee -a "$LOGFILE"

# Step 4d6: Import reviews into PostgreSQL before guidance/translation
echo "Step 4d6: Importing reviews into PostgreSQL..." | tee -a "$LOGFILE"
uv run import_reviews.py 2>&1 | tee -a "$LOGFILE"

# Step 4d6a: Reconcile AI translation freshness against current guidance rules
TRANSLATION_GUIDANCE_FRESHNESS_ENABLED="${TRANSLATION_GUIDANCE_FRESHNESS_ENABLED:-1}"
TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_LIMIT="${TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_LIMIT:-2000}"
TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_PRIORITY="${TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_PRIORITY:-20}"
if [ "$TRANSLATION_GUIDANCE_FRESHNESS_ENABLED" != "0" ]; then
    echo "Step 4d6a: Refreshing translation guidance freshness..." | tee -a "$LOGFILE"
    guidance_freshness_args=(
        uv run refresh_translation_guidance_freshness.py
        --source-document preferred
        --guidance-queue-priority "$TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_PRIORITY"
        --created-by "run_daily_pipeline.sh"
    )
    if [ "$TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_LIMIT" -gt 0 ]; then
        guidance_freshness_args+=(--enqueue-missing --max-guidance-queue-rows "$TRANSLATION_GUIDANCE_FRESHNESS_QUEUE_LIMIT")
    fi
    "${guidance_freshness_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation-guidance freshness refresh failed" | tee -a "$LOGFILE"
fi

# Step 4d7: Incrementally queue prompt-eligible guidance scans before translation
TRANSLATION_GUIDANCE_SCAN_QUEUE_LIMIT="${TRANSLATION_GUIDANCE_SCAN_QUEUE_LIMIT:-2000}"
TRANSLATION_GUIDANCE_SCAN_SOURCE_LIMIT="${TRANSLATION_GUIDANCE_SCAN_SOURCE_LIMIT:-}"
if [ "$TRANSLATION_GUIDANCE_SCAN_QUEUE_LIMIT" -gt 0 ]; then
    echo "Step 4d7: Queueing translation-guidance scans before translation..." | tee -a "$LOGFILE"
    guidance_enqueue_args=(
        --prompt-eligible-rules
        --source-document preferred
        --max-queue-rows "$TRANSLATION_GUIDANCE_SCAN_QUEUE_LIMIT"
        --prioritize-kappa-untranslated
        --created-by "run_daily_pipeline.sh"
        --notes "daily pipeline guidance-first scan"
    )
    if [ -n "$TRANSLATION_GUIDANCE_SCAN_SOURCE_LIMIT" ]; then
        guidance_enqueue_args+=(--limit "$TRANSLATION_GUIDANCE_SCAN_SOURCE_LIMIT")
    fi
    uv run enqueue_translation_guidance_scans.py "${guidance_enqueue_args[@]}" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation-guidance enqueue step failed" | tee -a "$LOGFILE"
fi

# Step 4d7a: Queue guidance needed for approved-human translation evaluation backfill
HUMAN_EVAL_TRANSLATION_ENABLED="${HUMAN_EVAL_TRANSLATION_ENABLED:-1}"
HUMAN_EVAL_TRANSLATION_PROFILE="${HUMAN_EVAL_TRANSLATION_PROFILE:-legacy_scholarly}"
HUMAN_EVAL_TRANSLATION_VERSIONS="${HUMAN_EVAL_TRANSLATION_VERSIONS:-3}"
HUMAN_EVAL_TRANSLATION_SOURCE_DOCUMENT="${HUMAN_EVAL_TRANSLATION_SOURCE_DOCUMENT:-preferred}"
HUMAN_EVAL_TRANSLATION_GUIDANCE_LIMIT="${HUMAN_EVAL_TRANSLATION_GUIDANCE_LIMIT:-300}"
HUMAN_EVAL_TRANSLATION_ENQUEUE_LIMIT="${HUMAN_EVAL_TRANSLATION_ENQUEUE_LIMIT:-90}"
HUMAN_EVAL_TRANSLATION_PRIORITY="${HUMAN_EVAL_TRANSLATION_PRIORITY:-5}"
HUMAN_EVAL_TRANSLATION_CREATED_BY="${HUMAN_EVAL_TRANSLATION_CREATED_BY:-run_daily_pipeline.sh:human-eval}"
if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ] && [ "$HUMAN_EVAL_TRANSLATION_GUIDANCE_LIMIT" -gt 0 ]; then
    echo "Step 4d7a: Queueing guidance for approved-human evaluation translations..." | tee -a "$LOGFILE"
    uv run enqueue_human_evaluation_translations.py \
        --profile "$HUMAN_EVAL_TRANSLATION_PROFILE" \
        --versions "$HUMAN_EVAL_TRANSLATION_VERSIONS" \
        --source-document "$HUMAN_EVAL_TRANSLATION_SOURCE_DOCUMENT" \
        --limit "$HUMAN_EVAL_TRANSLATION_GUIDANCE_LIMIT" \
        --priority "$HUMAN_EVAL_TRANSLATION_PRIORITY" \
        --created-by "$HUMAN_EVAL_TRANSLATION_CREATED_BY" \
        --prepare-guidance-first \
        --guidance-only \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: approved-human evaluation guidance queue step failed" | tee -a "$LOGFILE"
fi

# Step 4d7b: Queue guidance for approved-human translation experiments
HUMAN_EVAL_EXPERIMENT_ENABLED="${HUMAN_EVAL_EXPERIMENT_ENABLED:-1}"
HUMAN_EVAL_EXPERIMENT_PROFILES="${HUMAN_EVAL_EXPERIMENT_PROFILES:-legacy_scholarly_v3_repeat legacy_scholarly_v4_reasoning legacy_scholarly_v4_reasoning_medium legacy_scholarly_v4_reasoning_high legacy_scholarly_v4_mini legacy_scholarly_v4_mini_medium legacy_scholarly_v4_mini_high}"
HUMAN_EVAL_EXPERIMENT_SOURCE_DOCUMENT="${HUMAN_EVAL_EXPERIMENT_SOURCE_DOCUMENT:-$HUMAN_EVAL_TRANSLATION_SOURCE_DOCUMENT}"
HUMAN_EVAL_EXPERIMENT_GUIDANCE_LIMIT="${HUMAN_EVAL_EXPERIMENT_GUIDANCE_LIMIT:-30}"
HUMAN_EVAL_EXPERIMENT_ENQUEUE_LIMIT="${HUMAN_EVAL_EXPERIMENT_ENQUEUE_LIMIT:-1}"
HUMAN_EVAL_EXPERIMENT_MAX_OPEN_REQUESTS="${HUMAN_EVAL_EXPERIMENT_MAX_OPEN_REQUESTS:-1}"
HUMAN_EVAL_EXPERIMENT_PRIORITY="${HUMAN_EVAL_EXPERIMENT_PRIORITY:-4}"
HUMAN_EVAL_EXPERIMENT_CREATED_BY="${HUMAN_EVAL_EXPERIMENT_CREATED_BY:-run_daily_pipeline.sh:human-eval-experiment}"
if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ] && [ "$HUMAN_EVAL_EXPERIMENT_ENABLED" != "0" ] && [ "$HUMAN_EVAL_EXPERIMENT_GUIDANCE_LIMIT" -gt 0 ]; then
    echo "Step 4d7b: Queueing guidance for approved-human translation experiments..." | tee -a "$LOGFILE"
    for experiment_profile in $HUMAN_EVAL_EXPERIMENT_PROFILES; do
        uv run enqueue_human_evaluation_translations.py \
            --profile "$experiment_profile" \
            --versions 1 \
            --source-document "$HUMAN_EVAL_EXPERIMENT_SOURCE_DOCUMENT" \
            --limit "$HUMAN_EVAL_EXPERIMENT_GUIDANCE_LIMIT" \
            --priority "$HUMAN_EVAL_EXPERIMENT_PRIORITY" \
            --created-by "$HUMAN_EVAL_EXPERIMENT_CREATED_BY" \
            --prepare-guidance-first \
            --guidance-only \
            2>&1 | tee -a "$LOGFILE" || echo "  Warning: approved-human experiment guidance queue failed for ${experiment_profile}" | tee -a "$LOGFILE"
    done
fi

# Step 4d8: Process a bounded translation-guidance scan batch before translation
TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT="${TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT:-2000}"
TRANSLATION_GUIDANCE_SCAN_MODEL="${TRANSLATION_GUIDANCE_SCAN_MODEL:-gpt-5.4-mini}"
TRANSLATION_GUIDANCE_SCAN_DAILY_TOKEN_LIMIT="${TRANSLATION_GUIDANCE_SCAN_DAILY_TOKEN_LIMIT:-2000000}"
TRANSLATION_GUIDANCE_SCAN_GUIDANCE_AI_LIMIT="${TRANSLATION_GUIDANCE_SCAN_GUIDANCE_AI_LIMIT:-${TRANSLATION_GUIDANCE_SCAN_FORMULA_AI_LIMIT:-$TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT}}"
TRANSLATION_GUIDANCE_SCAN_DELAY="${TRANSLATION_GUIDANCE_SCAN_DELAY:-0}"
TRANSLATION_GUIDANCE_SCAN_USE_BATCH="${TRANSLATION_GUIDANCE_SCAN_USE_BATCH:-1}"
TRANSLATION_GUIDANCE_SCAN_BATCH_WAIT="${TRANSLATION_GUIDANCE_SCAN_BATCH_WAIT:-1}"
TRANSLATION_GUIDANCE_SCAN_BATCH_POLL_INTERVAL="${TRANSLATION_GUIDANCE_SCAN_BATCH_POLL_INTERVAL:-30}"
TRANSLATION_GUIDANCE_SCAN_BATCH_TIMEOUT="${TRANSLATION_GUIDANCE_SCAN_BATCH_TIMEOUT:-0}"
case "$TRANSLATION_GUIDANCE_SCAN_MODEL" in
    *-mini*) ;;
    *)
        echo "  ERROR: TRANSLATION_GUIDANCE_SCAN_MODEL must be a *-mini model, got ${TRANSLATION_GUIDANCE_SCAN_MODEL}" | tee -a "$LOGFILE"
        TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT=0
        ;;
esac
if [ "$TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT" -gt 0 ]; then
    echo "Step 4d8: Processing translation-guidance scans before translation..." | tee -a "$LOGFILE"
    guidance_process_args=(
        uv run process_translation_guidance_scans.py
        --limit "$TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT" \
        --model "$TRANSLATION_GUIDANCE_SCAN_MODEL" \
        --daily-token-limit "$TRANSLATION_GUIDANCE_SCAN_DAILY_TOKEN_LIMIT" \
        --guidance-ai-limit "$TRANSLATION_GUIDANCE_SCAN_GUIDANCE_AI_LIMIT"
    )
    if [ "$TRANSLATION_GUIDANCE_SCAN_USE_BATCH" != "0" ]; then
        guidance_process_args+=(--batch)
        if [ "$TRANSLATION_GUIDANCE_SCAN_BATCH_WAIT" != "0" ]; then
            guidance_process_args+=(--batch-wait --batch-poll-interval "$TRANSLATION_GUIDANCE_SCAN_BATCH_POLL_INTERVAL")
            if [ "$TRANSLATION_GUIDANCE_SCAN_BATCH_TIMEOUT" != "0" ]; then
                guidance_process_args+=(--batch-timeout "$TRANSLATION_GUIDANCE_SCAN_BATCH_TIMEOUT")
            fi
        fi
    else
        guidance_process_args+=(--delay "$TRANSLATION_GUIDANCE_SCAN_DELAY")
    fi
    "${guidance_process_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation-guidance scan step failed" | tee -a "$LOGFILE"
fi

# Step 4d8a: Queue approved-human evaluation translation requests before normal translation work
if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ] && [ "$HUMAN_EVAL_TRANSLATION_ENQUEUE_LIMIT" -gt 0 ]; then
    echo "Step 4d8a: Enqueuing approved-human evaluation translations..." | tee -a "$LOGFILE"
    uv run enqueue_human_evaluation_translations.py \
        --profile "$HUMAN_EVAL_TRANSLATION_PROFILE" \
        --versions "$HUMAN_EVAL_TRANSLATION_VERSIONS" \
        --source-document "$HUMAN_EVAL_TRANSLATION_SOURCE_DOCUMENT" \
        --limit "$HUMAN_EVAL_TRANSLATION_ENQUEUE_LIMIT" \
        --priority "$HUMAN_EVAL_TRANSLATION_PRIORITY" \
        --created-by "$HUMAN_EVAL_TRANSLATION_CREATED_BY" \
        --require-guidance-complete \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: approved-human evaluation translation enqueue step failed" | tee -a "$LOGFILE"
fi

# Step 4d8b: Queue approved-human translation experiment requests slowly
if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ] && [ "$HUMAN_EVAL_EXPERIMENT_ENABLED" != "0" ] && [ "$HUMAN_EVAL_EXPERIMENT_ENQUEUE_LIMIT" -gt 0 ]; then
    echo "Step 4d8b: Enqueuing approved-human translation experiments..." | tee -a "$LOGFILE"
    for experiment_profile in $HUMAN_EVAL_EXPERIMENT_PROFILES; do
        uv run enqueue_human_evaluation_translations.py \
            --profile "$experiment_profile" \
            --versions 1 \
            --source-document "$HUMAN_EVAL_EXPERIMENT_SOURCE_DOCUMENT" \
            --limit "$HUMAN_EVAL_EXPERIMENT_ENQUEUE_LIMIT" \
            --max-open-requests "$HUMAN_EVAL_EXPERIMENT_MAX_OPEN_REQUESTS" \
            --priority "$HUMAN_EVAL_EXPERIMENT_PRIORITY" \
            --created-by "$HUMAN_EVAL_EXPERIMENT_CREATED_BY" \
            --require-guidance-complete \
            2>&1 | tee -a "$LOGFILE" || echo "  Warning: approved-human experiment enqueue failed for ${experiment_profile}" | tee -a "$LOGFILE"
    done
fi

# Step 4e: Enqueue preferred-source translation run requests (set TRANSLATION_ENQUEUE_LIMIT=0 to disable)
TRANSLATION_ENQUEUE_LIMIT="${TRANSLATION_ENQUEUE_LIMIT:-20}"
TRANSLATION_ENQUEUE_ORDER="${TRANSLATION_ENQUEUE_ORDER:-canonical}"
# Kappa review is the current editorial priority; give these requests enough
# queue priority to run ahead of older mixed-letter v3 requests.
TRANSLATION_ENQUEUE_PRIORITY="${TRANSLATION_ENQUEUE_PRIORITY:-20}"
TRANSLATION_ENQUEUE_LETTER="${TRANSLATION_ENQUEUE_LETTER:-kappa}"
TRANSLATION_ENQUEUE_HEADWORD_PREFIX="${TRANSLATION_ENQUEUE_HEADWORD_PREFIX:-}"
if [ "$TRANSLATION_ENQUEUE_LIMIT" -gt 0 ]; then
    echo "Step 4e: Enqueuing translation run requests..." | tee -a "$LOGFILE"
    translation_enqueue_args=(
        uv run enqueue_translation_runs.py
        --profile legacy_scholarly
        --source-document preferred
        --limit "$TRANSLATION_ENQUEUE_LIMIT"
        --missing-final
        --order "$TRANSLATION_ENQUEUE_ORDER"
        --priority "$TRANSLATION_ENQUEUE_PRIORITY"
        --repeat 1
        --prepare-guidance-first
        --require-guidance-complete
    )
    if [ -n "$TRANSLATION_ENQUEUE_LETTER" ]; then
        translation_enqueue_args+=(--letter "$TRANSLATION_ENQUEUE_LETTER")
    fi
    if [ -n "$TRANSLATION_ENQUEUE_HEADWORD_PREFIX" ]; then
        translation_enqueue_args+=(--headword-prefix "$TRANSLATION_ENQUEUE_HEADWORD_PREFIX")
    fi
    "${translation_enqueue_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: enqueue step failed" | tee -a "$LOGFILE"
fi

# Step 5r: Translate Responses API/reasoning requests slowly before the batch lane
TRANSLATION_RESPONSES_RUN_LIMIT="${TRANSLATION_RESPONSES_RUN_LIMIT:-1}"
TRANSLATION_RESPONSES_REQUEST_LIMIT="${TRANSLATION_RESPONSES_REQUEST_LIMIT:-10}"
TRANSLATION_RESPONSES_DAILY_TOKEN_LIMIT="${TRANSLATION_RESPONSES_DAILY_TOKEN_LIMIT:-50000}"
if [ "$TRANSLATION_RESPONSES_RUN_LIMIT" -gt 0 ]; then
    echo "Step 5r: Translating Responses API requests slowly..." | tee -a "$LOGFILE"
    response_translation_args=(
        uv run translate_lemmas.py
        --api-mode responses
        --request-limit "$TRANSLATION_RESPONSES_REQUEST_LIMIT"
        --run-limit "$TRANSLATION_RESPONSES_RUN_LIMIT"
        --daily-token-limit "$TRANSLATION_RESPONSES_DAILY_TOKEN_LIMIT"
        --delay 1
    )
    if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ]; then
        response_translation_args+=(--allow-human-evaluation-translations)
    fi
    "${response_translation_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Responses API translation step failed" | tee -a "$LOGFILE"
fi

# Step 5: Translate Chat Completions requests with gpt-5.5 after guidance coverage is complete
echo "Step 5: Translating Chat Completions translation requests..." | tee -a "$LOGFILE"
TRANSLATION_USE_BATCH="${TRANSLATION_USE_BATCH:-1}"
TRANSLATION_BATCH_WAIT="${TRANSLATION_BATCH_WAIT:-1}"
TRANSLATION_BATCH_POLL_INTERVAL="${TRANSLATION_BATCH_POLL_INTERVAL:-30}"
TRANSLATION_BATCH_TIMEOUT="${TRANSLATION_BATCH_TIMEOUT:-0}"
translation_args=(uv run translate_lemmas.py --api-mode chat_completions)
if [ "$TRANSLATION_USE_BATCH" != "0" ]; then
    translation_args+=(--batch)
    if [ "$TRANSLATION_BATCH_WAIT" != "0" ]; then
        translation_args+=(--batch-wait --batch-poll-interval "$TRANSLATION_BATCH_POLL_INTERVAL")
        if [ "$TRANSLATION_BATCH_TIMEOUT" != "0" ]; then
            translation_args+=(--batch-timeout "$TRANSLATION_BATCH_TIMEOUT")
        fi
    fi
else
    translation_args+=(--delay 1)
fi
if [ "$HUMAN_EVAL_TRANSLATION_ENABLED" != "0" ]; then
    translation_args+=(--allow-human-evaluation-translations)
fi
"${translation_args[@]}" 2>&1 | tee -a "$LOGFILE"

# Step 4e2: Backfill prompt/request artifacts for older Batch translation runs
echo "Step 4e2: Backfilling translation prompt/request artifacts..." | tee -a "$LOGFILE"
uv run backfill_translation_run_request_payloads.py \
    2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation prompt/request artifact backfill failed" | tee -a "$LOGFILE"

# Step 5a0: Low-priority AI footnote detection (default: one check per run)
FOOTNOTE_DETECTION_LIMIT="${FOOTNOTE_DETECTION_LIMIT:-1}"
FOOTNOTE_DETECTION_MODEL="${FOOTNOTE_DETECTION_MODEL:-gpt-5.4-mini}"
FOOTNOTE_DETECTION_DAILY_TOKEN_LIMIT="${FOOTNOTE_DETECTION_DAILY_TOKEN_LIMIT:-20000}"
if [ "$FOOTNOTE_DETECTION_LIMIT" -gt 0 ]; then
    echo "Step 5a0: Detecting AI footnotes slowly..." | tee -a "$LOGFILE"
    uv run detect_footnotes.py \
        --limit "$FOOTNOTE_DETECTION_LIMIT" \
        --model "$FOOTNOTE_DETECTION_MODEL" \
        --daily-token-limit "$FOOTNOTE_DETECTION_DAILY_TOKEN_LIMIT" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: AI footnote detection step failed" | tee -a "$LOGFILE"
fi

# Step 5aa: Translate assembled Billerbeck German references to English
BILLERBECK_GERMAN_TRANSLATE_LIMIT="${BILLERBECK_GERMAN_TRANSLATE_LIMIT:-5}"
if [ "$BILLERBECK_GERMAN_TRANSLATE_LIMIT" -gt 0 ]; then
    echo "Step 5aa: Translating Billerbeck German references..." | tee -a "$LOGFILE"
    uv run translate_billerbeck_german.py --limit "$BILLERBECK_GERMAN_TRANSLATE_LIMIT" --delay 1 \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: Billerbeck German translation step failed" | tee -a "$LOGFILE"
fi

# Step 5a: Count words in Greek text
echo "Step 5a: Counting words in Greek text..." | tee -a "$LOGFILE"
uv run count_words.py 2>&1 | tee -a "$LOGFILE"

# Step 5b: Extract proper nouns
echo "Step 5b: Extracting proper nouns..." | tee -a "$LOGFILE"
uv run extract_proper_nouns.py 2>&1 | tee -a "$LOGFILE"

# Step 5b1: Extract distinct place clusters for entity review
PLACE_CLUSTER_EXTRACT_LIMIT="${PLACE_CLUSTER_EXTRACT_LIMIT:-3}"
PLACE_CLUSTER_EXTRACT_DELAY="${PLACE_CLUSTER_EXTRACT_DELAY:-1}"
PLACE_CLUSTER_DAILY_TOKEN_LIMIT="${PLACE_CLUSTER_DAILY_TOKEN_LIMIT:-12000}"
if [ "$PLACE_CLUSTER_EXTRACT_LIMIT" -gt 0 ]; then
    echo "Step 5b1: Extracting place clusters slowly (limit ${PLACE_CLUSTER_EXTRACT_LIMIT}/day)..." | tee -a "$LOGFILE"
    uv run extract_place_clusters.py \
        --daily-limit "$PLACE_CLUSTER_EXTRACT_LIMIT" \
        --daily-token-limit "$PLACE_CLUSTER_DAILY_TOKEN_LIMIT" \
        --delay "$PLACE_CLUSTER_EXTRACT_DELAY" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: place-cluster extraction step failed" | tee -a "$LOGFILE"
fi

# Step 5b2: Extract structured source-citation units (author+work+book)
SOURCE_CITATION_EXTRACT_MODEL="${SOURCE_CITATION_EXTRACT_MODEL:-gpt-5.4-mini}"
SOURCE_CITATION_EXTRACT_LIMIT="${SOURCE_CITATION_EXTRACT_LIMIT:-300}"
SOURCE_CITATION_EXTRACT_DELAY="${SOURCE_CITATION_EXTRACT_DELAY:-0.1}"
if [ "$SOURCE_CITATION_EXTRACT_LIMIT" -gt 0 ]; then
    echo "Step 5b2: Extracting source-citation units..." | tee -a "$LOGFILE"
    uv run extract_source_citation_units.py \
        --model "$SOURCE_CITATION_EXTRACT_MODEL" \
        --limit "$SOURCE_CITATION_EXTRACT_LIMIT" \
        --delay "$SOURCE_CITATION_EXTRACT_DELAY" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: source-citation extraction step failed" | tee -a "$LOGFILE"
fi

# Step 5c: Extract etymologies
echo "Step 5c: Extracting etymologies..." | tee -a "$LOGFILE"
uv run extract_etymologies.py 2>&1 | tee -a "$LOGFILE"

# Step 5d: Link proper nouns to Wikidata (limit to 20 per day to control costs)
echo "Step 5d: Linking sources to Wikidata..." | tee -a "$LOGFILE"
uv run link_wikidata.py --limit 20 2>&1 | tee -a "$LOGFILE"

# Step 5d1: Link structured source-citation units to Wikidata (optional; defaults off)
SOURCE_UNIT_WIKIDATA_LINK_LIMIT="${SOURCE_UNIT_WIKIDATA_LINK_LIMIT:-0}"
if [ "$SOURCE_UNIT_WIKIDATA_LINK_LIMIT" -gt 0 ]; then
    echo "Step 5d1: Linking source-citation units to Wikidata..." | tee -a "$LOGFILE"
    uv run link_wikidata_source_citation_units.py --limit "$SOURCE_UNIT_WIKIDATA_LINK_LIMIT" --delay 1 \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: source-unit Wikidata linking step failed" | tee -a "$LOGFILE"
fi

# Step 5d2: Link place headwords to Wikidata (limit to 10 per day to control costs)
echo "Step 5d2: Linking places to Wikidata..." | tee -a "$LOGFILE"
uv run link_wikidata_places.py --limit 10 2>&1 | tee -a "$LOGFILE"

# Step 5d3: Refresh additive canonical authority/entity tables
CANONICAL_AUTHORITY_REFRESH="${CANONICAL_AUTHORITY_REFRESH:-1}"
if [ "$CANONICAL_AUTHORITY_REFRESH" -gt 0 ]; then
    echo "Step 5d3: Refreshing canonical authority layer..." | tee -a "$LOGFILE"
    uv run refresh_canonical_authority_layer.py \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: canonical authority refresh failed" | tee -a "$LOGFILE"
fi

# Step 5e: Extract aliases from Greek text (limit to 20 per day to control costs)
echo "Step 5e: Extracting aliases from Greek text..." | tee -a "$LOGFILE"
uv run extract_aliases.py --limit 20 2>&1 | tee -a "$LOGFILE"

# Step 5f: Generate spelling variants
echo "Step 5f: Generating spelling variants..." | tee -a "$LOGFILE"
uv run generate_spelling_variants.py 2>&1 | tee -a "$LOGFILE"

# Step 5g: Analyze Meineke/Billerbeck differences with gpt-5.4-mini (small daily batch)
echo "Step 5g: Analyzing Meineke/Billerbeck differences..." | tee -a "$LOGFILE"
MEINEKE_DIFF_DAILY_TOKEN_LIMIT="${MEINEKE_DIFF_DAILY_TOKEN_LIMIT:-1000000}"
uv run analyze_meineke_differences.py --limit 20 --daily-token-limit "$MEINEKE_DIFF_DAILY_TOKEN_LIMIT" --delay 1 2>&1 | tee -a "$LOGFILE"

# Step 5g2: Sync versioned text-pair differences from current source versions
echo "Step 5g2: Syncing text-pair differences..." | tee -a "$LOGFILE"
uv run sync_text_pair_differences.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: text-pair differences sync failed" | tee -a "$LOGFILE"

# Step 5g3: Lemmatize Meineke word forms into word/lemma indexes
echo "Step 5g3: Lemmatizing Meineke word forms..." | tee -a "$LOGFILE"
MEINEKE_WORD_LEMMA_DAILY_TOKEN_LIMIT="${MEINEKE_WORD_LEMMA_DAILY_TOKEN_LIMIT:-250000}"
MEINEKE_WORD_LEMMA_DELAY="${MEINEKE_WORD_LEMMA_DELAY:-1}"
if [ -n "${MEINEKE_WORD_LEMMA_LIMIT:-}" ]; then
    uv run lemmatize_meineke_words.py \
        --daily-token-limit "$MEINEKE_WORD_LEMMA_DAILY_TOKEN_LIMIT" \
        --limit "$MEINEKE_WORD_LEMMA_LIMIT" \
        --delay "$MEINEKE_WORD_LEMMA_DELAY" \
        2>&1 | tee -a "$LOGFILE"
else
    uv run lemmatize_meineke_words.py \
        --daily-token-limit "$MEINEKE_WORD_LEMMA_DAILY_TOKEN_LIMIT" \
        --delay "$MEINEKE_WORD_LEMMA_DELAY" \
        2>&1 | tee -a "$LOGFILE"
fi

# Step 5g4: Refresh vocabulary signatures from the populated word/lemma index
VOCABULARY_SIGNATURES_ENABLED="${VOCABULARY_SIGNATURES_ENABLED:-1}"
VOCABULARY_SIGNATURE_WINDOW_SIZE="${VOCABULARY_SIGNATURE_WINDOW_SIZE:-100}"
VOCABULARY_SIGNATURE_MAX_FEATURES="${VOCABULARY_SIGNATURE_MAX_FEATURES:-500}"
VOCABULARY_SIGNATURE_MIN_FEATURE_COUNT="${VOCABULARY_SIGNATURE_MIN_FEATURE_COUNT:-5}"
if [ "$VOCABULARY_SIGNATURES_ENABLED" != "0" ]; then
    echo "Step 5g4: Refreshing vocabulary signatures..." | tee -a "$LOGFILE"
    uv run analyze_vocabulary_signatures.py \
        --source-document meineke \
        --feature-basis lemma \
        --window-size "$VOCABULARY_SIGNATURE_WINDOW_SIZE" \
        --max-features "$VOCABULARY_SIGNATURE_MAX_FEATURES" \
        --min-feature-count "$VOCABULARY_SIGNATURE_MIN_FEATURE_COUNT" \
        --notes "run_daily_pipeline.sh word-lemma vocabulary signatures" \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: vocabulary signature analysis failed" | tee -a "$LOGFILE"
fi

# Step 5h: Sync translation risk flags (blocks likely translation-changing Billerbeck-dependent rows)
echo "Step 5h: Syncing translation risk flags..." | tee -a "$LOGFILE"
uv run sync_translation_risk_flags.py 2>&1 | tee -a "$LOGFILE"

# Step 5i: Refresh legacy canonical fields from publication pointers
echo "Step 5i: Refreshing legacy canonical fields..." | tee -a "$LOGFILE"
uv run refresh_legacy_canonical_fields.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: legacy canonical refresh failed" | tee -a "$LOGFILE"

# Step 5l: Sync with nodegoat before progress/site generation
echo "Step 5l: Syncing with nodegoat..." | tee -a "$LOGFILE"
uv run sync_nodegoat.py --push --catch-up --limit 20 2>&1 | tee -a "$LOGFILE" || echo "  Warning: nodegoat sync failed" | tee -a "$LOGFILE"

# Step 7: Generate reference website
echo "Step 7: Generating reference website..." | tee -a "$LOGFILE"
uv run generate_reference_site.py 2>&1 | tee -a "$LOGFILE"

# Step 7a0: Generate word/lemma indexes and static search data
echo "Step 7a0: Generating word/lemma indexes and search data..." | tee -a "$LOGFILE"
uv run generate_word_lemma_indexes.py 2>&1 | tee -a "$LOGFILE"

# Step 7a: Generate statistics website
echo "Step 7a: Generating statistics website..." | tee -a "$LOGFILE"
uv run generate_statistics_site.py 2>&1 | tee -a "$LOGFILE"

# Step 7a0a: Generate translation prompt evaluation pages
echo "Step 7a0a: Generating translation prompt evaluation..." | tee -a "$LOGFILE"
uv run generate_translation_prompt_evaluation.py --approved-human-only 2>&1 | tee -a "$LOGFILE"

# Step 7a0a1: Generate v3 translation quality predictor page
echo "Step 7a0a1: Generating translation quality predictor page..." | tee -a "$LOGFILE"
uv run generate_translation_quality_predictor_page.py 2>&1 | tee -a "$LOGFILE"

# Step 7a0b: Generate translation operations/cost page
echo "Step 7a0b: Generating translation operations page..." | tee -a "$LOGFILE"
uv run generate_translation_operations_page.py 2>&1 | tee -a "$LOGFILE"

# Step 7a0c: Generate stylometric fingerprinting page
echo "Step 7a0c: Generating stylometric fingerprinting page..." | tee -a "$LOGFILE"
uv run generate_fingerprinting_page.py 2>&1 | tee -a "$LOGFILE"

# Step 7a0d: Generate vocabulary signature page
echo "Step 7a0d: Generating vocabulary signature page..." | tee -a "$LOGFILE"
uv run generate_vocabulary_signature_page.py 2>&1 | tee -a "$LOGFILE"

# Step 7a1: Generate pipeline progress page
echo "Step 7a1: Generating pipeline progress page..." | tee -a "$LOGFILE"
uv run generate_pipeline_progress.py 2>&1 | tee -a "$LOGFILE"

# Step 7a2: Analyze Pausanias citations
echo "Step 7a2: Analyzing Pausanias citations..." | tee -a "$LOGFILE"
uv run analyze_pausanias_citations.py 2>&1 | tee -a "$LOGFILE"

# Step 7a3: Generate places map
echo "Step 7a3: Generating places map..." | tee -a "$LOGFILE"
uv run generate_places_map.py 2>&1 | tee -a "$LOGFILE"

# Step 7b: Generate entity pages (sources, works, entities, peoples, fgrhist, aliases)
echo "Step 7b: Generating entity pages..." | tee -a "$LOGFILE"
uv run generate_sources_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_works_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_entities_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_peoples_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_fgrhist_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_aliases_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_meineke_difference_analysis_page.py 2>&1 | tee -a "$LOGFILE"
uv run generate_translation_guidance_page.py 2>&1 | tee -a "$LOGFILE"

# Step 7c: Generate protected pages
echo "Step 7c: Generating protected pages..." | tee -a "$LOGFILE"
uv run generate_protected_pages.py 2>&1 | tee -a "$LOGFILE"

# Step 7c1: Generate headword clustering page (UMAP + clustering)
echo "Step 7c1: Generating headword clustering page..." | tee -a "$LOGFILE"
uv run generate_headword_clustering_page.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: headword clustering page step failed" | tee -a "$LOGFILE"

# Step 7c2: Generate translation risk report
echo "Step 7c2: Generating translation risk report..." | tee -a "$LOGFILE"
uv run generate_translation_risk_report.py 2>&1 | tee -a "$LOGFILE"

# Step 7c3: Generate entity resolution review page
echo "Step 7c3: Generating entity resolution review page..." | tee -a "$LOGFILE"
uv run generate_entity_resolution_review_page.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: entity resolution review page step failed" | tee -a "$LOGFILE"

# Step 7c4: Generate Brady vs AI entity review page
echo "Step 7c4: Generating Brady vs AI entity review page..." | tee -a "$LOGFILE"
uv run generate_brady_entity_review_page.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Brady entity review page step failed" | tee -a "$LOGFILE"

# Step 8: Export lemmas CSV
echo "Step 8: Exporting lemmas CSV..." | tee -a "$LOGFILE"
uv run generate_csv_export.py --output exports/lemmas.csv 2>&1 | tee -a "$LOGFILE"

# Step 8a: Export proper nouns CSV
echo "Step 8a: Exporting proper nouns CSV..." | tee -a "$LOGFILE"
uv run export_proper_nouns_csv.py 2>&1 | tee -a "$LOGFILE"

# Step 8a2: Export etymologies CSV
echo "Step 8a2: Exporting etymologies CSV..." | tee -a "$LOGFILE"
uv run export_etymologies_csv.py 2>&1 | tee -a "$LOGFILE"

# Step 8a2b: Export structured source-citation CSVs
echo "Step 8a2b: Exporting structured source-citation CSVs..." | tee -a "$LOGFILE"
uv run export_source_citation_csv.py 2>&1 | tee -a "$LOGFILE"

# Step 8a3: Export for nodegoat
echo "Step 8a3: Exporting for nodegoat..." | tee -a "$LOGFILE"
uv run export_for_nodegoat.py --output exports/nodegoat 2>&1 | tee -a "$LOGFILE"

# Step 8a4: Generate PDF book
echo "Step 8a4: Generating PDF book..." | tee -a "$LOGFILE"
uv run generate_pdf_book.py 2>&1 | tee -a "$LOGFILE"

# Step 8a5: Generate downloads page
echo "Step 8a5: Generating downloads page..." | tee -a "$LOGFILE"
uv run generate_downloads_page.py 2>&1 | tee -a "$LOGFILE"

# Step 8a6: Generate short AI systems status RSS/JSON and cron-mail report
echo "Step 8a6: Generating AI systems status feed..." | tee -a "$LOGFILE"
emit_ai_systems_status_report 0 2>&1 | tee -a "$LOGFILE"
AI_SYSTEMS_STATUS_EMITTED=1

# Step 8b: Export lemma data for review interface
echo "Step 8b: Exporting lemma data for review interface..." | tee -a "$LOGFILE"
uv run export_for_review.py 2>&1 | tee -a "$LOGFILE"
uv run export_guidance_scan_db.py 2>&1 | tee -a "$LOGFILE"

# Step 8c: Generate ToposText intake report for Brady review.
# The dedicated ToposText cron owns these outputs in normal operation.
TOPOSTEXT_INTAKE_REPORT="${TOPOSTEXT_INTAKE_REPORT:-0}"
if [ "$TOPOSTEXT_INTAKE_REPORT" -gt 0 ]; then
    echo "Step 8c: Generating ToposText intake report..." | tee -a "$LOGFILE"
    topostext_report_args=(
        uv run generate_topostext_intake_report.py
        --output exports/topostext_intake_report.html
        --summary-json exports/topostext_intake_report_summary.json
    )
    if [ -f "$TOPOSTEXT_PAULY_WORKBOOK" ]; then
        topostext_report_args+=(--pauly-workbook "$TOPOSTEXT_PAULY_WORKBOOK")
    else
        echo "  Warning: PaulyHeadwords workbook not found at $TOPOSTEXT_PAULY_WORKBOOK; generating without RE enrichment" | tee -a "$LOGFILE"
    fi
    "${topostext_report_args[@]}" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText intake report generation failed" | tee -a "$LOGFILE"

    echo "Step 8c1: Generating ToposText review queues..." | tee -a "$LOGFILE"
    uv run generate_topostext_review_page.py \
        --output exports/topostext_review.html \
        --queue-csv exports/topostext_review_queue.csv \
        --diff-csv exports/topostext_snapshot_diff.csv \
        --tag-review-csv exports/topostext_tag_review.csv \
        --re-candidates-csv exports/topostext_re_candidates.csv \
        --summary-json exports/topostext_review_summary.json \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText review page generation failed" | tee -a "$LOGFILE"

    echo "Step 8c2: Generating ToposText snapshot history..." | tee -a "$LOGFILE"
    uv run generate_topostext_history_page.py \
        --output exports/topostext_history.html \
        --changesets-csv exports/topostext_history_changesets.csv \
        --transitions-csv exports/topostext_history_transitions.csv \
        --entry-history-csv exports/topostext_history_entries.csv \
        --summary-json exports/topostext_history_summary.json \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText history page generation failed" | tee -a "$LOGFILE"

    echo "Step 8c3: Generating ToposText authority status worklists..." | tee -a "$LOGFILE"
    uv run generate_topostext_authority_status_page.py \
        --output exports/topostext_authority_status.html \
        --re-candidates-csv exports/topostext_unmatched_re_candidates.csv \
        --ethnic-suggestions-csv exports/topostext_ethnic_suggestions.csv \
        --new-ids-csv exports/topostext_new_id_worklist.csv \
        --recent-changes-csv exports/topostext_recent_entity_changes.csv \
        --summary-json exports/topostext_authority_status_summary.json \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: ToposText authority status page generation failed" | tee -a "$LOGFILE"
fi

# Step 9: Deploy to merah
echo "Step 9: Deploying to merah..." | tee -a "$LOGFILE"
# Deploy reference_site/ (contains statistics.html, statistics/, statistics_images/, people.html, and all lemma pages)
run_optional_rsync_logged "reference_site" reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
# Remove retired duplicate root progress page if it exists.
ssh stephanos@merah.cassia.ifost.org.au "rm -f /var/www/vhosts/stephanos.symmachus.org/htdocs/progress.html" 2>&1 | tee -a "$LOGFILE"
# Deploy CSV exports
run_rsync_logged exports/lemmas.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
run_rsync_logged exports/proper_nouns.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
run_rsync_logged exports/etymologies.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
run_rsync_logged exports/source_citation_units.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
run_rsync_logged exports/source_citation_mentions.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
# Deploy ToposText intake report outputs when generated
for topostext_export in \
    exports/topostext_intake_report.html \
    exports/topostext_intake_report_mentions.csv \
    exports/topostext_intake_report_re_namespace.csv \
    exports/topostext_intake_report_summary.json \
    exports/topostext_review.html \
    exports/topostext_review_queue.csv \
    exports/topostext_snapshot_diff.csv \
    exports/topostext_tag_review.csv \
    exports/topostext_re_candidates.csv \
    exports/topostext_review_summary.json \
    exports/topostext_history.html \
    exports/topostext_history_changesets.csv \
    exports/topostext_history_transitions.csv \
    exports/topostext_history_entries.csv \
    exports/topostext_history_summary.json \
    exports/topostext_authority_status.html \
    exports/topostext_unmatched_re_candidates.csv \
    exports/topostext_ethnic_suggestions.csv \
    exports/topostext_new_id_worklist.csv \
    exports/topostext_recent_entity_changes.csv \
    exports/topostext_authority_status_summary.json; do
    if [ -f "$topostext_export" ]; then
        run_rsync_logged "$topostext_export" stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
    fi
done
# Deploy nodegoat exports
run_rsync_logged exports/nodegoat/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/nodegoat/
# Deploy review data snapshot
run_rsync_logged review_data.sqlite stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/
# Deploy protected scan evidence database
run_rsync_logged guidance_scan_results.db stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/
# Deploy review CGI binaries from current source
run_review_cgi_deploy_logged || echo "  Warning: review CGI deploy failed or timed out" | tee -a "$LOGFILE"

# Step 10: Backup databases with rolling history
echo "Step 10: Backing up databases..." | tee -a "$LOGFILE"

# Backup PostgreSQL database
echo "  Backing up PostgreSQL database..." | tee -a "$LOGFILE"
mkdir -p backups
dump_postgres_backup "backups/stephanos_${DATE}.sql.gz" 2>&1 | tee -a "$LOGFILE"
DAILY_BACKUP_DONE=1

# Backup review database on merah
echo "  Backing up review database on merah..." | tee -a "$LOGFILE"
ssh stephanos@merah.cassia.ifost.org.au "bash ~/stephanos/backup_review_db.sh" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to backup review database" | tee -a "$LOGFILE"

# Remove local backups older than 7 days
echo "  Cleaning up old local backups (keeping last 7 days)..." | tee -a "$LOGFILE"
find backups -name "stephanos_*.sql.gz" -mtime +7 -delete 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to cleanup old local backups" | tee -a "$LOGFILE"

echo "Pipeline complete: $(date)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"
