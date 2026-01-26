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

# Step 5: Translate lemmas with gpt-5.2
echo "Step 5: Translating lemmas with gpt-5.2..." | tee -a "$LOGFILE"
uv run translate_lemmas.py \
    --delay 1 \
    2>&1 | tee -a "$LOGFILE"

# Step 5a: Count words in Greek text
echo "Step 5a: Counting words in Greek text..." | tee -a "$LOGFILE"
uv run count_words.py 2>&1 | tee -a "$LOGFILE"

# Step 5b: Extract proper nouns
echo "Step 5b: Extracting proper nouns..." | tee -a "$LOGFILE"
uv run extract_proper_nouns.py 2>&1 | tee -a "$LOGFILE"

# Step 5c: Extract etymologies
echo "Step 5c: Extracting etymologies..." | tee -a "$LOGFILE"
uv run extract_etymologies.py 2>&1 | tee -a "$LOGFILE"

# Step 5d: Link proper nouns to Wikidata (limit to 20 per day to control costs)
echo "Step 5d: Linking sources to Wikidata..." | tee -a "$LOGFILE"
uv run link_wikidata.py --limit 20 2>&1 | tee -a "$LOGFILE"

# Step 5d2: Link place headwords to Wikidata (limit to 10 per day to control costs)
echo "Step 5d2: Linking places to Wikidata..." | tee -a "$LOGFILE"
uv run link_wikidata_places.py --limit 10 2>&1 | tee -a "$LOGFILE"

# Step 5e: Extract aliases from Greek text (limit to 20 per day to control costs)
echo "Step 5e: Extracting aliases from Greek text..." | tee -a "$LOGFILE"
uv run extract_aliases.py --limit 20 2>&1 | tee -a "$LOGFILE"

# Step 5f: Generate spelling variants
echo "Step 5f: Generating spelling variants..." | tee -a "$LOGFILE"
uv run generate_spelling_variants.py 2>&1 | tee -a "$LOGFILE"

# Step 6: Generate progress website
echo "Step 6: Generating progress website..." | tee -a "$LOGFILE"
uv run generate_progress_site.py 2>&1 | tee -a "$LOGFILE"

# Step 7: Generate reference website
echo "Step 7: Generating reference website..." | tee -a "$LOGFILE"
uv run generate_reference_site.py 2>&1 | tee -a "$LOGFILE"

# Step 7a: Generate statistics website
echo "Step 7a: Generating statistics website..." | tee -a "$LOGFILE"
uv run generate_statistics_site.py 2>&1 | tee -a "$LOGFILE"

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

# Step 7c: Generate protected pages
echo "Step 7c: Generating protected pages..." | tee -a "$LOGFILE"
uv run generate_protected_pages.py 2>&1 | tee -a "$LOGFILE"

# Step 8: Export lemmas CSV
echo "Step 8: Exporting lemmas CSV..." | tee -a "$LOGFILE"
uv run generate_csv_export.py --output exports/lemmas.csv 2>&1 | tee -a "$LOGFILE"

# Step 8a: Export proper nouns CSV
echo "Step 8a: Exporting proper nouns CSV..." | tee -a "$LOGFILE"
uv run export_proper_nouns_csv.py 2>&1 | tee -a "$LOGFILE"

# Step 8a2: Export etymologies CSV
echo "Step 8a2: Exporting etymologies CSV..." | tee -a "$LOGFILE"
uv run export_etymologies_csv.py 2>&1 | tee -a "$LOGFILE"

# Step 8a3: Export for nodegoat
echo "Step 8a3: Exporting for nodegoat..." | tee -a "$LOGFILE"
uv run export_for_nodegoat.py --output exports/nodegoat 2>&1 | tee -a "$LOGFILE"

# Step 8a4: Generate PDF book
echo "Step 8a4: Generating PDF book..." | tee -a "$LOGFILE"
uv run generate_pdf_book.py 2>&1 | tee -a "$LOGFILE"

# Step 8a5: Generate downloads page
echo "Step 8a5: Generating downloads page..." | tee -a "$LOGFILE"
uv run generate_downloads_page.py 2>&1 | tee -a "$LOGFILE"

