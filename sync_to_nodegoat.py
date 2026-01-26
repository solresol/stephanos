#!/usr/bin/env python3
"""
Sync lemmas from PostgreSQL to nodegoat.

WARNING: The nodegoat PATCH API behavior is not fully understood. A PATCH request
may affect more objects than intended. DO NOT USE THIS SCRIPT until the API
behavior has been verified with the nodegoat team.

This script attempts to partially update existing nodegoat objects by matching
on Billerbeck ID. It ONLY updates specific fields:
  - Billerbeck Greek (48310): Our OCR greek_text
  - confidence (48328): OCR confidence level
  - DTG (48329): Date/time of processing
  - OCR_Process (48325): Model used for OCR

Usage:
  uv run sync_to_nodegoat.py              # Sync entries with Billerbeck IDs
  uv run sync_to_nodegoat.py --dry-run    # Show what would be synced
  uv run sync_to_nodegoat.py --limit 10   # Sync only first N lemmas
"""
import argparse
import json
import sys
from datetime import datetime

import db
from nodegoat_client import NodegoatClient
from config import NODEGOAT_PROJECT_ID, NODEGOAT_LEMMA_TYPE_ID

# Field IDs in nodegoat "Steph Paragraph" type
FIELD_IDS = {
    "greek_headword": 48236,
    "billerbeck_id": 48240,
    "meineke_id": 48241,
    "meineke_greek": 48237,
    "billerbeck_greek": 48310,  # This is where OCR greek_text should go
    "english_ai": 48238,
    "english_edited": 48239,
    "english_approved": 48354,  # Approved EN translation (new)
    "sort_order": 48272,
    "ocr_process": 48325,
    "confidence": 48328,
    "dtg": 48329,
    "epitome_parisinus": 48353,  # Epitome/Parisinus/Other (new)
}

# Fields we UPDATE in nodegoat (per expert guidance)
# Do NOT include sort_order - that's managed in nodegoat
UPDATE_FIELDS = {
    "billerbeck_greek": "greek_text",      # Our OCR text -> Billerbeck Greek
    "confidence": "confidence",             # confidence -> confidence
    "ocr_process": "ocr_model",            # We'll use a constant or column
    "dtg": "processed_at",                  # Date/time stamp
}


def find_nodegoat_object_by_billerbeck_id(client: NodegoatClient, billerbeck_id: str) -> dict | None:
    """Search nodegoat for an object with the given Billerbeck ID."""
    try:
        # Use higher limit because search for "Δ1" also matches "Δ10", "Δ100", etc.
        result = client.query_data(
            type_id=int(NODEGOAT_LEMMA_TYPE_ID),
            search=billerbeck_id,
            project_id=NODEGOAT_PROJECT_ID,
            limit=200,
        )

        objects = result.get("data", {}).get("objects", {})

        # Find the one with exact matching Billerbeck ID
        for obj_id, obj_data in objects.items():
            defs = obj_data.get("object_definitions", {})
            obj_billerbeck = defs.get(str(FIELD_IDS["billerbeck_id"]), {})
            if obj_billerbeck.get("object_definition_value") == billerbeck_id:
                return {
                    "object_id": obj_id,
                    "nodegoat_id": obj_data.get("object", {}).get("nodegoat_id"),
                    "object_name": obj_data.get("object", {}).get("object_name"),
                }

        return None
    except Exception as e:
        print(f"    Error searching for {billerbeck_id}: {e}")
        return None


def build_update_payload(row: dict) -> dict:
    """Build the nodegoat update payload for a lemma."""
    object_definitions = {}

    # Billerbeck Greek (our OCR text)
    if row.get("greek_text"):
        object_definitions[str(FIELD_IDS["billerbeck_greek"])] = {
            "object_description_id": FIELD_IDS["billerbeck_greek"],
            "object_definition_value": row["greek_text"],
        }

    # Confidence
    if row.get("confidence"):
        object_definitions[str(FIELD_IDS["confidence"])] = {
            "object_description_id": FIELD_IDS["confidence"],
            "object_definition_value": row["confidence"],
        }

    # OCR Process - use a descriptive string
    ocr_process = "gemini-2.0-flash"  # Default, could be from DB
    object_definitions[str(FIELD_IDS["ocr_process"])] = {
        "object_description_id": FIELD_IDS["ocr_process"],
        "object_definition_value": ocr_process,
    }

    # DTG (date/time group) - when we processed it
    if row.get("created_at"):
        dtg = row["created_at"].strftime("%m/%d/%Y %H:%M") if hasattr(row["created_at"], "strftime") else str(row["created_at"])
        object_definitions[str(FIELD_IDS["dtg"])] = {
            "object_description_id": FIELD_IDS["dtg"],
            "object_definition_value": dtg,
        }

    return {"object_definitions": object_definitions}


