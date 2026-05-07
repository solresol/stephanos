#!/usr/bin/env python3
"""
Remove modern oracle-reference labels from source-citation authors.

Parke, Wormell, and Fontenrose references are preserved in the private
oracle_references index. They should not also appear as ancient authors or
works in source_citation_units.
"""

from __future__ import annotations

import argparse

from db import get_connection


MODERN_ORACLE_AUTHOR_WHERE = """
(
    author_english ILIKE '%Parke%'
    OR author_english ILIKE '%Wormell%'
    OR author_english ILIKE '%Fontenrose%'
    OR author_lemma_form ILIKE '%Παρκε%'
    OR author_lemma_form ILIKE '%Πάρκ%'
    OR author_lemma_form ILIKE '%Οὐόρ%'
    OR author_lemma_form ILIKE '%Φοντεν%'
)
AND (
    raw_unit_text ILIKE '%Parke%'
    OR raw_unit_text ILIKE '%Wormell%'
    OR raw_unit_text ILIKE '%Fontenrose%'
    OR identifiers_json::text ILIKE '%Parke%'
    OR identifiers_json::text ILIKE '%Wormell%'
    OR identifiers_json::text ILIKE '%Fontenrose%'
)
"""


def fetch_targets(cur) -> list[dict]:
    cur.execute(
        f"""
        SELECT
            u.id,
            array_agg(DISTINCT m.lemma_id ORDER BY m.lemma_id) AS lemma_ids,
            COALESCE(u.author_lemma_form, '') AS author_lemma_form,
            COALESCE(u.author_english, '') AS author_english,
            COALESCE(u.work_title, '') AS work_title,
            COALESCE(u.book_label, '') AS book_label,
            COALESCE(u.raw_unit_text, '') AS raw_unit_text,
            COUNT(m.id) AS mention_count
        FROM source_citation_units u
        JOIN lemma_source_citation_mentions m ON m.unit_id = u.id
        WHERE {MODERN_ORACLE_AUTHOR_WHERE}
        GROUP BY u.id
        ORDER BY MIN(m.lemma_id), u.id
        """
    )
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete the targeted source citation units and their mentions.")
    args = parser.parse_args()

    conn = get_connection()
    try:
        cur = conn.cursor()
        targets = fetch_targets(cur)
        print(f"target_units={len(targets)}")
        for target in targets:
            print(
                "unit={id} lemmas={lemmas} mentions={mentions} author={author}/{english} raw={raw}".format(
                    id=target["id"],
                    lemmas=",".join(str(item) for item in target["lemma_ids"]),
                    mentions=target["mention_count"],
                    author=target["author_lemma_form"],
                    english=target["author_english"],
                    raw=target["raw_unit_text"],
                )
            )

        if not args.apply:
            conn.rollback()
            print("dry_run=true")
            return

        if targets:
            unit_ids = [target["id"] for target in targets]
            cur.execute(
                "DELETE FROM lemma_source_citation_mentions WHERE unit_id = ANY(%s)",
                (unit_ids,),
            )
            mention_deleted = cur.rowcount
            cur.execute("DELETE FROM source_citation_units WHERE id = ANY(%s)", (unit_ids,))
            unit_deleted = cur.rowcount
        else:
            mention_deleted = 0
            unit_deleted = 0
        conn.commit()
        print(f"deleted_mentions={mention_deleted}")
        print(f"deleted_units={unit_deleted}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
