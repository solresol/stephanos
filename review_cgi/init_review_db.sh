#!/bin/bash
# Initialize SQLite review database on merah
# This script should be run on merah as the apache user

set -e

DB_DIR="/var/www/vhosts/stephanos.symmachus.org/db"
DB_FILE="$DB_DIR/reviews.db"
SCHEMA_FILE="$(dirname "$0")/init_schema.sql"

echo "Initializing review database..."

# Create database directory if it doesn't exist
if [ ! -d "$DB_DIR" ]; then
    echo "Creating database directory: $DB_DIR"
    mkdir -p "$DB_DIR"
fi

# Initialize database with schema
if [ -f "$DB_FILE" ]; then
    echo "WARNING: Database already exists at $DB_FILE"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
    rm "$DB_FILE"
fi

echo "Creating database: $DB_FILE"
sqlite3 "$DB_FILE" < "$SCHEMA_FILE"

# Set proper permissions
chmod 664 "$DB_FILE"
chown apache:apache "$DB_FILE" 2>/dev/null || echo "Warning: Could not set ownership (run as root/sudo)"

echo "Database initialized successfully!"
echo "Location: $DB_FILE"
sqlite3 "$DB_FILE" "SELECT COUNT(*) as table_count FROM sqlite_master WHERE type='table';"
