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
import html as html_module
import json
from datetime import datetime, timezone
from pathlib import Path

import canonical_variants
import db
from nodegoat_client import NodegoatClient
from config import NODEGOAT_PROJECT_ID, NODEGOAT_LEMMA_TYPE_ID
from site_navigation import render_site_navigation, site_navigation_styles

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

TRANSLATION_LOCAL_COLUMNS = {
    "translation",
    "corrected_english_translation",
    "reviewed_english_translation",
}


def pg_table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def summarize_presented_variant(v: dict) -> dict:
    text = (v.get("translation_text") or "").strip()
    preview = text
    if len(preview) > 160:
        preview = preview[:157].rstrip() + "..."
    return {
        "kind": v.get("kind", ""),
        "id": str(v.get("id", "") or ""),
        "is_primary": bool(v.get("is_primary", False)),
        "status": v.get("status", ""),
        "source_document": v.get("source_document", ""),
        "source_text_version_id": str(v.get("source_text_version_id", "") or ""),
        "preview": preview,
    }


def describe_zero_presented(cur, lemma_id: int) -> dict:
    info = {"memberships": [], "fallback": None}

    if canonical_variants.table_exists(cur, "lemma_canonical_variants"):
        cur.execute(
            """
            SELECT variant_kind, variant_id, COALESCE(is_primary, FALSE) AS is_primary, updated_at
            FROM lemma_canonical_variants
            WHERE lemma_id = %s
              AND is_active = TRUE
            ORDER BY COALESCE(is_primary, FALSE) DESC, updated_at DESC, variant_kind, variant_id
            """,
            (lemma_id,),
        )
        for kind, vid, is_primary, updated_at in cur.fetchall():
            resolved = canonical_variants.resolve_variant(
                cur,
                lemma_id=lemma_id,
                variant_kind=kind,
                variant_id=str(vid),
            )
            info["memberships"].append(
                {
                    "kind": (kind or "").strip(),
                    "id": str(vid or "").strip(),
                    "is_primary": bool(is_primary),
                    "membership_updated_at": str(updated_at) if updated_at else "",
                    "exists": bool(resolved.get("exists")),
                    "publishable": bool(resolved.get("publishable")),
                    "status": resolved.get("status", ""),
                    "block_reason": resolved.get("block_reason", ""),
                }
            )

    fallback = canonical_variants.resolve_fallback_variant(cur, lemma_id=lemma_id)
    if fallback:
        info["fallback"] = summarize_presented_variant(fallback)
    return info


