#!/usr/bin/env python3
"""
Add analytics tables and columns to the database.

Adds:
- word_count column to assembled_lemmas
- proper_nouns_analyzed, etymologies_analyzed tracking columns
- proper_nouns table
- etymologies table
"""
from db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    print("Adding columns to assembled_lemmas...")

    # Add word count column
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS word_count INTEGER
    """)

    # Add proper noun analysis tracking
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS proper_nouns_analyzed BOOLEAN DEFAULT FALSE
    """)
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS proper_nouns_analyzed_at TIMESTAMPTZ
    """)

    # Add etymology analysis tracking
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS etymologies_analyzed BOOLEAN DEFAULT FALSE
    """)
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS etymologies_analyzed_at TIMESTAMPTZ
    """)

    print("Creating proper_nouns table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS proper_nouns (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            proper_noun TEXT NOT NULL,
            lemma_form TEXT NOT NULL,
            english_translation TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_proper_nouns_lemma_id
        ON proper_nouns(lemma_id)
    """)

    print("Creating etymologies table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS etymologies (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            greek_text TEXT NOT NULL,
            english_translation TEXT,
            category TEXT NOT NULL CHECK (category IN (
                'EPONYM_PERSON',
                'MORPHOLOGICAL_COMPOSITION',
                'PLACE_TRANSFER',
                'BORROWING_NON_GREEK',
                'FOLK_ETYMOLOGY_NARRATIVE',
                'UNCLEAR_METALINGUISTIC'
            )),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_etymologies_lemma_id
        ON etymologies(lemma_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_etymologies_category
        ON etymologies(category)
    """)

    conn.commit()
    conn.close()

    print("Migration complete!")


if __name__ == "__main__":
    migrate()
