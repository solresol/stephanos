#!/bin/bash
# Backup SQLite review database on merah
# This script should be run on merah to create daily backups

set -e

BACKUP_DIR="$HOME/backups/review_db"
DB_PATH="/var/www/vhosts/stephanos.symmachus.org/db/reviews.db"
DATE=$(date +%Y%m%d)
BACKUP_FILE="$BACKUP_DIR/reviews_${DATE}.db"
LOG_FILE="$HOME/stephanos/logs/review_backup.log"

# Create directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Starting review database backup ==="

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Database not found: $DB_PATH"
    exit 1
fi

# Get database size
DB_SIZE=$(ls -lh "$DB_PATH" | awk '{print $5}')
log "Database size: $DB_SIZE"

# Create backup (using sqlite3 .backup for safe copying)
log "Creating backup: $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    log "Backup created successfully (size: $BACKUP_SIZE)"

    # Quick sanity check
    REVIEW_COUNT=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM reviews WHERE review_status != 'not_reviewed';" 2>/dev/null || echo "0")
    log "Reviews in backup: $REVIEW_COUNT reviewed entries"
else
    log "ERROR: Backup failed"
    exit 1
fi

# Remove backups older than 7 days
log "Cleaning up old backups (keeping 7 days)..."
find "$BACKUP_DIR" -name "reviews_*.db" -mtime +7 -delete
REMAINING=$(find "$BACKUP_DIR" -name "reviews_*.db" | wc -l | tr -d ' ')
log "Backups remaining: $REMAINING"

log "=== Review database backup complete ==="
