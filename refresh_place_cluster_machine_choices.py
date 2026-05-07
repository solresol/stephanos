#!/usr/bin/env python3
"""
Recompute machine-preferred authority IDs from existing place-cluster candidates.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from db import get_connection
from place_cluster_extraction import preferred_machine_choice, rank_place_candidates


def load_cluster_rows(cur, *, lemma_id: int | None, limit: int | None) -> list[dict]:
    params: list[object] = []
    where = ""
    if lemma_id is not None:
        where = "WHERE pc.lemma_id = %s"
        params.append(lemma_id)
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(limit)

    cur.execute(
        f"""
        SELECT
            pc.id,
            pc.lemma_id,
            pc.display_label,
            pc.inferred_canonical_name,
            pc.place_type,
            pc.region
        FROM place_clusters pc
        {where}
        ORDER BY pc.lemma_id, pc.cluster_index, pc.id
        {limit_sql}
        """,
        params,
    )
    return [
        {
            "id": int(row[0]),
            "lemma_id": int(row[1]),
            "display_label": row[2] or "",
            "inferred_canonical_name": row[3] or "",
            "place_type": row[4] or "",
            "region": row[5] or "",
        }
        for row in cur.fetchall()
    ]


def load_mentions_by_cluster(cur, cluster_ids: list[int]) -> dict[int, list[dict]]:
    if not cluster_ids:
        return {}
    cur.execute(
        """
        SELECT place_cluster_id, text_form, normalized_form, mention_order
        FROM place_cluster_mentions
        WHERE place_cluster_id = ANY(%s)
        ORDER BY place_cluster_id, mention_order, id
        """,
        (cluster_ids,),
    )
    mentions_by_cluster: dict[int, list[dict]] = defaultdict(list)
    for cluster_id, text_form, normalized_form, mention_order in cur.fetchall():
        mentions_by_cluster[int(cluster_id)].append(
            {
                "text_form": text_form or "",
                "normalized_form": normalized_form or "",
                "mention_order": mention_order,
            }
        )
    return mentions_by_cluster


def load_candidates_by_cluster(cur, cluster_ids: list[int]) -> dict[int, list[dict]]:
    if not cluster_ids:
        return {}
    cur.execute(
        """
        SELECT
            place_cluster_id,
            source_name,
            external_id,
            label,
            description,
            place_type,
            region,
            url,
            metadata_json
        FROM place_cluster_candidates
        WHERE place_cluster_id = ANY(%s)
        ORDER BY place_cluster_id, rank_order, id
        """,
        (cluster_ids,),
    )
    candidates_by_cluster: dict[int, list[dict]] = defaultdict(list)
    for row in cur.fetchall():
        (
            cluster_id,
            source_name,
            external_id,
            label,
            description,
            place_type,
            region,
            url,
            metadata_json,
        ) = row
        candidates_by_cluster[int(cluster_id)].append(
            {
                "source_name": source_name or "",
                "external_id": external_id or "",
                "label": label or "",
                "description": description or "",
                "place_type": place_type or "",
                "region": region or "",
                "url": url or "",
                "metadata_json": metadata_json or {},
            }
        )
    return candidates_by_cluster


def update_machine_choice(cur, cluster_id: int, machine_choice: dict) -> None:
    cur.execute(
        """
        UPDATE place_clusters
        SET
            preferred_external_id_type = %s,
            preferred_external_id_value = %s,
            wikidata_qid = %s,
            wikidata_label = %s,
            wikidata_description = %s,
            wikidata_confidence = %s,
            topostext_id = %s,
            pleiades_id = %s,
            resolution_status = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            machine_choice["preferred_external_id_type"] or None,
            machine_choice["preferred_external_id_value"] or None,
            machine_choice["wikidata_qid"] or None,
            machine_choice["wikidata_label"] or None,
            machine_choice["wikidata_description"] or None,
            machine_choice["wikidata_confidence"] or None,
            machine_choice["topostext_id"] or None,
            machine_choice["pleiades_id"] or None,
            machine_choice["resolution_status"] or None,
            cluster_id,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh place-cluster machine choices from stored candidates.")
    parser.add_argument("--lemma-id", type=int, default=None, help="Refresh only one lemma")
    parser.add_argument("--limit", type=int, default=None, help="Maximum clusters to refresh")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without updating the database")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    try:
        clusters = load_cluster_rows(cur, lemma_id=args.lemma_id, limit=args.limit)
        cluster_ids = [cluster["id"] for cluster in clusters]
        mentions_by_cluster = load_mentions_by_cluster(cur, cluster_ids)
        candidates_by_cluster = load_candidates_by_cluster(cur, cluster_ids)

        changed = 0
        for cluster in clusters:
            cluster["mentions"] = mentions_by_cluster.get(cluster["id"], [])
            candidates = candidates_by_cluster.get(cluster["id"], [])
            machine_choice = preferred_machine_choice(rank_place_candidates(cluster, candidates))
            if machine_choice["resolution_status"] == "unresolved" and candidates:
                changed += 1
            if args.dry_run:
                print(
                    f"{cluster['lemma_id']}\t{cluster['id']}\t{cluster['display_label']}\t"
                    f"{machine_choice['resolution_status']}\t{machine_choice['wikidata_qid']}"
                )
            else:
                update_machine_choice(cur, cluster["id"], machine_choice)

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
        print(f"Refreshed {len(clusters)} place clusters; unresolved_with_candidates={changed}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
