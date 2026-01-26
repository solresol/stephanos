#!/usr/bin/env python3
"""
Import data from nodegoat into the local database.

This script pulls:
- AI translations (english_ai) -> translation column
- Human-edited translations (english_edited) -> reviewed_english_translation
- Comments -> human_notes

Usage:
  uv run sync_from_nodegoat.py --dry-run              # Preview what would be imported
  uv run sync_from_nodegoat.py                        # Import all missing data
  uv run sync_from_nodegoat.py --letter K             # Import only letter K entries
  uv run sync_from_nodegoat.py --billerbeck Κ7        # Import specific entry
"""
import argparse
import time
from datetime import datetime

import db
from nodegoat_client import NodegoatClient
from config import NODEGOAT_PROJECT_ID, NODEGOAT_LEMMA_TYPE_ID

# nodegoat field IDs
NG_FIELDS = {
    "greek_headword": 48236,
    "billerbeck_id": 48240,
    "meineke_id": 48241,
    "meineke_greek": 48237,
    "billerbeck_greek": 48310,
    "english_ai": 48238,
    "english_edited": 48239,
    "comments": 48242,
    "sort_order": 48272,
    "ocr_process": 48325,
    "confidence": 48328,
    "dtg": 48329,
}

# Rate limiting: nodegoat allows 30 requests per 15 minutes
# Be conservative: 1 request every 35 seconds = ~25 requests per 15 minutes
RATE_LIMIT_SECONDS = 35


def get_local_missing_translations(conn, letter_filter=None):
    """Get entries from local DB that are missing translations."""
    cur = conn.cursor()
    query = """
        SELECT id, billerbeck_id, lemma, translation
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL AND billerbeck_id != ''
          AND (translation IS NULL OR translation = '')
    """
    params = []

    if letter_filter:
        query += " AND billerbeck_id LIKE %s"
        params.append(f"{letter_filter}%")

    query += " ORDER BY billerbeck_id"

    cur.execute(query, params)
    columns = ['id', 'billerbeck_id', 'lemma', 'translation']
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_nodegoat_entries_batch(client, search_prefix, limit=500):
    """
    Fetch entries from nodegoat by search prefix.
    Returns a dict mapping billerbeck_id -> entry data.
    """
    result = client.query_data(
        type_id=int(NODEGOAT_LEMMA_TYPE_ID),
        search=search_prefix,
        project_id=NODEGOAT_PROJECT_ID,
        limit=limit,
    )

    entries = {}
    objects = result.get("data", {}).get("objects", {})

    for obj_id, obj_data in objects.items():
        defs = obj_data.get("object_definitions", {})

        billerbeck_id = defs.get(str(NG_FIELDS["billerbeck_id"]), {}).get("object_definition_value")
        if not billerbeck_id:
            continue

        entries[billerbeck_id] = {
            "object_id": obj_id,
            "nodegoat_id": obj_data.get("object", {}).get("nodegoat_id"),
            "object_name": obj_data.get("object", {}).get("object_name"),
            "english_ai": defs.get(str(NG_FIELDS["english_ai"]), {}).get("object_definition_value"),
            "english_edited": defs.get(str(NG_FIELDS["english_edited"]), {}).get("object_definition_value"),
            "comments": defs.get(str(NG_FIELDS["comments"]), {}).get("object_definition_value"),
        }

    return entries


def import_single_entry(conn, local_id, billerbeck_id, nodegoat_entry, dry_run=False):
    """Import data from a single nodegoat entry into local DB."""
    updates = []
    params = []

    # Import AI translation if present
    if nodegoat_entry.get("english_ai"):
        updates.append("translation = %s")
        params.append(nodegoat_entry["english_ai"])
        updates.append("translated = 1")
        updates.append("translated_at = NOW()")

    # Import human-edited translation if present
    if nodegoat_entry.get("english_edited"):
        updates.append("reviewed_english_translation = %s")
        params.append(nodegoat_entry["english_edited"])

    # Import comments/notes if present
    if nodegoat_entry.get("comments"):
        updates.append("human_notes = %s")
        params.append(nodegoat_entry["comments"])

    # Store nodegoat_id for future syncs
    if nodegoat_entry.get("nodegoat_id"):
        updates.append("nodegoat_id = %s")
        params.append(nodegoat_entry["nodegoat_id"])

    if not updates:
        return False

    if dry_run:
        return True

    params.append(local_id)
    sql = f"UPDATE assembled_lemmas SET {', '.join(updates)} WHERE id = %s"

    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()

    return True


