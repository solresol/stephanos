#!/usr/bin/env python3
"""
Bidirectional sync between local PostgreSQL and nodegoat.

This script handles both directions:
- PUSH: Send our data TO nodegoat (Billerbeck Greek, translations, version info)
- PULL: Get human corrections FROM nodegoat (edited translations, comments)

Field Mappings (Local DB -> nodegoat):
  - greek_text           -> Billerbeck Greek (48310)     [PUSH only if not in nodegoat]
  - translation          -> English AI (48238)           [PUSH]
  - corrected_english_translation -> English edited (48239) [PUSH - Initial Human]
  - reviewed_english_translation  -> Approved EN (48354)    [PUSH]
  - version              -> Epitome/Parisinus/Other (48353) [PUSH]

Field Mappings (nodegoat -> Local DB):
  - English edited (48239)  -> reviewed_english_translation  [PULL - human corrections]
  - Comments (48242)        -> human_notes                   [PULL]

We NEVER update Meineke Greek (48237) - we don't have that data.

Usage:
  uv run sync_nodegoat.py --push --limit 10      # Push 10 changed entries to nodegoat
  uv run sync_nodegoat.py --pull --limit 50      # Pull 50 entries from nodegoat
  uv run sync_nodegoat.py --push --dry-run       # Preview push without changes
  uv run sync_nodegoat.py --catch-up --limit 50  # Sync entries never synced before
"""
import argparse
from datetime import datetime

import db
from nodegoat_client import NodegoatClient
from config import NODEGOAT_PROJECT_ID, NODEGOAT_LEMMA_TYPE_ID

# nodegoat field IDs for "Steph Paragraph" type
NG_FIELDS = {
    # Identification
    "greek_headword": 48236,
    "billerbeck_id": 48240,
    "meineke_id": 48241,
    "sort_order": 48272,
    # Greek text
    "meineke_greek": 48237,        # We DON'T write this - not our data
    "billerbeck_greek": 48310,     # We write this (OCR greek_text)
    # Translations
    "english_ai": 48238,           # AI translation (translation column)
    "english_edited": 48239,       # Initial human translation (corrected_english_translation)
    "english_approved": 48354,     # Reviewed translation (reviewed_english_translation)
    # Metadata
    "comments": 48242,             # Human notes
    "epitome_parisinus": 48353,    # Version (epitome/parisinus/synthetic)
    "ocr_process": 48325,
    "confidence": 48328,
    "dtg": 48329,
    "edit_status": 48333,
    # Places/references (read-only for us)
    "headword_place": 48254,
    "other_places": 48297,
    "persons_mentioned": 48340,
}

# Fields we PUSH to nodegoat (local -> nodegoat)
# Maps local column -> nodegoat field name
PUSH_FIELDS = {
    "greek_text": "billerbeck_greek",
    "translation": "english_ai",
    "corrected_english_translation": "english_edited",
    "reviewed_english_translation": "english_approved",
    "version": "epitome_parisinus",
    "confidence": "confidence",
}

# Fields we PULL from nodegoat (nodegoat -> local)
# Maps nodegoat field name -> local column
PULL_FIELDS = {
    "english_edited": "reviewed_english_translation",
    "comments": "human_notes",
}


def get_nodegoat_entries(client: NodegoatClient, limit: int = 5000) -> dict:
    """Fetch all entries from nodegoat, indexed by billerbeck_id."""
    result = client.query_data(
        type_id=int(NODEGOAT_LEMMA_TYPE_ID),
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
            "fields": {
                field_name: defs.get(str(field_id), {}).get("object_definition_value")
                for field_name, field_id in NG_FIELDS.items()
            }
        }

    return entries


