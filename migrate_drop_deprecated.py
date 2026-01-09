#!/usr/bin/env python3
"""
Drop deprecated JSON columns after verifying migration is complete.

This migration removes:
1. assembled_lemmas.translation_json (replaced by translation column)
2. assembled_lemmas.assembled_json (completely redundant)
3. assembled_lemmas.source_image_ids (replaced by lemma_images junction table)

IMPORTANT: Only run this after verifying all scripts work with the new schema!
"""
from db import get_connection


def verify_migration(cur):
    """Verify the migration is complete before dropping columns."""
    print("Verifying migration completeness...")

    # Check translation column has data
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(translation) as with_translation,
            COUNT(translation_json) as with_json
        FROM assembled_lemmas
        WHERE translated = 1
    """)
    row = cur.fetchone()
    print(f"  Translated lemmas: {row[0]} total, {row[1]} with translation column, {row[2]} with translation_json")

    if row[1] < row[2]:
        print(f"  WARNING: {row[2] - row[1]} lemmas have translation_json but no translation column!")
        return False

    # Check junction table has all entries
    cur.execute("SELECT COUNT(*) FROM lemma_images")
    junction_count = cur.fetchone()[0]
    cur.execute("""
        SELECT SUM(json_array_length(source_image_ids::json))
        FROM assembled_lemmas
        WHERE source_image_ids IS NOT NULL
    """)
    expected_count = cur.fetchone()[0] or 0
    print(f"  Junction table: {junction_count} entries, expected {expected_count}")

    if junction_count < expected_count:
        print(f"  WARNING: Junction table missing {expected_count - junction_count} entries!")
        return False

    print("  All verifications passed!")
    return True


def drop_deprecated_columns(cur):
    """Drop the deprecated columns."""
    print("\nDropping deprecated columns...")

    # Drop translation_json
    print("  Dropping translation_json...")
    cur.execute("ALTER TABLE assembled_lemmas DROP COLUMN IF EXISTS translation_json")

    # Drop assembled_json
    print("  Dropping assembled_json...")
    cur.execute("ALTER TABLE assembled_lemmas DROP COLUMN IF EXISTS assembled_json")

    # Drop source_image_ids
    print("  Dropping source_image_ids...")
    cur.execute("ALTER TABLE assembled_lemmas DROP COLUMN IF EXISTS source_image_ids")

    # Drop the old unique index that depended on source_image_ids
    print("  Dropping old indexes...")
    cur.execute("DROP INDEX IF EXISTS assembled_lemmas_composite_version_idx")

    # Create new unique index using junction table relationship
    # (Actually we probably need a different approach here - the unique constraint
    # should be based on the actual lemma content, not source IDs)
    print("  Note: Unique constraint strategy needs review - source_image_ids was used for deduplication")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Drop deprecated JSON columns")
    parser.add_argument("--force", action="store_true",
                       help="Drop columns even if verification fails")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    verified = verify_migration(cur)

    if not verified and not args.force:
        print("\nMigration verification failed. Use --force to drop columns anyway.")
        conn.close()
        return

    if not verified:
        print("\nWARNING: Proceeding despite verification failure (--force used)")

    # Confirm before proceeding
    print("\n" + "=" * 60)
    print("WARNING: This will permanently drop the following columns:")
    print("  - assembled_lemmas.translation_json")
    print("  - assembled_lemmas.assembled_json")
    print("  - assembled_lemmas.source_image_ids")
    print("=" * 60)

    response = input("\nType 'yes' to proceed: ")
    if response.strip().lower() != 'yes':
        print("Aborted.")
        conn.close()
        return

    drop_deprecated_columns(cur)
    conn.commit()
    conn.close()

    print("\nDeprecated columns dropped successfully!")
    print("Note: You may need to create a new unique constraint based on lemma content.")


if __name__ == "__main__":
    main()