def get_lemmas_to_sync(conn, limit: int = None) -> list:
    """Get lemmas that have Billerbeck IDs and need syncing."""
    cur = conn.cursor()

    # Get entries with Billerbeck IDs that either:
    # 1. Don't have a nodegoat_id yet (need to find and link)
    # 2. Or we want to update anyway
    query = """
        SELECT id, lemma, billerbeck_id, greek_text, translation,
               confidence, meineke_id, created_at
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL
          AND billerbeck_id != ''
        ORDER BY billerbeck_id
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def sync_lemmas(client: NodegoatClient, conn, lemmas: list, dry_run: bool = False) -> tuple[int, int]:
    """
    Sync lemmas to nodegoat by matching on Billerbeck ID.
    Returns (updated_count, not_found_count)
    """
    if not lemmas:
        print("No lemmas to sync.")
        return 0, 0

    print(f"\nProcessing {len(lemmas)} lemma(s)...")

    updated_count = 0
    not_found_count = 0
    cur = conn.cursor()

    for i, lemma in enumerate(lemmas):
        billerbeck_id = lemma["billerbeck_id"]

        # Find the nodegoat object
        ng_obj = find_nodegoat_object_by_billerbeck_id(client, billerbeck_id)

        if not ng_obj:
            print(f"  [{i+1}/{len(lemmas)}] {lemma['lemma']} ({billerbeck_id}): NOT FOUND in nodegoat")
            not_found_count += 1
            continue

        if dry_run:
            print(f"  [{i+1}/{len(lemmas)}] {lemma['lemma']} ({billerbeck_id}): Would update {ng_obj['object_name']}")
            updated_count += 1
            continue

        # Build and send update using PATCH (partial update, preserves other fields)
        try:
            payload = build_update_payload(lemma)
            # Add the object_id to the payload for PATCH
            payload["object"] = {"object_id": int(ng_obj["object_id"])}

            result = client.patch_object(
                type_id=int(NODEGOAT_LEMMA_TYPE_ID),
                object_data=payload,
                project_id=NODEGOAT_PROJECT_ID,
            )

            # Store the nodegoat_id in our database
            cur.execute(
                "UPDATE assembled_lemmas SET nodegoat_id = %s WHERE id = %s",
                (ng_obj["nodegoat_id"], lemma["id"])
            )

            updated_count += 1
            print(f"  [{i+1}/{len(lemmas)}] {lemma['lemma']} ({billerbeck_id}): Updated")

        except Exception as e:
            print(f"  [{i+1}/{len(lemmas)}] {lemma['lemma']} ({billerbeck_id}): ERROR - {e}")

    if not dry_run:
        conn.commit()

    return updated_count, not_found_count


def main():
    parser = argparse.ArgumentParser(description="Sync lemmas to nodegoat (update by Billerbeck ID)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--limit", type=int, help="Limit number of lemmas to sync")
    args = parser.parse_args()

    print(f"nodegoat sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project ID: {NODEGOAT_PROJECT_ID}")
    print(f"Lemma Type ID: {NODEGOAT_LEMMA_TYPE_ID}")
    print(f"Strategy: Match by Billerbeck ID, update Billerbeck Greek/confidence/DTG/OCR_Process")

    if args.dry_run:
        print("DRY RUN - no changes will be made")

    try:
        client = NodegoatClient()
        conn = db.get_connection()

        lemmas = get_lemmas_to_sync(conn, args.limit)
        print(f"\nFound {len(lemmas)} lemma(s) with Billerbeck IDs")

        updated, not_found = sync_lemmas(client, conn, lemmas, args.dry_run)

        print(f"\n=== Summary ===")
        print(f"Updated: {updated}")
        print(f"Not found in nodegoat: {not_found}")

        conn.close()

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
