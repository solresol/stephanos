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
DATE=$(date +%Y%m%d)

echo "========================================" | tee -a "$LOGFILE"
echo "Pipeline run: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# Step 0: Git pull to get latest instructions/code
echo "Step 0: Pulling latest changes from git..." | tee -a "$LOGFILE"
if git diff --quiet && git diff --cached --quiet; then
    git pull 2>&1 | tee -a "$LOGFILE" || echo "Git pull failed (continuing anyway)" | tee -a "$LOGFILE"
else
    echo "Git working tree has local changes; skipping git pull" | tee -a "$LOGFILE"
fi

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

# Step 2b: Queue missing Meineke page scans based on headword hole detection
echo "Step 2b: Queueing missing Meineke hole pages..." | tee -a "$LOGFILE"
uv run enqueue_meineke_holes.py --image-dir pdf_pages_meineke 2>&1 | tee -a "$LOGFILE"

# Step 3: Retire finished Billerbeck OCR step
echo "Step 3: Skipping Billerbeck OCR (OCR corpus complete)." | tee -a "$LOGFILE"

# Step 3b: Process queued Meineke images with line/apparatus OCR
echo "Step 3b: Processing Meineke images..." | tee -a "$LOGFILE"
uv run process_meineke_pages.py --delay 1 2>&1 | tee -a "$LOGFILE"

# Step 4: Assemble lemmas across pages (handles continuations and human overrides)
echo "Step 4: Assembling lemmas..." | tee -a "$LOGFILE"
uv run assemble_lemmas.py 2>&1 | tee -a "$LOGFILE"

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

# Step 4d3: Backfill authoritative translation runs from compatibility columns
echo "Step 4d3: Backfilling authoritative translation runs..." | tee -a "$LOGFILE"
uv run backfill_legacy_translation_runs.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: translation backfill failed" | tee -a "$LOGFILE"

# Step 4e: Enqueue translation run requests (set TRANSLATION_ENQUEUE_LIMIT=0 to disable)
TRANSLATION_ENQUEUE_LIMIT="${TRANSLATION_ENQUEUE_LIMIT:-20}"
if [ "$TRANSLATION_ENQUEUE_LIMIT" -gt 0 ]; then
    echo "Step 4e: Enqueuing translation run requests..." | tee -a "$LOGFILE"
    uv run enqueue_translation_runs.py \
        --profile legacy_scholarly \
        --source-document billerbeck \
        --limit "$TRANSLATION_ENQUEUE_LIMIT" \
        --repeat 1 \
        2>&1 | tee -a "$LOGFILE" || echo "  Warning: enqueue step failed" | tee -a "$LOGFILE"
fi

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

# Step 5b2: Extract structured source-citation units (author+work+book)
SOURCE_CITATION_EXTRACT_MODEL="${SOURCE_CITATION_EXTRACT_MODEL:-gpt-5-mini}"
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

# Step 5e: Extract aliases from Greek text (limit to 20 per day to control costs)
echo "Step 5e: Extracting aliases from Greek text..." | tee -a "$LOGFILE"
uv run extract_aliases.py --limit 20 2>&1 | tee -a "$LOGFILE"

# Step 5f: Generate spelling variants
echo "Step 5f: Generating spelling variants..." | tee -a "$LOGFILE"
uv run generate_spelling_variants.py 2>&1 | tee -a "$LOGFILE"

# Step 5g: Analyze Meineke/Billerbeck differences with gpt-5-mini (small daily batch)
echo "Step 5g: Analyzing Meineke/Billerbeck differences..." | tee -a "$LOGFILE"
MEINEKE_DIFF_DAILY_TOKEN_LIMIT="${MEINEKE_DIFF_DAILY_TOKEN_LIMIT:-1000000}"
uv run analyze_meineke_differences.py --limit 20 --daily-token-limit "$MEINEKE_DIFF_DAILY_TOKEN_LIMIT" --delay 1 2>&1 | tee -a "$LOGFILE"

# Step 5g2: Sync versioned text-pair differences from current source versions
echo "Step 5g2: Syncing text-pair differences..." | tee -a "$LOGFILE"
uv run sync_text_pair_differences.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: text-pair differences sync failed" | tee -a "$LOGFILE"

# Step 5h: Sync translation risk flags (blocks likely translation-changing Billerbeck-dependent rows)
echo "Step 5h: Syncing translation risk flags..." | tee -a "$LOGFILE"
uv run sync_translation_risk_flags.py 2>&1 | tee -a "$LOGFILE"

# Step 5i: Refresh legacy canonical fields from publication pointers
echo "Step 5i: Refreshing legacy canonical fields..." | tee -a "$LOGFILE"
uv run refresh_legacy_canonical_fields.py 2>&1 | tee -a "$LOGFILE" || echo "  Warning: legacy canonical refresh failed" | tee -a "$LOGFILE"

# Step 5j: Sync review database from merah before site generation
echo "Step 5j: Syncing review database from merah..." | tee -a "$LOGFILE"
./sync_review_db.sh 2>&1 | tee -a "$LOGFILE" || echo "  Warning: Failed to sync review database" | tee -a "$LOGFILE"

# Step 5k: Import reviews into PostgreSQL before site generation
echo "Step 5k: Importing reviews into PostgreSQL..." | tee -a "$LOGFILE"
uv run import_reviews.py 2>&1 | tee -a "$LOGFILE"

# Step 5l: Sync with nodegoat before progress/site generation
echo "Step 5l: Syncing with nodegoat..." | tee -a "$LOGFILE"
uv run sync_nodegoat.py --push --catch-up --limit 20 2>&1 | tee -a "$LOGFILE" || echo "  Warning: nodegoat sync failed" | tee -a "$LOGFILE"

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
uv run generate_meineke_difference_analysis_page.py 2>&1 | tee -a "$LOGFILE"

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

# Step 8b: Export lemma data for review interface
echo "Step 8b: Exporting lemma data for review interface..." | tee -a "$LOGFILE"
uv run export_for_review.py 2>&1 | tee -a "$LOGFILE"

# Step 9: Deploy to merah
echo "Step 9: Deploying to merah..." | tee -a "$LOGFILE"
# Deploy reference_site/ (contains statistics.html, statistics/, statistics_images/, people.html, and all lemma pages)
rsync -az reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy progress.html (kept at root for backwards compatibility)
rsync -az progress.html stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy CSV exports
rsync -az exports/lemmas.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -az exports/proper_nouns.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -az exports/etymologies.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -az exports/source_citation_units.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -az exports/source_citation_mentions.csv stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
# Deploy nodegoat exports
rsync -az exports/nodegoat/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/nodegoat/ 2>&1 | tee -a "$LOGFILE"
# Deploy review data JSON
rsync -az review_data.json stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/ 2>&1 | tee -a "$LOGFILE"
# Deploy review CGI binaries from current source
./review_cgi/deploy_review_cgi.sh 2>&1 | tee -a "$LOGFILE" || echo "  Warning: review CGI deploy failed" | tee -a "$LOGFILE"

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
rsync -az backups/stephanos_${DATE}.sql.gz ${BACKUP_DIR}/ 2>&1 | tee -a "$LOGFILE"

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
