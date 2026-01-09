#!/usr/bin/env python3
"""
Add Wikidata linking columns to proper_nouns table.
"""
from db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    print("Adding Wikidata columns to proper_nouns table...")

    # Add wikidata_qid column for Wikidata Q-codes
    cur.execute("""
        ALTER TABLE proper_nouns
        ADD COLUMN IF NOT EXISTS wikidata_qid TEXT
    """)

    # Add disambiguation confidence (how confident we are in the match)
    cur.execute("""
        ALTER TABLE proper_nouns
        ADD COLUMN IF NOT EXISTS wikidata_confidence TEXT
        CHECK (wikidata_confidence IN ('high', 'medium', 'low', 'ambiguous', 'not_found'))
    """)

    # Add timestamp for when the Wikidata linking was done
    cur.execute("""
        ALTER TABLE proper_nouns
        ADD COLUMN IF NOT EXISTS wikidata_linked_at TIMESTAMPTZ
    """)

    # Add index for quick lookup by Wikidata QID
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_proper_nouns_wikidata_qid
        ON proper_nouns(wikidata_qid)
        WHERE wikidata_qid IS NOT NULL
    """)

    conn.commit()
    conn.close()

    print("Migration complete!")
    print("New columns added:")
    print("  - wikidata_qid: Wikidata Q-code (e.g., Q42)")
    print("  - wikidata_confidence: high/medium/low/ambiguous/not_found")
    print("  - wikidata_linked_at: timestamp of linking")


if __name__ == "__main__":
    migrate()
