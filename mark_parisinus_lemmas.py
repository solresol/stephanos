#!/usr/bin/env python3
"""
Script to manually mark lemmas as belonging to Parisinus Coislinianus 228.

Parisinus Coislinianus 228 contains the unabridged text for:
- The last 13 delta entries (Δάαι through Δανούβιον)
- The first epsilon entry (when scanned)

All other entries are from the Epitomised version.
"""
import sys
from db import get_connection

def mark_lemmas_by_ids(lemma_ids, is_parisinus=True):
    """Mark specific lemmas by their IDs."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Mark the lemmas
        cur.execute("""
            UPDATE assembled_lemmas
            SET is_parisinus_228 = %s
            WHERE id = ANY(%s)
        """, (is_parisinus, lemma_ids))

        affected = cur.rowcount
        conn.commit()

        print(f"✓ Marked {affected} lemma(s) as {'Parisinus 228' if is_parisinus else 'Epitomised'}")

        # Show what was marked
        cur.execute("""
            SELECT id, lemma, entry_number
            FROM assembled_lemmas
            WHERE id = ANY(%s)
            ORDER BY id
        """, (lemma_ids,))

        print("\nMarked lemmas:")
        for row in cur.fetchall():
            print(f"  ID {row[0]}: {row[1]} (entry {row[2]})")

        return affected

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def mark_delta_lemmas_as_parisinus():
    """Mark all current delta lemmas (Δάαι through Δανούβιον) as Parisinus 228."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Find all delta lemmas
        cur.execute("""
            SELECT id, lemma, entry_number
            FROM assembled_lemmas
            WHERE lemma LIKE 'Δ%'
            ORDER BY id
        """)

        delta_lemmas = cur.fetchall()

        if not delta_lemmas:
            print("No delta lemmas found")
            return 0

        print(f"Found {len(delta_lemmas)} delta lemmas:")
        for row in delta_lemmas:
            print(f"  ID {row[0]}: {row[1]} (entry {row[2]})")

        # Mark them all as Parisinus 228
        lemma_ids = [row[0] for row in delta_lemmas]

        cur.execute("""
            UPDATE assembled_lemmas
            SET is_parisinus_228 = TRUE
            WHERE id = ANY(%s)
        """, (lemma_ids,))

        affected = cur.rowcount
        conn.commit()

        print(f"\n✓ Marked {affected} delta lemma(s) as Parisinus Coislinianus 228")
        return affected

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def show_parisinus_status():
    """Show the current Parisinus 228 vs Epitomised breakdown."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_parisinus_228 = TRUE) as parisinus_count,
                COUNT(*) FILTER (WHERE is_parisinus_228 = FALSE) as epitomised_count,
                COUNT(*) as total
            FROM assembled_lemmas
        """)

        row = cur.fetchone()
        parisinus_count, epitomised_count, total = row

        print("\nCurrent status:")
        print(f"  Parisinus Coislinianus 228: {parisinus_count} lemmas")
        print(f"  Epitomised version: {epitomised_count} lemmas")
        print(f"  Total: {total} lemmas")

        # Show which lemmas are Parisinus
        if parisinus_count > 0:
            cur.execute("""
                SELECT id, lemma, entry_number
                FROM assembled_lemmas
                WHERE is_parisinus_228 = TRUE
                ORDER BY id
            """)

            print("\nParisinus Coislinianus 228 lemmas:")
            for row in cur.fetchall():
                print(f"  ID {row[0]}: {row[1]} (entry {row[2]})")

    finally:
        cur.close()
        conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 mark_parisinus_lemmas.py status           - Show current status")
        print("  python3 mark_parisinus_lemmas.py mark-delta       - Mark all delta lemmas as Parisinus 228")
        print("  python3 mark_parisinus_lemmas.py mark <id> [...]  - Mark specific IDs as Parisinus 228")
        print("  python3 mark_parisinus_lemmas.py unmark <id> [...] - Unmark specific IDs")
        return 1

    command = sys.argv[1]

    if command == "status":
        show_parisinus_status()
    elif command == "mark-delta":
        mark_delta_lemmas_as_parisinus()
        print()
        show_parisinus_status()
    elif command == "mark":
        if len(sys.argv) < 3:
            print("Error: Please provide lemma IDs to mark", file=sys.stderr)
            return 1
        lemma_ids = [int(x) for x in sys.argv[2:]]
        mark_lemmas_by_ids(lemma_ids, is_parisinus=True)
        print()
        show_parisinus_status()
    elif command == "unmark":
        if len(sys.argv) < 3:
            print("Error: Please provide lemma IDs to unmark", file=sys.stderr)
            return 1
        lemma_ids = [int(x) for x in sys.argv[2:]]
        mark_lemmas_by_ids(lemma_ids, is_parisinus=False)
        print()
        show_parisinus_status()
    else:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
