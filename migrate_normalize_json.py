#!/usr/bin/env python3
"""
Normalize JSON columns in the database to proper relational schema.

This migration:
1. Adds 'translation' column to assembled_lemmas (extracts from translation_json)
2. Creates lemma_images junction table (normalizes source_image_ids)
3. Migrates existing data from JSON columns
4. Keeps old columns initially for verification, marks them deprecated

After verification, a follow-up migration can drop the deprecated columns.
"""
import json
from db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    print("=" * 60)
    print("PHASE 1: Add new normalized columns")
    print("=" * 60)

    # Add translation column
    print("Adding 'translation' column to assembled_lemmas...")
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS translation TEXT
    """)

    # Create lemma_images junction table
    print("Creating lemma_images junction table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lemma_images (
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
            position INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (lemma_id, image_id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lemma_images_lemma_id ON lemma_images(lemma_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lemma_images_image_id ON lemma_images(image_id)
    """)

    conn.commit()
    print("Phase 1 complete.\n")

    print("=" * 60)
    print("PHASE 2: Migrate translation_json -> translation column")
    print("=" * 60)

    # Get all rows with translation_json
    cur.execute("""
        SELECT id, translation_json
        FROM assembled_lemmas
        WHERE translation_json IS NOT NULL
          AND translation IS NULL
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} rows with translation_json to migrate")

    migrated_translations = 0
    failed_translations = 0
    for lemma_id, translation_json in rows:
        try:
            data = json.loads(translation_json)
            translation = data.get("translation") or data.get("english_translation") or ""
            if translation:
                cur.execute(
                    "UPDATE assembled_lemmas SET translation = %s WHERE id = %s",
                    (translation, lemma_id)
                )
                migrated_translations += 1
        except json.JSONDecodeError:
            failed_translations += 1
            print(f"  Failed to parse translation_json for lemma_id={lemma_id}")

    conn.commit()
    print(f"Migrated {migrated_translations} translations, {failed_translations} failures\n")

    print("=" * 60)
    print("PHASE 3: Migrate source_image_ids -> lemma_images junction table")
    print("=" * 60)

    # Get all rows with source_image_ids
    cur.execute("""
        SELECT id, source_image_ids
        FROM assembled_lemmas
        WHERE source_image_ids IS NOT NULL
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} rows with source_image_ids to migrate")

    # Check what's already migrated
    cur.execute("SELECT COUNT(*) FROM lemma_images")
    existing_count = cur.fetchone()[0]
    print(f"Existing entries in lemma_images: {existing_count}")

    migrated_links = 0
    failed_links = 0
    skipped_duplicates = 0
    for lemma_id, source_image_ids in rows:
        try:
            image_ids = json.loads(source_image_ids)
            if isinstance(image_ids, list):
                for position, image_id in enumerate(image_ids):
                    try:
                        cur.execute(
                            """
                            INSERT INTO lemma_images (lemma_id, image_id, position)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (lemma_id, image_id) DO NOTHING
                            """,
                            (lemma_id, image_id, position)
                        )
                        if cur.rowcount > 0:
                            migrated_links += 1
                        else:
                            skipped_duplicates += 1
                    except Exception as e:
                        failed_links += 1
                        print(f"  Failed to insert link lemma_id={lemma_id}, image_id={image_id}: {e}")
        except json.JSONDecodeError:
            failed_links += 1
            print(f"  Failed to parse source_image_ids for lemma_id={lemma_id}")

    conn.commit()
    print(f"Migrated {migrated_links} links, skipped {skipped_duplicates} duplicates, {failed_links} failures\n")

    print("=" * 60)
    print("PHASE 4: Verification")
    print("=" * 60)

    # Verify translations
    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE translation_json IS NOT NULL AND translation IS NOT NULL
    """)
    verified_translations = cur.fetchone()[0]
    print(f"Lemmas with both translation_json and translation: {verified_translations}")

    # Verify junction table
    cur.execute("SELECT COUNT(*) FROM lemma_images")
    total_links = cur.fetchone()[0]
    print(f"Total entries in lemma_images: {total_links}")

    # Compare with source_image_ids counts
    cur.execute("""
        SELECT SUM(
            json_array_length(source_image_ids::json)
        ) FROM assembled_lemmas
        WHERE source_image_ids IS NOT NULL
    """)
    expected_links = cur.fetchone()[0] or 0
    print(f"Expected links from source_image_ids: {expected_links}")

    if total_links == expected_links:
        print("✓ Junction table migration verified!")
    else:
        print(f"⚠ Mismatch: junction table has {total_links}, expected {expected_links}")

    # Add comments to mark deprecated columns
    print("\nAdding deprecation comments to old columns...")
    cur.execute("""
        COMMENT ON COLUMN assembled_lemmas.translation_json IS
        'DEPRECATED: Use translation column instead. Will be removed in future migration.'
    """)
    cur.execute("""
        COMMENT ON COLUMN assembled_lemmas.assembled_json IS
        'DEPRECATED: All fields are available as columns. Will be removed in future migration.'
    """)
    cur.execute("""
        COMMENT ON COLUMN assembled_lemmas.source_image_ids IS
        'DEPRECATED: Use lemma_images junction table instead. Will be removed in future migration.'
    """)

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print("""
Next steps:
1. Update translate_lemmas.py to use tool calling and write to 'translation' column
2. Update assemble_lemmas.py to use lemma_images junction table
3. Update generate_reference_site.py to read from new columns/tables
4. After verification, run migrate_drop_deprecated.py to remove old columns
""")


if __name__ == "__main__":
    migrate()
