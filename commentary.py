#!/usr/bin/env python3
"""
CRUD helper for phrase-level lemma commentary.

Backlog item: "add a commentary field that works at the phrase level".

Requires the `lemma_commentary_entries` table (see migrations/20260302_commentary_and_entity_audit.sql).
"""

from __future__ import annotations

import argparse

from db import get_connection


def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
    return bool(cur.fetchone()[0])


def cmd_add(cur, *, lemma_id: int, phrase_text: str, commentary_text: str, source_text_version_id: int | None, by: str):
    cur.execute(
        """
        INSERT INTO lemma_commentary_entries (
            lemma_id, source_text_version_id,
            phrase_text, commentary_text,
            created_by, updated_by
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (lemma_id, source_text_version_id, phrase_text, commentary_text, by, by),
    )
    new_id = cur.fetchone()[0]
    print(f"Inserted commentary id={new_id}")


def cmd_list(cur, *, lemma_id: int):
    cur.execute(
        """
        SELECT
            id,
            COALESCE(phrase_text, '') AS phrase_text,
            COALESCE(commentary_text, '') AS commentary_text,
            COALESCE(created_by, '') AS created_by,
            created_at,
            COALESCE(updated_by, '') AS updated_by,
            updated_at
        FROM lemma_commentary_entries
        WHERE lemma_id = %s
        ORDER BY id
        """,
        (lemma_id,),
    )
    rows = cur.fetchall()
    if not rows:
        print("(no commentary entries)")
        return
    for cid, phrase, note, created_by, created_at, updated_by, updated_at in rows:
        print(f"- id={cid} phrase={phrase!r}")
        print(f"  note={note!r}")
        if created_by or created_at:
            print(f"  created_by={created_by or '-'} created_at={created_at}")
        if updated_by or updated_at:
            print(f"  updated_by={updated_by or '-'} updated_at={updated_at}")


def cmd_delete(cur, *, entry_id: int):
    cur.execute("DELETE FROM lemma_commentary_entries WHERE id = %s", (entry_id,))
    if cur.rowcount:
        print(f"Deleted id={entry_id}")
    else:
        print(f"No row found for id={entry_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phrase-level commentary helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add", help="Insert a commentary entry")
    add_p.add_argument("--lemma-id", type=int, required=True)
    add_p.add_argument("--phrase", dest="phrase_text", required=True)
    add_p.add_argument("--commentary", dest="commentary_text", required=True)
    add_p.add_argument("--source-text-version-id", type=int, default=None)
    add_p.add_argument("--by", default="system", help="created_by/updated_by label (default: system)")

    list_p = sub.add_parser("list", help="List entries for a lemma")
    list_p.add_argument("--lemma-id", type=int, required=True)

    del_p = sub.add_parser("delete", help="Delete a commentary entry by id")
    del_p.add_argument("--id", dest="entry_id", type=int, required=True)

    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "lemma_commentary_entries"):
        print("lemma_commentary_entries table missing. Apply migrations first.")
        conn.close()
        return 2

    if args.cmd == "add":
        cmd_add(
            cur,
            lemma_id=args.lemma_id,
            phrase_text=args.phrase_text,
            commentary_text=args.commentary_text,
            source_text_version_id=args.source_text_version_id,
            by=args.by,
        )
        conn.commit()
    elif args.cmd == "list":
        cmd_list(cur, lemma_id=args.lemma_id)
    elif args.cmd == "delete":
        cmd_delete(cur, entry_id=args.entry_id)
        conn.commit()

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

