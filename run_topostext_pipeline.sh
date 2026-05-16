#!/bin/bash
#
# Dedicated Brady/ToposText Dropbox intake pipeline.
#
# This is intentionally separate from run_daily_pipeline.sh so the shared HTML
# is fetched after Brady's Greek workday rather than during the Sydney evening.

set -e
set -o pipefail

cd "$(dirname "$0")"

LOGFILE="${TOPOSTEXT_LOGFILE:-topostext_pipeline.log}"
LOCKFILE="${TOPOSTEXT_LOCKFILE:-topostext_pipeline.lock}"

exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "ToposText pipeline already running; exiting at $(date)" | tee -a "$LOGFILE"
    exit 0
fi

export DB_HOST="${DB_HOST:-raksasa}"
export DB_USER="${DB_USER:-stephanos}"
export DB_NAME="${DB_NAME:-stephanos}"
export TOPOSTEXT_PAULY_WORKBOOK="${TOPOSTEXT_PAULY_WORKBOOK:-data/pauly/PaulyHeadwordstoWikidata from Margherita scrape.xlsx}"

deploy_target="${TOPOSTEXT_DEPLOY_TARGET:-stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/}"

echo "========================================" | tee -a "$LOGFILE"
echo "ToposText pipeline run: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

echo "Step 0: Pulling latest changes from git..." | tee -a "$LOGFILE"
if git diff --quiet && git diff --cached --quiet; then
    git pull --ff-only origin main 2>&1 | tee -a "$LOGFILE" || echo "  Warning: git pull failed; continuing" | tee -a "$LOGFILE"
else
    echo "  Git working tree has local changes; skipping git pull" | tee -a "$LOGFILE"
fi

echo "Step 1: Fetching Brady's Dropbox ToposText HTML snapshot..." | tee -a "$LOGFILE"
uv run fetch_topostext_html.py --output-dir data/topostext_snapshots \
    2>&1 | tee -a "$LOGFILE"

echo "Step 2: Importing ToposText intake staging rows..." | tee -a "$LOGFILE"
topostext_import_args=(uv run import_topostext_intake.py)
if [ -f "$TOPOSTEXT_PAULY_WORKBOOK" ]; then
    topostext_import_args+=(--pauly-workbook "$TOPOSTEXT_PAULY_WORKBOOK")
else
    echo "  Warning: PaulyHeadwords workbook not found at $TOPOSTEXT_PAULY_WORKBOOK; importing without RE enrichment" | tee -a "$LOGFILE"
fi
"${topostext_import_args[@]}" 2>&1 | tee -a "$LOGFILE"

echo "Step 3: Refreshing canonical authority layer..." | tee -a "$LOGFILE"
uv run refresh_canonical_authority_layer.py \
    2>&1 | tee -a "$LOGFILE"

echo "Step 4: Generating ToposText intake report..." | tee -a "$LOGFILE"
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
"${topostext_report_args[@]}" 2>&1 | tee -a "$LOGFILE"

echo "Step 5: Generating ToposText review queues..." | tee -a "$LOGFILE"
uv run generate_topostext_review_page.py \
    --output exports/topostext_review.html \
    --queue-csv exports/topostext_review_queue.csv \
    --diff-csv exports/topostext_snapshot_diff.csv \
    --tag-review-csv exports/topostext_tag_review.csv \
    --re-candidates-csv exports/topostext_re_candidates.csv \
    --summary-json exports/topostext_review_summary.json \
    2>&1 | tee -a "$LOGFILE"

echo "Step 6: Generating ToposText snapshot history..." | tee -a "$LOGFILE"
uv run generate_topostext_history_page.py \
    --output exports/topostext_history.html \
    --changesets-csv exports/topostext_history_changesets.csv \
    --transitions-csv exports/topostext_history_transitions.csv \
    --entry-history-csv exports/topostext_history_entries.csv \
    --summary-json exports/topostext_history_summary.json \
    2>&1 | tee -a "$LOGFILE"

echo "Step 7: Generating ToposText authority status worklists..." | tee -a "$LOGFILE"
uv run generate_topostext_authority_status_page.py \
    --output exports/topostext_authority_status.html \
    --re-candidates-csv exports/topostext_unmatched_re_candidates.csv \
    --ethnic-suggestions-csv exports/topostext_ethnic_suggestions.csv \
    --new-ids-csv exports/topostext_new_id_worklist.csv \
    --recent-changes-csv exports/topostext_recent_entity_changes.csv \
    --summary-json exports/topostext_authority_status_summary.json \
    2>&1 | tee -a "$LOGFILE"

echo "Step 8: Deploying ToposText outputs to merah..." | tee -a "$LOGFILE"
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
        rsync -az "$topostext_export" "$deploy_target" 2>&1 | tee -a "$LOGFILE"
    fi
done

echo "ToposText pipeline completed: $(date)" | tee -a "$LOGFILE"
