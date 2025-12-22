#!/usr/bin/env python3
"""
Import review data from SQLite (merah) into PostgreSQL (raksasa).

This script reads the reviews.db SQLite database that was pulled from merah
and updates the assembled_lemmas table in PostgreSQL with human corrections.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from db import get_connection

SQLITE_DB = Path.home() / "stephanos" / "review_data" / "reviews.db"
LOG_FILE = Path.home() / "stephanos" / "logs" / "review_import.log"


def log(message):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open('a') as f:
        f.write(log_message + '\n')


def import_reviews():
    """Import reviews from SQLite to PostgreSQL."""
    log("=== Starting review import ===")

    # Check if SQLite database exists
    if not SQLITE_DB.exists():
        log(f"ERROR: SQLite database not found: {SQLITE_DB}")
        log("Run sync_review_db.sh first to pull database from merah")
        return 1

    # Connect to databases
    log(f"Connecting to SQLite: {SQLITE_DB}")
    sqlite_conn = sqlite3.connect(str(SQLITE_DB))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    log("Connecting to PostgreSQL")
    pg_conn = get_connection()
    pg_cur = pg_conn.cursor()

    # Get all reviewed entries from SQLite
    sqlite_cur.execute("""
        SELECT lemma_id, review_status,
               corrected_greek_text, corrected_english_translation,
               reviewer_username, reviewed_at, notes
        FROM reviews
        WHERE review_status != 'not_reviewed'
        ORDER BY reviewed_at
    """)

    reviews = sqlite_cur.fetchall()
    log(f"Found {len(reviews)} reviewed entries in SQLite")

    if len(reviews) == 0:
        log("No reviews to import")
        sqlite_conn.close()
        pg_conn.close()
        return 0

    # Statistics
    updated_count = 0
    skipped_count = 0
    error_count = 0

    # Process each review
    for review in reviews:
        lemma_id = review['lemma_id']
        review_status = review['review_status']
        corrected_greek = review['corrected_greek_text'] or None
        corrected_english = review['corrected_english_translation'] or None
        reviewer = review['reviewer_username']
        reviewed_at = review['reviewed_at']
        notes = review['notes'] or None

        try:
            # Check if lemma exists in PostgreSQL
            pg_cur.execute("SELECT lemma FROM assembled_lemmas WHERE id = %s", (lemma_id,))
            result = pg_cur.fetchone()

            if not result:
                log(f"  WARNING: Lemma ID {lemma_id} not found in PostgreSQL")
                skipped_count += 1
                continue

            lemma_name = result[0]

            # Update PostgreSQL
            update_query = """
                UPDATE assembled_lemmas
                SET review_status = %s,
                    corrected_greek_scan = %s,
                    corrected_english_translation = %s,
                    reviewed_by = %s,
                    reviewed_at = %s,
                    human_notes = %s
                WHERE id = %s
            """

            pg_cur.execute(update_query, (
                review_status,
                corrected_greek,
                corrected_english,
                reviewer,
                reviewed_at,
                notes,
                lemma_id
            ))

            updated_count += 1

            # Log details for reviewed_corrections
            if review_status == 'reviewed_corrections':
                corrections = []
                if corrected_greek:
                    corrections.append("Greek")
                if corrected_english:
                    corrections.append("English")
                if corrections:
                    log(f"  Updated {lemma_name} (ID {lemma_id}): {', '.join(corrections)} corrected by {reviewer}")
                else:
                    log(f"  Updated {lemma_name} (ID {lemma_id}): marked as corrected (no text changes)")

        except Exception as e:
            log(f"  ERROR processing lemma ID {lemma_id}: {e}")
            error_count += 1
            continue

    # Commit changes
    pg_conn.commit()

    # Close connections
    sqlite_conn.close()
    pg_conn.close()

    # Summary
    log(f"=== Import complete ===")
    log(f"  Updated: {updated_count}")
    log(f"  Skipped: {skipped_count}")
    log(f"  Errors: {error_count}")

    if error_count > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(import_reviews())