def get_local_entries_to_push(conn, limit: int = None, catch_up: bool = False) -> list:
    """Get local entries that need to be pushed to nodegoat.

    If catch_up=True, gets entries never synced before.
    Otherwise, gets entries modified since last sync.
    """
    cur = conn.cursor()

    if catch_up:
        # Get entries with billerbeck_id that have never been synced
        query = """
            SELECT id, billerbeck_id, lemma, greek_text, translation,
                   corrected_english_translation, reviewed_english_translation,
                   version, confidence, nodegoat_id
            FROM assembled_lemmas
            WHERE billerbeck_id IS NOT NULL
              AND billerbeck_id != ''
              AND last_synced_to_nodegoat_at IS NULL
            ORDER BY billerbeck_id
        """
    else:
        # Get entries modified since last sync
        query = """
            SELECT id, billerbeck_id, lemma, greek_text, translation,
                   corrected_english_translation, reviewed_english_translation,
                   version, confidence, nodegoat_id
            FROM assembled_lemmas
            WHERE billerbeck_id IS NOT NULL
              AND billerbeck_id != ''
              AND (
                  last_synced_to_nodegoat_at IS NULL
                  OR translation_modified_at > last_synced_to_nodegoat_at
                  OR reviewed_translation_modified_at > last_synced_to_nodegoat_at
                  OR updated_at > last_synced_to_nodegoat_at
              )
            ORDER BY billerbeck_id
        """

    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def build_push_payload(local_entry: dict, ng_entry: dict | None) -> dict | None:
    """Build nodegoat PATCH payload with only changed fields.

    Returns None if no changes needed.
    """
    object_definitions = {}
    ng_fields = ng_entry["fields"] if ng_entry else {}

    # Check each pushable field
    for local_col, ng_field_name in PUSH_FIELDS.items():
        local_value = local_entry.get(local_col)
        ng_value = ng_fields.get(ng_field_name)

        # Skip if local value is empty
        if not local_value:
            continue

        # Special handling for billerbeck_greek: only push if nodegoat is empty
        if ng_field_name == "billerbeck_greek" and ng_value:
            continue

        # Skip if values match
        if local_value == ng_value:
            continue

        # Add to update payload
        field_id = NG_FIELDS[ng_field_name]
        object_definitions[str(field_id)] = {
            "object_description_id": field_id,
            "object_definition_value": local_value,
        }

    if not object_definitions:
        return None

    return {"object_definitions": object_definitions}


def push_to_nodegoat(
    client: NodegoatClient,
    conn,
    local_entries: list,
    ng_entries: dict,
    dry_run: bool = False
) -> tuple[int, int, int]:
    """Push local entries to nodegoat.

    Returns (pushed_count, skipped_count, not_found_count)
    """
    pushed_count = 0
    skipped_count = 0
    not_found_count = 0
    cur = conn.cursor()

    for i, local_entry in enumerate(local_entries):
        billerbeck_id = local_entry["billerbeck_id"]
        ng_entry = ng_entries.get(billerbeck_id)

        if not ng_entry:
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): NOT IN NODEGOAT")
            not_found_count += 1
            continue

        payload = build_push_payload(local_entry, ng_entry)

        if not payload:
            skipped_count += 1
            continue

        fields_to_update = list(payload["object_definitions"].keys())
        field_names = [k for k, v in NG_FIELDS.items() if str(v) in fields_to_update]

        if dry_run:
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): Would update {field_names}")
            pushed_count += 1
            continue

        # Add object_id for PATCH
        payload["object"] = {"object_id": int(ng_entry["object_id"])}

        try:
            result = client.patch_object(
                type_id=int(NODEGOAT_LEMMA_TYPE_ID),
                object_data=payload,
                project_id=NODEGOAT_PROJECT_ID,
            )

            # Update sync timestamp and nodegoat_id
            cur.execute("""
                UPDATE assembled_lemmas
                SET last_synced_to_nodegoat_at = NOW(),
                    nodegoat_id = %s
                WHERE id = %s
            """, (ng_entry["nodegoat_id"], local_entry["id"]))

            pushed_count += 1
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): Updated {field_names}")

        except Exception as e:
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): ERROR - {e}")

    if not dry_run:
        conn.commit()

    return pushed_count, skipped_count, not_found_count


