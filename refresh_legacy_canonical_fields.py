#!/usr/bin/env python3
"""
Refresh legacy assembled_lemmas translation fields from canonical publication pointers.

This keeps legacy scripts operational while canonical variant storage moves to
lemma_publication_targets + translation_runs/human_translations.
"""
from db import get_connection


def fetch_canonical_rows(cur):
    cur.execute(
        """
        SELECT
            lpt.lemma_id,
            lpt.variant_kind,
            lpt.variant_id
        FROM lemma_publication_targets lpt
        WHERE lpt.surface = 'public_translation'
        ORDER BY lpt.lemma_id
        """
    )
    return cur.fetchall()


def resolve_translation_text(cur, variant_kind: str, variant_id: str):
    if variant_kind == "translation_run":
        cur.execute(
            """
            SELECT COALESCE(translation_text, ''), COALESCE(status, '')
            FROM translation_runs
            WHERE id = %s
            LIMIT 1
            """,
            (variant_id,),
        )
        row = cur.fetchone()
        return row if row else ("", "")

    if variant_kind == "human_translation":
        cur.execute(
            """
            SELECT COALESCE(translation_text, ''), COALESCE(status, '')
            FROM human_translations
            WHERE id = %s
            LIMIT 1
            """,
            (variant_id,),
        )
        row = cur.fetchone()
        return row if row else ("", "")

    if variant_kind == "legacy_assembled":
        cur.execute(
            """
            SELECT COALESCE(translation, ''), 'approved'
            FROM assembled_lemmas
            WHERE id = %s
            LIMIT 1
            """,
            (variant_id,),
        )
        row = cur.fetchone()
        return row if row else ("", "")

    return "", ""


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.lemma_publication_targets') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        print("lemma_publication_targets table missing; nothing to refresh.")
        conn.close()
        return

    rows = fetch_canonical_rows(cur)
    updated = 0
    for lemma_id, variant_kind, variant_id in rows:
        text, status = resolve_translation_text(cur, variant_kind, variant_id)
        if not (text or "").strip():
            continue

        if variant_kind == "human_translation":
            reviewed_value = text if status == "approved" else None
            corrected_value = text
        else:
            reviewed_value = None
            corrected_value = None

        cur.execute(
            """
            UPDATE assembled_lemmas
            SET translation = %s,
                corrected_english_translation = COALESCE(%s, corrected_english_translation),
                reviewed_english_translation = COALESCE(%s, reviewed_english_translation),
                translated = 1,
                translated_at = COALESCE(translated_at, NOW()),
                updated_at = NOW()
            WHERE id = %s
            """,
            (text, corrected_value, reviewed_value, lemma_id),
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"Refreshed legacy canonical fields for {updated} lemmas.")


if __name__ == "__main__":
    main()
