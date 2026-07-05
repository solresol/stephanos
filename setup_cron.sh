#!/bin/bash
# Setup cron jobs for Stephanos review system automation
#
# DEPRECATED (2026-07-05): superseded by run_daily_pipeline.sh (the single daily
# orchestrator). This granular installer set up a divergent job set that never
# calls run_daily_pipeline.sh, and it included a public database-dump upload and
# an `rsync --delete` deploy that could wipe htdocs. It now refuses to run.
# See docs/architecture/JOBS.md and docs/architecture/ANOMALIES.md (P-01/S-01/S-02).
echo "setup_cron.sh is DEPRECATED and disabled." >&2
echo "Use the daily orchestrator instead: run_daily_pipeline.sh" >&2
echo "See docs/architecture/JOBS.md" >&2
exit 1

CRON_FILE="/tmp/stephanos_cron.txt"
STEPHANOS_DIR="$HOME/stephanos"

cat > "$CRON_FILE" <<'EOF'
# Stephanos Review System - Daily Pipeline
# Runs at 1 AM daily
#
# Cron mail should land in the stephanos mailbox on merah, where .forward keeps
# local delivery for automations and forwards a copy to gregb@ifost.org.au.
MAILTO=stephanos@merah.cassia.ifost.org.au

# 1. Export lemma data for review interface (1:00 AM)
0 1 * * * cd ~/stephanos && uv run export_for_review.py && uv run export_guidance_scan_db.py && rsync review_data.sqlite guidance_scan_results.db stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/ >> logs/export_for_review.log 2>&1

# 2. Sync review database from merah (2:00 AM)
0 2 * * * ~/stephanos/sync_review_db.sh

# 3. Import reviews into PostgreSQL (2:10 AM)
10 2 * * * cd ~/stephanos && uv run import_reviews.py >> logs/review_import.log 2>&1

# 4. Regenerate websites with corrections (2:20 AM)
20 2 * * * cd ~/stephanos && uv run generate_pipeline_progress.py >> logs/pipeline_site.log 2>&1
25 2 * * * cd ~/stephanos && uv run generate_reference_site.py >> logs/reference_site.log 2>&1

# 5. Deploy websites to merah (2:30 AM)
# NOTE: --delete removed — htdocs also holds CSVs, nodegoat/, the PDF, and
# ToposText exports deployed by other steps, which --delete would wipe.
30 2 * * * rsync -avz ~/stephanos/reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ >> logs/deploy_site.log 2>&1

# 6. Backup review database on merah (2:45 AM, keep 7 days)
45 2 * * * ssh stephanos@merah.cassia.ifost.org.au "bash ~/stephanos/backup_review_db.sh"

# 7. Backup PostgreSQL database (3:00 AM, keep 7 days)
0 3 * * * pg_dump -U stephanos stephanos | gzip > ~/stephanos/backups/stephanos_$(date +\%Y\%m\%d).sql.gz && find ~/stephanos/backups -name "stephanos_*.sql.gz" -mtime +7 -delete

# 8. (REMOVED) Public PostgreSQL-dump upload — this rsynced the full database
#    dump to a public web docroot (datadumps.ifost.org.au/htdocs). Deliberately
#    deleted; backups stay local only. See ANOMALIES.md S-01.

# 9. Hourly nodegoat sync (small batch to avoid rate limits)
0 * * * * ~/stephanos/nodegoat_hourly_sync.sh >> logs/nodegoat_sync.log 2>&1
EOF

echo "=== Stephanos Cron Job Setup ==="
echo

# Create necessary directories
mkdir -p "$STEPHANOS_DIR/logs"
mkdir -p "$STEPHANOS_DIR/backups"

echo "Created directories:"
echo "  - $STEPHANOS_DIR/logs/"
echo "  - $STEPHANOS_DIR/backups/"
echo

# Show proposed cron jobs
echo "Proposed cron jobs:"
echo "-------------------"
cat "$CRON_FILE"
echo "-------------------"
echo

# Get current crontab
crontab -l > /tmp/current_cron.txt 2>/dev/null || touch /tmp/current_cron.txt

# Check if stephanos jobs already exist
if grep -q "Stephanos Review System" /tmp/current_cron.txt; then
    echo "WARNING: Stephanos cron jobs already exist in crontab"
    echo
    read -p "Remove existing jobs and install new ones? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. No changes made."
        exit 1
    fi

    # Remove existing Stephanos section
    sed -i '/# Stephanos Review System/,/^$/d' /tmp/current_cron.txt
fi

# Append new jobs
cat /tmp/current_cron.txt "$CRON_FILE" | crontab -

echo "✓ Cron jobs installed successfully!"
echo

# Verify installation
echo "Current crontab:"
crontab -l | grep -A 20 "Stephanos Review System"

echo
echo "Cron job schedule:"
echo "  1:00 AM - Export data and sync to merah"
echo "  2:00 AM - Pull review database from merah"
echo "  2:10 AM - Import reviews to PostgreSQL"
echo "  2:20 AM - Regenerate websites"
echo "  2:30 AM - Deploy to merah"
echo "  2:45 AM - Backup review database on merah (7-day retention)"
echo "  3:00 AM - Backup PostgreSQL database (7-day retention)"
echo "  3:10 AM - Upload PostgreSQL backup to merah"
echo "  Hourly - nodegoat sync (small batch)"
echo

# Cleanup
rm -f "$CRON_FILE" /tmp/current_cron.txt

echo "Setup complete!"
echo
echo "Logs will be written to: $STEPHANOS_DIR/logs/"
echo "Database backups saved to: $STEPHANOS_DIR/backups/"
echo
echo "To remove these jobs, run: crontab -e"
echo "  (then delete the '# Stephanos Review System' section)"
