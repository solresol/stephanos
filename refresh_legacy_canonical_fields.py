#!/usr/bin/env python3
"""
Refresh legacy assembled_lemmas translation fields from canonical publication pointers.

This keeps legacy scripts operational while canonical variant storage moves to
lemma_canonical_variants + translation_runs/human_translations.
"""
from db import get_connection
import canonical_variants


def fetch_lemma_ids_with_canonical_memberships(cur) -> list[int]:
    cur.execute(
        """
        SELECT DISTINCT lemma_id
        FROM lemma_canonical_variants
        WHERE is_active = TRUE
        ORDER BY lemma_id
        """
    )
    return [int(row[0]) for row in cur.fetchall()]


def main():
    conn = get_connection()
    cur = conn.cursor()

    if not canonical_variants.table_exists(cur, "lemma_canonical_variants"):
        print("lemma_canonical_variants table missing; nothing to refresh.")
        conn.close()
        return

    lemma_ids = fetch_lemma_ids_with_canonical_memberships(cur)
    updated = 0
    for lemma_id in lemma_ids:
        choice = canonical_variants.select_pointer_variant(cur, lemma_id=lemma_id)
        if not choice:
            continue

        text = (choice.get("translation_text") or "").strip()
        if not (text or "").strip():
            continue

        variant_kind = choice.get("kind", "") or ""
        status = choice.get("status", "") or ""
        if variant_kind == "human_translation":
            reviewed_value = text if (status or "").strip() == "approved" else None
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
