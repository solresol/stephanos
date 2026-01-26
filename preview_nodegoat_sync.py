#!/usr/bin/env python3
"""
Preview what would change when syncing between nodegoat and local database.

This script shows differences WITHOUT making any changes.

Usage:
  uv run preview_nodegoat_sync.py                    # Preview all differences
  uv run preview_nodegoat_sync.py --limit 50         # Preview first 50 entries
  uv run preview_nodegoat_sync.py --billerbeck Α1    # Preview specific entry
"""
import argparse
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
    "english_approved": 48354,  # New: Approved EN translation
    "comments": 48242,
    "sort_order": 48272,
    "ocr_process": 48325,
    "confidence": 48328,
    "dtg": 48329,
    "edit_status": 48333,
    "headword_place": 48254,
    "other_places": 48297,
    "persons_mentioned": 48340,
    "epitome_parisinus": 48353,  # New: Epitome/Parisinus/Other
}

# Mapping: nodegoat field -> local DB column
# For pulling FROM nodegoat TO local DB
PULL_MAPPING = {
    "english_edited": "reviewed_english_translation",  # Human translations from nodegoat
    "comments": "human_notes",                          # Human notes from nodegoat
    # Note: We DON'T pull billerbeck_greek back - we're the source of that
}

# Mapping: local DB column -> nodegoat field
# For pushing FROM local DB TO nodegoat
PUSH_MAPPING = {
    "greek_text": "billerbeck_greek",      # Our OCR text
    "translation": "english_ai",            # Our AI translation
    "confidence": "confidence",
}


def get_nodegoat_entry(client, billerbeck_id: str) -> dict | None:
    """Fetch a single entry from nodegoat by Billerbeck ID."""
    result = client.query_data(
        type_id=int(NODEGOAT_LEMMA_TYPE_ID),
        search=billerbeck_id,
        project_id=NODEGOAT_PROJECT_ID,
        limit=200,
    )

    objects = result.get("data", {}).get("objects", {})
    for obj_id, obj_data in objects.items():
        defs = obj_data.get("object_definitions", {})
        obj_billerbeck = defs.get(str(NG_FIELDS["billerbeck_id"]), {})
        if obj_billerbeck.get("object_definition_value") == billerbeck_id:
            return {
                "object_id": obj_id,
                "nodegoat_id": obj_data.get("object", {}).get("nodegoat_id"),
                "object_name": obj_data.get("object", {}).get("object_name"),
                "definitions": {
                    field_name: defs.get(str(field_id), {}).get("object_definition_value")
                    for field_name, field_id in NG_FIELDS.items()
                }
            }
    return None


def get_local_entry(conn, billerbeck_id: str) -> dict | None:
    """Fetch a single entry from local database by Billerbeck ID."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, lemma, billerbeck_id, meineke_id, greek_text, translation,
               confidence, human_greek_text, human_notes,
               corrected_english_translation, reviewed_english_translation,
               review_status, nodegoat_id, version
        FROM assembled_lemmas
        WHERE billerbeck_id = %s
        LIMIT 1
    """, (billerbeck_id,))
    row = cur.fetchone()
    if row:
        columns = ['id', 'lemma', 'billerbeck_id', 'meineke_id', 'greek_text', 'translation',
                   'confidence', 'human_greek_text', 'human_notes',
                   'corrected_english_translation', 'reviewed_english_translation',
                   'review_status', 'nodegoat_id', 'version']
        return dict(zip(columns, row))
    return None


def truncate(s, length=80):
    """Truncate string for display."""
    if not s:
        return "(empty)"
    s = str(s).replace('\n', ' ')
    return s[:length] + "..." if len(s) > length else s


def compare_entry(local: dict, nodegoat: dict) -> dict:
    """Compare local and nodegoat entries, return differences."""
    diffs = {
        "pull_from_nodegoat": [],  # Changes to make in local DB
        "push_to_nodegoat": [],    # Changes to make in nodegoat
    }

    ng_defs = nodegoat["definitions"] if nodegoat else {}

    # Check fields we might PULL from nodegoat
    for ng_field, local_col in PULL_MAPPING.items():
        ng_value = ng_defs.get(ng_field) if ng_defs else None
        local_value = local.get(local_col) if local else None

        # Normalize empty values
        ng_value = ng_value if ng_value else None
        local_value = local_value if local_value else None

        if ng_value and ng_value != local_value:
            diffs["pull_from_nodegoat"].append({
                "field": local_col,
                "nodegoat_field": ng_field,
                "local_value": local_value,
                "nodegoat_value": ng_value,
            })

    # Check fields we might PUSH to nodegoat
    for local_col, ng_field in PUSH_MAPPING.items():
        local_value = local.get(local_col) if local else None
        ng_value = ng_defs.get(ng_field) if ng_defs else None

        # Normalize empty values
        ng_value = ng_value if ng_value else None
        local_value = local_value if local_value else None

        if local_value and local_value != ng_value:
            diffs["push_to_nodegoat"].append({
                "field": ng_field,
                "local_field": local_col,
                "local_value": local_value,
                "nodegoat_value": ng_value,
            })

    return diffs


