#!/bin/bash
# Sync review database from merah to raksasa
# This script pulls the SQLite database containing human review data

set -e

REVIEW_DIR="$HOME/stephanos/review_data"
REMOTE_DB="/var/www/vhosts/stephanos.symmachus.org/db/reviews.db"
LOCAL_DB="$REVIEW_DIR/reviews.db"
LOG_FILE="$HOME/stephanos/logs/review_sync.log"

# Create directories
mkdir -p "$REVIEW_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Starting review database sync ==="

# Check if remote database exists
if ! ssh stephanos@merah.cassia.ifost.org.au "test -f $REMOTE_DB"; then
    log "WARNING: Remote database does not exist yet: $REMOTE_DB"
    log "This is normal if the review system hasn't been deployed yet."
    exit 0
fi

# Get remote database size
REMOTE_SIZE=$(ssh stephanos@merah.cassia.ifost.org.au "ls -lh $REMOTE_DB | awk '{print \$5}'")
log "Remote database size: $REMOTE_SIZE"

# Pull database from merah
log "Pulling database from merah..."
scp stephanos@merah.cassia.ifost.org.au:"$REMOTE_DB" "$LOCAL_DB"

if [ $? -eq 0 ]; then
    LOCAL_SIZE=$(ls -lh "$LOCAL_DB" | awk '{print $5}')
    log "Successfully synced database (local size: $LOCAL_SIZE)"

    # Quick sanity check - count reviews
    REVIEW_COUNT=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(*) FROM reviews WHERE review_status != 'not_reviewed';")
    log "Reviews in database: $REVIEW_COUNT reviewed entries"
else
    log "ERROR: Failed to sync database"
    exit 1
fi

log "=== Review database sync complete ==="