def pull_from_nodegoat(
    client: NodegoatClient,
    conn,
    ng_entries: dict,
    limit: int = None,
    dry_run: bool = False
) -> tuple[int, int]:
    """Pull human corrections from nodegoat to local database.

    Returns (pulled_count, skipped_count)
    """
    pulled_count = 0
    skipped_count = 0
    cur = conn.cursor()

    entries_to_check = list(ng_entries.items())
    if limit:
        entries_to_check = entries_to_check[:limit]

    for i, (billerbeck_id, ng_entry) in enumerate(entries_to_check):
        # Get local entry
        cur.execute("""
            SELECT id, reviewed_english_translation, human_notes, last_synced_from_nodegoat_at
            FROM assembled_lemmas
            WHERE billerbeck_id = %s
            LIMIT 1
        """, (billerbeck_id,))
        local_row = cur.fetchone()

        if not local_row:
            skipped_count += 1
            continue

        local_id, local_reviewed, local_notes, last_synced = local_row
        ng_fields = ng_entry["fields"]

        updates = []
        params = []

        # Check each pullable field
        for ng_field_name, local_col in PULL_FIELDS.items():
            ng_value = ng_fields.get(ng_field_name)

            if not ng_value:
                continue

            # Map local column name to current value
            if local_col == "reviewed_english_translation":
                local_value = local_reviewed
            elif local_col == "human_notes":
                local_value = local_notes
            else:
                local_value = None

            # Update if nodegoat has value we don't have
            if ng_value and ng_value != local_value:
                updates.append(f"{local_col} = %s")
                params.append(ng_value)

                if local_col == "reviewed_english_translation":
                    updates.append("reviewed_translation_modified_at = NOW()")

        if not updates:
            skipped_count += 1
            continue

        if dry_run:
            print(f"  [{i+1}/{len(entries_to_check)}] {ng_entry['object_name']} ({billerbeck_id}): Would update {[u.split('=')[0].strip() for u in updates if '=' in u and 'modified_at' not in u]}")
            pulled_count += 1
            continue

        # Add sync timestamp and execute
        updates.append("last_synced_from_nodegoat_at = NOW()")
        params.append(local_id)

        sql = f"UPDATE assembled_lemmas SET {', '.join(updates)} WHERE id = %s"
        cur.execute(sql, params)

        pulled_count += 1
        print(f"  [{i+1}/{len(entries_to_check)}] {ng_entry['object_name']} ({billerbeck_id}): Pulled updates")

    if not dry_run:
        conn.commit()

    return pulled_count, skipped_count


def main():
    parser = argparse.ArgumentParser(description="Sync data with nodegoat")
    parser.add_argument("--push", action="store_true", help="Push local changes to nodegoat")
    parser.add_argument("--pull", action="store_true", help="Pull changes from nodegoat")
    parser.add_argument("--catch-up", action="store_true", help="Sync entries never synced before")
    parser.add_argument("--limit", type=int, help="Limit number of entries to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without making them")
    args = parser.parse_args()

    if not args.push and not args.pull:
        print("Please specify --push or --pull (or both)")
        return

    print(f"nodegoat sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project ID: {NODEGOAT_PROJECT_ID}")
    if args.dry_run:
        print("DRY RUN - no changes will be made")
    print()

    client = NodegoatClient()
    conn = db.get_connection()

    # Fetch all nodegoat entries once
    print("Fetching nodegoat entries...")
    ng_entries = get_nodegoat_entries(client)
    print(f"Found {len(ng_entries)} entries in nodegoat")
    print()

    if args.push:
        print("=" * 70)
        print("PUSH: Local -> nodegoat")
        print("=" * 70)

        local_entries = get_local_entries_to_push(conn, args.limit, args.catch_up)
        print(f"Found {len(local_entries)} local entries to check")

        if local_entries:
            pushed, skipped, not_found = push_to_nodegoat(
                client, conn, local_entries, ng_entries, args.dry_run
            )
            print()
            print(f"Pushed: {pushed}")
            print(f"Skipped (no changes): {skipped}")
            print(f"Not in nodegoat: {not_found}")
        print()

    if args.pull:
        print("=" * 70)
        print("PULL: nodegoat -> Local")
        print("=" * 70)

        pulled, skipped = pull_from_nodegoat(
            client, conn, ng_entries, args.limit, args.dry_run
        )
        print()
        print(f"Pulled: {pulled}")
        print(f"Skipped (no changes): {skipped}")

    conn.close()
    print()
    print("Done.")


if __name__ == "__main__":
    main()
