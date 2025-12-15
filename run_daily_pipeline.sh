#!/bin/bash
#
# Daily pipeline script for Stephanos processing
# Run this via cron to automate the entire workflow
#

set -e

# Change to project directory
cd "$(dirname "$0")"

# Log file
LOGFILE="pipeline.log"
DATE=$(date +%Y%m%d)

echo "========================================" | tee -a "$LOGFILE"
echo "Pipeline run: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# Step 0: Git pull to get latest instructions/code
echo "Step 0: Pulling latest changes from git..." | tee -a "$LOGFILE"
git pull 2>&1 | tee -a "$LOGFILE" || echo "Git pull failed (continuing anyway)" | tee -a "$LOGFILE"

# Step 1: Process any new EPUB files in home directory
echo "Step 1: Extracting new EPUB files..." | tee -a "$LOGFILE"
for epub in ~/*.epub; do
    if [ -f "$epub" ]; then
        echo "  Processing: $epub" | tee -a "$LOGFILE"
        uv run extract_epub.py "$epub" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to process $epub" | tee -a "$LOGFILE"
    fi
done

# Step 2: Extract images from unprocessed HTML files
echo "Step 2: Extracting images from HTML files..." | tee -a "$LOGFILE"
uv run extract_images_to_postgres.py --from-db 2>&1 | tee -a "$LOGFILE"

# Step 3: Process images with gpt-5 (no limit, will stop at daily token limit)
echo "Step 3: Processing images with gpt-5..." | tee -a "$LOGFILE"
uv run batch_process.py \
    --delay 1 \
    2>&1 | tee -a "$LOGFILE"

# Step 4: Assemble lemmas across pages (handles continuations and human overrides)
echo "Step 4: Assembling lemmas..." | tee -a "$LOGFILE"
uv run assemble_lemmas.py 2>&1 | tee -a "$LOGFILE"

# Step 5: Translate lemmas with gpt-5.1
echo "Step 5: Translating lemmas with gpt-5.1..." | tee -a "$LOGFILE"
uv run translate_lemmas.py \
    --delay 1 \
    2>&1 | tee -a "$LOGFILE"

# Step 6: Generate progress website
echo "Step 6: Generating progress website..." | tee -a "$LOGFILE"
uv run generate_progress_site.py 2>&1 | tee -a "$LOGFILE"

# Step 7: Generate reference website
echo "Step 7: Generating reference website..." | tee -a "$LOGFILE"
uv run generate_reference_site.py 2>&1 | tee -a "$LOGFILE"

# Step 8: Export lemmas CSV
echo "Step 8: Exporting lemmas CSV..." | tee -a "$LOGFILE"
uv run generate_csv_export.py --output exports/lemmas.csv 2>&1 | tee -a "$LOGFILE"

# Step 9: Deploy to merah
echo "Step 9: Deploying to merah..." | tee -a "$LOGFILE"
rsync -avz progress.html stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -avz reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -avz exports/lemmas.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"

# Step 10: Backup database with rolling history
echo "Step 10: Backing up database..." | tee -a "$LOGFILE"
BACKUP_DIR="stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos"
DB_PATH="$HOME/stephanos.db"

# Create dated backup
BACKUP_NAME="stephanos_${DATE}.db"
scp "$DB_PATH" "${BACKUP_DIR}/${BACKUP_NAME}" 2>&1 | tee -a "$LOGFILE"

# Also copy as 'latest' for convenience
scp "$DB_PATH" "${BACKUP_DIR}/stephanos_latest.db" 2>&1 | tee -a "$LOGFILE"

# Remove backups older than 7 days (keep rolling history)
echo "  Cleaning up old backups (keeping last 7 days)..." | tee -a "$LOGFILE"
ssh stephanos@merah.cassia.ifost.org.au "find /var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos -name 'stephanos_*.db' -mtime +7 -delete" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to cleanup old backups" | tee -a "$LOGFILE"

echo "Pipeline complete: $(date)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"
