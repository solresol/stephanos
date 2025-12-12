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

echo "========================================" | tee -a "$LOGFILE"
echo "Pipeline run: $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# Step 1: Process images with gpt-5-mini (no limit, will stop at daily token limit)
echo "Step 1: Processing images with gpt-5-mini..." | tee -a "$LOGFILE"
uv run batch_process.py \
    --image-dir /Users/gregb/Downloads/OEBPS \
    --delay 1 \
    2>&1 | tee -a "$LOGFILE"

# Step 2: Translate lemmas with gpt-5.1
echo "Step 2: Translating lemmas with gpt-5.1..." | tee -a "$LOGFILE"
uv run translate_lemmas.py \
    --delay 1 \
    2>&1 | tee -a "$LOGFILE"

# Step 3: Generate progress website
echo "Step 3: Generating progress website..." | tee -a "$LOGFILE"
uv run generate_progress_site.py 2>&1 | tee -a "$LOGFILE"

# Step 4: Generate reference website
echo "Step 4: Generating reference website..." | tee -a "$LOGFILE"
uv run generate_reference_site.py 2>&1 | tee -a "$LOGFILE"

# Step 5: Deploy to merah
echo "Step 5: Deploying to merah..." | tee -a "$LOGFILE"
rsync -avz progress.html stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"
rsync -avz reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/ 2>&1 | tee -a "$LOGFILE"

echo "Pipeline complete: $(date)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"
