#!/usr/bin/env python3
"""
One-shot backfill: insert a 'completed' row into source_citation_extraction_runs
for every lemma that already has at least one row in lemma_source_citation_mentions.

This avoids reprocessing the ~2.4k already-extracted lemmas after the runs table
goes live. Lemmas with zero citations (no mentions) are *not* backfilled — they
will be re-processed once and recorded properly thereafter.

Idempotent: skips lemmas that already have any run row.
"""

from __future__ import annotations

import hashlib

from db import get_connection


def hash_input_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            a.id,
            COALESCE(a.corrected_greek_scan, a.human_greek_text, a.greek_text, '') AS greek_text,
            (SELECT extracted_by_model
             FROM lemma_source_citation_mentions m
             WHERE m.lemma_id = a.id
             ORDER BY m.extracted_at DESC NULLS LAST, m.id DESC
             LIMIT 1) AS last_model,
            (SELECT COUNT(*) FROM lemma_source_citation_mentions m WHERE m.lemma_id = a.id) AS mention_count
        FROM assembled_lemmas a
        WHERE EXISTS (SELECT 1 FROM lemma_source_citation_mentions m WHERE m.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM source_citation_extraction_runs r WHERE r.lemma_id = a.id)
        ORDER BY a.id
        """
    )
    rows = cur.fetchall()

    if not rows:
        print("Nothing to backfill.")
        conn.close()
        return

    print(f"Backfilling {len(rows)} lemmas...")

    inserted = 0
    for lemma_id, greek_text, last_model, mention_count in rows:
        stripped = (greek_text or "").strip()
        if not stripped:
            continue
        input_hash = hash_input_text(stripped)
        model = last_model or "unknown"

        # We don't know how many "units" the original extraction produced
        # (mentions can collapse via the unique constraint). Record mention
        # count as a useful proxy, leave units_extracted=0 to flag this row
        # as a backfill rather than a fresh result. Tokens are unknown.
        cur.execute(
            """
            INSERT INTO source_citation_extraction_runs (
                lemma_id, model, input_text_sha256,
                units_extracted, mentions_inserted, tokens_used,
                status, error_message
            )
            VALUES (%s, %s, %s, 0, %s, 0, 'completed', 'backfilled from existing mentions')
            """,
            (int(lemma_id), model, input_hash, int(mention_count)),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Done. Inserted {inserted} backfill rows.")


if __name__ == "__main__":
    main()