# Step 8b: Export lemma data for review interface
echo "Step 8b: Exporting lemma data for review interface..." | tee -a "$LOGFILE"
uv run export_for_review.py 2>&1 | tee -a "$LOGFILE"

# Step 8c: Sync review database from merah
echo "Step 8c: Syncing review database from merah..." | tee -a "$LOGFILE"
./sync_review_db.sh 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to sync review database" | tee -a "$LOGFILE"

# Step 8d: Import reviews into PostgreSQL
echo "Step 8d: Importing reviews into PostgreSQL..." | tee -a "$LOGFILE"
uv run import_reviews.py 2>&1 | tee -a "$LOGFILE"

# Step 8e: Sync with nodegoat (push changes, limit to 20 per day for safety)
echo "Step 8e: Syncing with nodegoat..." | tee -a "$LOGFILE"
uv run sync_nodegoat.py --push --catch-up --limit 20 2>&1 | tee -a "$LOGFILE" || echo "  Warning: nodegoat sync failed" | tee -a "$LOGFILE"

# Step 9: Deploy to merah
echo "Step 9: Deploying to merah..." | tee -a "$LOGFILE"
# Deploy reference_site/ (contains statistics.html, statistics/, statistics_images/, people.html, and all lemma pages)
rsync -avz reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy progress.html (kept at root for backwards compatibility)
rsync -avz progress.html stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy CSV exports
rsync -avz exports/lemmas.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -avz exports/proper_nouns.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -avz exports/etymologies.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy nodegoat exports
rsync -avz exports/nodegoat/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/nodegoat/ 2>&1 | tee -a "$LOGFILE"
# Deploy review data JSON
rsync -avz review_data.json stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/ 2>&1 | tee -a "$LOGFILE"

# Step 10: Backup databases with rolling history
echo "Step 10: Backing up databases..." | tee -a "$LOGFILE"
BACKUP_DIR="stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos"

# Backup SQLite database if it exists
if [ -f "$HOME/stephanos.db" ]; then
    echo "  Backing up SQLite database..." | tee -a "$LOGFILE"
    DB_PATH="$HOME/stephanos.db"
    BACKUP_NAME="stephanos_${DATE}.db"
    scp "$DB_PATH" "${BACKUP_DIR}/${BACKUP_NAME}" 2>&1 | tee -a "$LOGFILE"
    scp "$DB_PATH" "${BACKUP_DIR}/stephanos_latest.db" 2>&1 | tee -a "$LOGFILE"
fi

# Backup PostgreSQL database
echo "  Backing up PostgreSQL database..." | tee -a "$LOGFILE"
mkdir -p backups
pg_dump -U stephanos stephanos | gzip > backups/stephanos_${DATE}.sql.gz 2>&1 | tee -a "$LOGFILE"
# Upload PostgreSQL backup to merah
rsync -avz backups/stephanos_${DATE}.sql.gz ${BACKUP_DIR}/ 2>&1 | tee -a "$LOGFILE"

# Backup review database on merah
echo "  Backing up review database on merah..." | tee -a "$LOGFILE"
ssh stephanos@merah.cassia.ifost.org.au "bash ~/stephanos/backup_review_db.sh" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to backup review database" | tee -a "$LOGFILE"

# Remove local backups older than 7 days
echo "  Cleaning up old local backups (keeping last 7 days)..." | tee -a "$LOGFILE"
find backups -name "stephanos_*.sql.gz" -mtime +7 -delete 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to cleanup old local backups" | tee -a "$LOGFILE"

# Remove remote backups older than 7 days (keep rolling history)
echo "  Cleaning up old remote backups (keeping last 7 days)..." | tee -a "$LOGFILE"
ssh stephanos@merah.cassia.ifost.org.au "find /var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos -name 'stephanos_*.db' -o -name 'stephanos_*.sql.gz' -mtime +7 -delete" 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to cleanup old remote backups" | tee -a "$LOGFILE"

echo "Pipeline complete: $(date)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"