def write_canonical_sync_ambiguity_report(
    ambiguities: list[dict],
    *,
    output_dir: Path = Path("reference_site/protected"),
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "generated_at": generated_at,
        "count": len(ambiguities),
        "ambiguities": ambiguities,
    }
    json_path = output_dir / "canonical_sync_ambiguities.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = []
    for item in ambiguities:
        variants_html = ""
        variants = item.get("presented_variants") or []
        if variants:
            parts = []
            for v in variants:
                label = f"{v.get('kind', '')}:{v.get('id', '')}".strip(":")
                if v.get("is_primary"):
                    label = f"{label} (primary)"
                preview = (v.get("preview") or "").strip()
                if preview:
                    parts.append(f"<li><b>{html_module.escape(label)}</b><br><span>{html_module.escape(preview)}</span></li>")
                else:
                    parts.append(f"<li><b>{html_module.escape(label)}</b></li>")
            variants_html = "<ul>" + "".join(parts) + "</ul>"

        lemma_id = item.get("lemma_id")
        lemma_label = html_module.escape(item.get("lemma") or "")
        billerbeck_id = html_module.escape(item.get("billerbeck_id") or "")
        reason = html_module.escape(item.get("reason") or "")
        count = int(item.get("presented_count") or 0)
        review_link = f"/cgi-bin/review.cgi?id={lemma_id}" if lemma_id else "#"
        rows.append(
            "<tr>"
            f"<td><a href='{html_module.escape(review_link)}'>{lemma_id}</a></td>"
            f"<td>{lemma_label}</td>"
            f"<td>{billerbeck_id}</td>"
            f"<td>{reason}</td>"
            f"<td style='text-align:center'>{count}</td>"
            f"<td>{variants_html}</td>"
            "</tr>"
        )

    html_body = (
        "<h1>Canonical sync ambiguities</h1>"
        "<p>Nodegoat sync skips translation fields when a lemma does not have exactly one presentable translation variant.</p>"
        f"<p>Generated at: {html_module.escape(generated_at)}</p>"
    )
    if not rows:
        html_body += "<p><b>No ambiguities found in this sync run.</b></p>"
    else:
        html_body += (
            "<table>"
            "<thead><tr><th>Lemma ID</th><th>Headword</th><th>Billerbeck</th><th>Reason</th><th>#</th><th>Presented variants</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    html_text = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Canonical sync ambiguities</title>"
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;margin:20px;color:#222;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;vertical-align:top;}"
        "th{background:#f3f4f6;text-align:left;}"
        "ul{margin:0;padding-left:18px;}"
        "li{margin:6px 0;}"
        f"{site_navigation_styles()}"
        "</style></head><body>"
        + render_site_navigation("operations", depth=1)
        + html_body
        + "</body></html>"
    )

    html_path = output_dir / "canonical_sync_ambiguities.html"
    html_path.write_text(html_text + "\n", encoding="utf-8")
    return json_path, html_path


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

    has_canonical_variants = pg_table_exists(cur, "lemma_canonical_variants")
    has_translation_runs = pg_table_exists(cur, "translation_runs")
    has_human_translations = pg_table_exists(cur, "human_translations")

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
        extra_conditions = []
        if has_canonical_variants:
            extra_conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM lemma_canonical_variants lcv
                    WHERE lcv.lemma_id = assembled_lemmas.id
                      AND (
                          assembled_lemmas.last_synced_to_nodegoat_at IS NULL
                          OR lcv.updated_at > assembled_lemmas.last_synced_to_nodegoat_at
                      )
                )
                """
            )
        if has_translation_runs:
            extra_conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM translation_runs tr
                    WHERE tr.lemma_id = assembled_lemmas.id
                      AND (
                          assembled_lemmas.last_synced_to_nodegoat_at IS NULL
                          OR COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) > assembled_lemmas.last_synced_to_nodegoat_at
                      )
                )
                """
            )
        if has_human_translations:
            extra_conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM human_translations ht
                    WHERE ht.lemma_id = assembled_lemmas.id
                      AND (
                          assembled_lemmas.last_synced_to_nodegoat_at IS NULL
                          OR ht.updated_at > assembled_lemmas.last_synced_to_nodegoat_at
                      )
                )
                """
            )

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
                  {extra_predicate}
              )
            ORDER BY billerbeck_id
        """
        extra_predicate = ""
        if extra_conditions:
            extra_predicate = " OR " + " OR ".join(extra_conditions)
        query = query.format(extra_predicate=extra_predicate)

    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def build_push_payload(local_entry: dict, ng_entry: dict | None, *, skip_translation: bool = False) -> dict | None:
    """Build nodegoat update payload with only changed fields.

    Returns None if no changes needed.
    """
    object_definitions = {}
    ng_fields = ng_entry["fields"] if ng_entry else {}

    # Check each pushable field
    for local_col, ng_field_name in PUSH_FIELDS.items():
        if skip_translation and local_col in TRANSLATION_LOCAL_COLUMNS:
            continue
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