def main():
    parser = argparse.ArgumentParser(description="Import data from nodegoat")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--letter", type=str, help="Filter by letter (e.g., K, Α, Β)")
    parser.add_argument("--billerbeck", type=str, help="Import specific Billerbeck ID")
    parser.add_argument("--all-missing", action="store_true", help="Find ALL entries with AI in nodegoat but not locally")
    parser.add_argument("--no-rate-limit", action="store_true", help="Disable rate limiting (use with caution)")
    args = parser.parse_args()

    print(f"nodegoat import - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project ID: {NODEGOAT_PROJECT_ID}")
    if args.dry_run:
        print("DRY RUN - No changes will be made")
    print()

    client = NodegoatClient()
    conn = db.get_connection()

    if args.billerbeck:
        # Import single entry
        print(f"Looking up {args.billerbeck} in nodegoat...")
        ng_entries = get_nodegoat_entries_batch(client, args.billerbeck, limit=200)

        if args.billerbeck not in ng_entries:
            print(f"Entry {args.billerbeck} not found in nodegoat")
            return

        ng_entry = ng_entries[args.billerbeck]
        print(f"Found in nodegoat: {ng_entry['object_name']}")
        print(f"  AI translation: {ng_entry.get('english_ai', '(none)')[:100]}...")
        print(f"  Human translation: {ng_entry.get('english_edited', '(none)')[:100] if ng_entry.get('english_edited') else '(none)'}...")

        # Find local entry
        cur = conn.cursor()
        cur.execute("SELECT id FROM assembled_lemmas WHERE billerbeck_id = %s LIMIT 1", (args.billerbeck,))
        row = cur.fetchone()

        if not row:
            print(f"Entry {args.billerbeck} not found in local database")
            return

        local_id = row[0]

        if import_single_entry(conn, local_id, args.billerbeck, ng_entry, args.dry_run):
            action = "Would import" if args.dry_run else "Imported"
            print(f"{action} data for {args.billerbeck}")
        else:
            print(f"Nothing to import for {args.billerbeck}")

        return

    if args.all_missing:
        # Scan all letters for missing AI translations
        print("Scanning all entries for missing AI translations...")

        # Greek letters in order
        letters = ['Α', 'Β', 'Γ', 'Δ', 'Ε', 'Ζ', 'Η', 'Θ', 'Ι', 'Κ', 'Λ', 'Μ',
                   'Ν', 'Ξ', 'Ο', 'Π', 'Ρ', 'Σ', 'Τ', 'Υ', 'Φ', 'Χ', 'Ψ', 'Ω']

        all_missing = []

        for letter in letters:
            print(f"\nChecking {letter}...")
            local_missing = get_local_missing_translations(conn, letter)

            if not local_missing:
                print(f"  No missing translations for {letter}")
                continue

            print(f"  {len(local_missing)} entries missing translation locally")

            # Rate limit
            if not args.no_rate_limit:
                time.sleep(RATE_LIMIT_SECONDS)

            # Fetch from nodegoat
            ng_entries = get_nodegoat_entries_batch(client, letter, limit=500)
            print(f"  {len(ng_entries)} entries found in nodegoat")

            # Find entries where nodegoat has AI but local doesn't
            for local_entry in local_missing:
                billerbeck_id = local_entry['billerbeck_id']
                ng_entry = ng_entries.get(billerbeck_id)

                if ng_entry and ng_entry.get('english_ai'):
                    all_missing.append({
                        'local': local_entry,
                        'nodegoat': ng_entry,
                    })

        print(f"\n{'='*70}")
        print(f"Found {len(all_missing)} entries with AI in nodegoat but not locally")
        print(f"{'='*70}\n")

        if all_missing:
            for entry in all_missing[:20]:
                local = entry['local']
                ng = entry['nodegoat']
                print(f"  {local['billerbeck_id']}: {local['lemma']}")
                print(f"    AI: {ng.get('english_ai', '')[:80]}...")

            if len(all_missing) > 20:
                print(f"\n  ... and {len(all_missing) - 20} more")

            if not args.dry_run:
                print(f"\nImporting {len(all_missing)} translations...")
                imported = 0
                for entry in all_missing:
                    if import_single_entry(
                        conn,
                        entry['local']['id'],
                        entry['local']['billerbeck_id'],
                        entry['nodegoat'],
                        dry_run=False
                    ):
                        imported += 1
                print(f"Imported {imported} translations")

        return

    # Get local entries missing translations
    local_missing = get_local_missing_translations(conn, args.letter)

    if not local_missing:
        print("No entries missing translations in local database")
        return

    print(f"Found {len(local_missing)} entries missing translations locally")

    # Group by first letter for batch querying
    by_letter = {}
    for entry in local_missing:
        if entry['billerbeck_id']:
            letter = entry['billerbeck_id'][0]
            if letter not in by_letter:
                by_letter[letter] = []
            by_letter[letter].append(entry)

    imported_count = 0
    checked_count = 0

    for letter, entries in sorted(by_letter.items()):
        print(f"\nProcessing {letter} ({len(entries)} entries)...")

        # Rate limiting
        if not args.no_rate_limit and checked_count > 0:
            print(f"  Rate limiting: waiting {RATE_LIMIT_SECONDS}s...")
            time.sleep(RATE_LIMIT_SECONDS)

        # Fetch nodegoat entries for this letter
        ng_entries = get_nodegoat_entries_batch(client, letter, limit=500)
        print(f"  {len(ng_entries)} entries found in nodegoat")
        checked_count += 1

        # Match and import
        for local_entry in entries:
            billerbeck_id = local_entry['billerbeck_id']
            ng_entry = ng_entries.get(billerbeck_id)

            if not ng_entry:
                continue

            if not ng_entry.get('english_ai') and not ng_entry.get('english_edited'):
                continue

            if import_single_entry(conn, local_entry['id'], billerbeck_id, ng_entry, args.dry_run):
                imported_count += 1
                action = "Would import" if args.dry_run else "Imported"
                translation = ng_entry.get('english_ai') or ng_entry.get('english_edited')
                print(f"  {action}: {billerbeck_id} ({local_entry['lemma']})")

    print(f"\n{'='*70}")
    action = "Would import" if args.dry_run else "Imported"
    print(f"{action} {imported_count} translations")

    conn.close()


if __name__ == "__main__":
    main()