def main():
    parser = argparse.ArgumentParser(description="Preview nodegoat sync changes")
    parser.add_argument("--limit", type=int, default=100, help="Limit entries to check")
    parser.add_argument("--billerbeck", type=str, help="Check specific Billerbeck ID")
    parser.add_argument("--show-all", action="store_true", help="Show all entries, not just those with differences")
    args = parser.parse_args()

    print(f"nodegoat sync preview - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project ID: {NODEGOAT_PROJECT_ID}")
    print()

    client = NodegoatClient()
    conn = db.get_connection()
    cur = conn.cursor()

    # Get entries to check
    if args.billerbeck:
        cur.execute("""
            SELECT DISTINCT billerbeck_id FROM assembled_lemmas
            WHERE billerbeck_id = %s
        """, (args.billerbeck,))
    else:
        cur.execute("""
            SELECT DISTINCT billerbeck_id FROM assembled_lemmas
            WHERE billerbeck_id IS NOT NULL AND billerbeck_id != ''
            ORDER BY billerbeck_id
            LIMIT %s
        """, (args.limit,))

    billerbeck_ids = [row[0] for row in cur.fetchall()]
    print(f"Checking {len(billerbeck_ids)} entries...")
    print()

    # Statistics
    stats = {
        "checked": 0,
        "not_in_nodegoat": 0,
        "not_in_local": 0,
        "in_sync": 0,
        "has_pull_changes": 0,
        "has_push_changes": 0,
    }

    pull_changes = []
    push_changes = []

    for i, billerbeck_id in enumerate(billerbeck_ids):
        stats["checked"] += 1

        local = get_local_entry(conn, billerbeck_id)
        nodegoat = get_nodegoat_entry(client, billerbeck_id)

        if not nodegoat:
            stats["not_in_nodegoat"] += 1
            if args.show_all:
                print(f"  {billerbeck_id}: NOT IN NODEGOAT")
            continue

        if not local:
            stats["not_in_local"] += 1
            if args.show_all:
                print(f"  {billerbeck_id}: NOT IN LOCAL DB")
            continue

        diffs = compare_entry(local, nodegoat)

        if diffs["pull_from_nodegoat"]:
            stats["has_pull_changes"] += 1
            pull_changes.append({
                "billerbeck_id": billerbeck_id,
                "lemma": local.get("lemma"),
                "changes": diffs["pull_from_nodegoat"],
            })

        if diffs["push_to_nodegoat"]:
            stats["has_push_changes"] += 1
            push_changes.append({
                "billerbeck_id": billerbeck_id,
                "lemma": local.get("lemma"),
                "changes": diffs["push_to_nodegoat"],
            })

        if not diffs["pull_from_nodegoat"] and not diffs["push_to_nodegoat"]:
            stats["in_sync"] += 1

        # Progress indicator
        if (i + 1) % 50 == 0:
            print(f"  ...checked {i + 1}/{len(billerbeck_ids)}")

    # Print results
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Entries checked: {stats['checked']}")
    print(f"Not in nodegoat: {stats['not_in_nodegoat']}")
    print(f"Not in local DB: {stats['not_in_local']}")
    print(f"Fully in sync: {stats['in_sync']}")
    print()

    if pull_changes:
        print("=" * 70)
        print(f"WOULD PULL FROM NODEGOAT → LOCAL DB: {len(pull_changes)} entries")
        print("=" * 70)
        for entry in pull_changes[:10]:  # Show first 10
            print(f"\n{entry['lemma']} ({entry['billerbeck_id']}):")
            for change in entry["changes"]:
                print(f"  {change['field']}:")
                print(f"    Local:    {truncate(change['local_value'])}")
                print(f"    Nodegoat: {truncate(change['nodegoat_value'])}")
        if len(pull_changes) > 10:
            print(f"\n  ... and {len(pull_changes) - 10} more entries")
    else:
        print("No changes to pull from nodegoat.")

    print()

    if push_changes:
        print("=" * 70)
        print(f"WOULD PUSH FROM LOCAL DB → NODEGOAT: {len(push_changes)} entries")
        print("=" * 70)
        for entry in push_changes[:10]:  # Show first 10
            print(f"\n{entry['lemma']} ({entry['billerbeck_id']}):")
            for change in entry["changes"]:
                print(f"  {change['field']}:")
                print(f"    Local:    {truncate(change['local_value'])}")
                print(f"    Nodegoat: {truncate(change['nodegoat_value'])}")
        if len(push_changes) > 10:
            print(f"\n  ... and {len(push_changes) - 10} more entries")
    else:
        print("No changes to push to nodegoat.")

    conn.close()
    print()


if __name__ == "__main__":
    main()