def build_full_update_payload(ng_entry: dict, changes: dict) -> dict:
    """Merge existing nodegoat fields with changes for safe PUT update."""
    merged_definitions = {}

    # Preserve existing nodegoat fields to avoid wiping data
    for field_name, field_id in NG_FIELDS.items():
        existing_value = ng_entry["fields"].get(field_name)
        if existing_value is None or existing_value == "":
            continue
        merged_definitions[str(field_id)] = {
            "object_description_id": field_id,
            "object_definition_value": existing_value,
        }

    # Overlay changes
    for field_id, payload in changes["object_definitions"].items():
        merged_definitions[field_id] = payload

    return {"object_definitions": merged_definitions}


def push_to_nodegoat(
    client: NodegoatClient,
    conn,
    local_entries: list,
    ng_entries: dict,
    dry_run: bool = False,
    verbose: bool = False,
    batch_size: int = 25,
) -> tuple[int, int, int]:
    """Push local entries to nodegoat.

    Returns (pushed_count, skipped_count, not_found_count)
    """
    pushed_count = 0
    skipped_count = 0
    not_found_count = 0
    cur = conn.cursor()
    canonical_sync_ambiguities: list[dict] = []

    batch_size = max(1, int(batch_size or 1))

    # Collect updates first so we can send fewer API calls (nodegoat supports bulk PUT updates).
    pending_updates: list[dict] = []

    for i, local_entry in enumerate(local_entries):
        billerbeck_id = local_entry["billerbeck_id"]
        ng_entry = ng_entries.get(billerbeck_id)

        if not ng_entry:
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): NOT IN NODEGOAT")
            not_found_count += 1
            continue

        lemma_id = int(local_entry.get("id") or 0)
        presented = canonical_variants.select_presented_variants(cur, lemma_id=lemma_id, ux_mode="multi")
        skip_translation = len(presented) != 1
        if skip_translation:
            if len(presented) > 1:
                canonical_sync_ambiguities.append(
                    {
                        "lemma_id": lemma_id,
                        "lemma": local_entry.get("lemma", ""),
                        "billerbeck_id": billerbeck_id,
                        "reason": "multiple_presented_variants",
                        "presented_count": len(presented),
                        "presented_variants": [summarize_presented_variant(v) for v in presented],
                    }
                )
            else:
                has_any_translation = any(
                    (local_entry.get(col) or "").strip() for col in TRANSLATION_LOCAL_COLUMNS
                )
                has_any_membership = False
                if canonical_variants.table_exists(cur, "lemma_canonical_variants"):
                    cur.execute(
                        """
                        SELECT 1
                        FROM lemma_canonical_variants
                        WHERE lemma_id = %s
                          AND is_active = TRUE
                        LIMIT 1
                        """,
                        (lemma_id,),
                    )
                    has_any_membership = bool(cur.fetchone())

                if has_any_translation or has_any_membership:
                    canonical_sync_ambiguities.append(
                        {
                            "lemma_id": lemma_id,
                            "lemma": local_entry.get("lemma", ""),
                            "billerbeck_id": billerbeck_id,
                            "reason": "zero_presented_variants",
                            "presented_count": 0,
                            "presented_variants": [],
                            "zero_presented_detail": describe_zero_presented(cur, lemma_id),
                        }
                    )

        payload = build_push_payload(local_entry, ng_entry, skip_translation=skip_translation)

        if not payload:
            skipped_count += 1
            continue

        fields_to_update = list(payload["object_definitions"].keys())
        field_names = [k for k, v in NG_FIELDS.items() if str(v) in fields_to_update]

        if dry_run:
            print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): Would update {field_names}")
            pushed_count += 1
            continue

        # Build full update payload (PUT) to avoid PATCH side effects
        full_payload = build_full_update_payload(ng_entry, payload)

        pending_updates.append(
            {
                "i": i,
                "local_entry": local_entry,
                "ng_entry": ng_entry,
                "full_payload": full_payload,
                "field_names": field_names,
            }
        )

    # Execute in batches to reduce HTTP overhead.
    for batch_start in range(0, len(pending_updates), batch_size):
        batch = pending_updates[batch_start:batch_start + batch_size]
        updates = {int(item["ng_entry"]["object_id"]): item["full_payload"] for item in batch}

        try:
            result = client.update_objects(
                type_id=int(NODEGOAT_LEMMA_TYPE_ID),
                updates=updates,
                project_id=NODEGOAT_PROJECT_ID,
            )
            if verbose:
                ids = [int(item["ng_entry"]["object_id"]) for item in batch]
                print(f"  Batch PUT ({len(batch)} objects): {ids} response {result}")

            for item in batch:
                i = item["i"]
                local_entry = item["local_entry"]
                ng_entry = item["ng_entry"]
                field_names = item["field_names"]
                billerbeck_id = local_entry["billerbeck_id"]

                # Update sync timestamp and nodegoat_id
                cur.execute(
                    """
                    UPDATE assembled_lemmas
                    SET last_synced_to_nodegoat_at = NOW(),
                        nodegoat_id = %s
                    WHERE id = %s
                    """,
                    (ng_entry["nodegoat_id"], local_entry["id"]),
                )

                pushed_count += 1
                print(
                    f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): Updated {field_names}"
                )

        except Exception as e:
            print(f"  Batch PUT ERROR ({len(batch)} objects): {e}")

            # Fallback: try single-object updates so one bad payload doesn't block the rest.
            if len(batch) == 1:
                item = batch[0]
                i = item["i"]
                local_entry = item["local_entry"]
                ng_entry = item["ng_entry"]
                field_names = item["field_names"]
                billerbeck_id = local_entry["billerbeck_id"]
                print(f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): ERROR - {e}")
                continue

            for item in batch:
                i = item["i"]
                local_entry = item["local_entry"]
                ng_entry = item["ng_entry"]
                full_payload = item["full_payload"]
                field_names = item["field_names"]
                billerbeck_id = local_entry["billerbeck_id"]

                try:
                    result = client.update_objects(
                        type_id=int(NODEGOAT_LEMMA_TYPE_ID),
                        updates={int(ng_entry["object_id"]): full_payload},
                        project_id=NODEGOAT_PROJECT_ID,
                    )
                    if verbose:
                        print(
                            f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): PUT response {result}"
                        )

                    cur.execute(
                        """
                        UPDATE assembled_lemmas
                        SET last_synced_to_nodegoat_at = NOW(),
                            nodegoat_id = %s
                        WHERE id = %s
                        """,
                        (ng_entry["nodegoat_id"], local_entry["id"]),
                    )

                    pushed_count += 1
                    print(
                        f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): Updated {field_names}"
                    )

                except Exception as e2:
                    print(
                        f"  [{i+1}/{len(local_entries)}] {local_entry['lemma']} ({billerbeck_id}): ERROR - {e2}"
                    )

    if not dry_run:
        json_path, html_path = write_canonical_sync_ambiguity_report(canonical_sync_ambiguities)
        print(f"Wrote canonical sync ambiguity report ({len(canonical_sync_ambiguities)} lemmas): {json_path} {html_path}")
        conn.commit()

    return pushed_count, skipped_count, not_found_count


def pull_from_nodegoat(
    client: NodegoatClient,
    conn,
    ng_entries: dict,
    limit: int = None,
    dry_run: bool = False,
    verbose: bool = False,
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
        if verbose:
            print(f"  [{i+1}/{len(entries_to_check)}] {ng_entry['object_name']} ({billerbeck_id}): Applied updates {updates}")

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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Push only: number of objects per bulk PUT update (default: 25)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without making them")
    parser.add_argument("--verbose", action="store_true", help="Print raw nodegoat responses")
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
                client,
                conn,
                local_entries,
                ng_entries,
                args.dry_run,
                args.verbose,
                batch_size=args.batch_size,
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
            client, conn, ng_entries, args.limit, args.dry_run, args.verbose
        )
        print()
        print(f"Pulled: {pulled}")
        print(f"Skipped (no changes): {skipped}")

    conn.close()
    print()
    print("Done.")


if __name__ == "__main__":
    main()
