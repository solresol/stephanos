#!/usr/bin/env python3
"""
Extract distinct place clusters for each lemma and store them in PostgreSQL.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from openai import OpenAI
from psycopg2.extras import Json

from api_keys import load_api_key
from db import get_connection
from link_wikidata_places import query_wikidata_places
from source_documents import public_source_document_list_sql, source_document_priority_sql
from place_cluster_extraction import (
    build_wikidata_candidates,
    explicit_place_list_count,
    extract_place_clusters_for_lemma,
    place_cluster_queue_priority,
    preferred_machine_choice,
    rank_place_candidates,
)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def current_meineke_sql(has_source_versions: bool) -> str:
    if not has_source_versions:
        return "COALESCE(a.human_greek_text, a.greek_text, '')"
    return """
        COALESCE(
            current_meineke.text_body,
            a.human_greek_text,
            a.greek_text,
            ''
        )
    """


def load_lemma_rows(cur, *, limit: int | None, lemma_id: int | None, rebuild: bool) -> list[tuple]:
    has_source_versions = table_exists(cur, "lemma_source_text_versions")
    has_proper_nouns = table_exists(cur, "proper_nouns")
    greek_expr = current_meineke_sql(has_source_versions)
    lateral_join = ""
    if has_source_versions:
        lateral_join = f"""
        LEFT JOIN LATERAL (
            SELECT COALESCE(stv.text_body, '') AS text_body
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = a.id
              AND stv.source_document IN ({public_source_document_list_sql()})
              AND COALESCE(stv.source_variant, '') <> 'ocr'
              AND COALESCE(stv.is_current, FALSE) = TRUE
            ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
            LIMIT 1
        ) current_meineke ON TRUE
        """
    place_signal_expr = "0"
    if has_proper_nouns:
        place_signal_expr = """
            COALESCE((
                SELECT COUNT(*)
                FROM proper_nouns pn
                WHERE pn.lemma_id = a.id
                  AND LOWER(COALESCE(pn.noun_type, '')) = 'place'
            ), 0)
        """

    where_clauses = [
        "COALESCE(a.quarantined, FALSE) = FALSE",
        "COALESCE(NULLIF(BTRIM(a.lemma), ''), '') <> ''",
    ]
    params: list = []

    if lemma_id is not None:
        where_clauses.append("a.id = %s")
        params.append(lemma_id)
    elif not rebuild:
        where_clauses.append("COALESCE(a.place_clusters_analyzed, FALSE) = FALSE")

    query = f"""
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            {greek_expr} AS working_greek_text,
            COALESCE(
                a.reviewed_english_translation,
                a.corrected_english_translation,
                a.translation,
                ''
            ) AS english_translation,
            COALESCE(a.type, '') AS lemma_type,
            (
                COALESCE(NULLIF(BTRIM(a.wikidata_place_qid), ''), '') <> ''
                OR COALESCE(NULLIF(BTRIM(a.pleiades_id), ''), '') <> ''
            ) AS has_headword_alignment,
            {place_signal_expr} AS place_signal_count
        FROM assembled_lemmas a
        {lateral_join}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY a.id
    """

    cur.execute(query, params)
    rows = cur.fetchall()
    if lemma_id is not None:
        return [row[:4] for row in rows]

    prioritized_rows = sorted(
        rows,
        key=lambda row: (
            -place_cluster_queue_priority(
                lemma_type=row[4],
                has_headword_alignment=bool(row[5]),
                place_signal_count=int(row[6] or 0),
                explicit_place_list_markers=explicit_place_list_count(row[1], row[2]),
            ),
            row[0],
        ),
    )
    if limit is not None:
        prioritized_rows = prioritized_rows[:limit]
    return [row[:4] for row in prioritized_rows]


def upsert_cluster(cur, lemma_id: int, cluster: dict) -> int:
    cur.execute(
        """
        INSERT INTO place_clusters (
            lemma_id,
            cluster_index,
            display_label,
            inferred_canonical_name,
            place_type,
            region,
            explicit_name_present,
            extraction_confidence,
            extraction_notes,
            preferred_external_id_type,
            preferred_external_id_value,
            wikidata_qid,
            wikidata_label,
            wikidata_description,
            wikidata_confidence,
            topostext_id,
            pleiades_id,
            resolution_status,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (lemma_id, cluster_index) DO UPDATE SET
            display_label = EXCLUDED.display_label,
            inferred_canonical_name = EXCLUDED.inferred_canonical_name,
            place_type = EXCLUDED.place_type,
            region = EXCLUDED.region,
            explicit_name_present = EXCLUDED.explicit_name_present,
            extraction_confidence = EXCLUDED.extraction_confidence,
            extraction_notes = EXCLUDED.extraction_notes,
            preferred_external_id_type = EXCLUDED.preferred_external_id_type,
            preferred_external_id_value = EXCLUDED.preferred_external_id_value,
            wikidata_qid = EXCLUDED.wikidata_qid,
            wikidata_label = EXCLUDED.wikidata_label,
            wikidata_description = EXCLUDED.wikidata_description,
            wikidata_confidence = EXCLUDED.wikidata_confidence,
            topostext_id = EXCLUDED.topostext_id,
            pleiades_id = EXCLUDED.pleiades_id,
            resolution_status = EXCLUDED.resolution_status,
            updated_at = NOW()
        RETURNING id
        """,
        (
            lemma_id,
            cluster["cluster_index"],
            cluster["display_label"],
            cluster["inferred_canonical_name"],
            cluster["place_type"] or None,
            cluster["region"] or None,
            bool(cluster["explicit_name_present"]),
            cluster["extraction_confidence"] or None,
            cluster["extraction_notes"] or None,
            cluster["preferred_external_id_type"] or None,
            cluster["preferred_external_id_value"] or None,
            cluster["wikidata_qid"] or None,
            cluster["wikidata_label"] or None,
            cluster["wikidata_description"] or None,
            cluster["wikidata_confidence"] or None,
            cluster["topostext_id"] or None,
            cluster["pleiades_id"] or None,
            cluster["resolution_status"] or None,
        ),
    )
    return int(cur.fetchone()[0])


def replace_mentions_and_candidates(cur, lemma_id: int, cluster_id: int, cluster: dict) -> None:
    cur.execute("DELETE FROM place_cluster_mentions WHERE place_cluster_id = %s", (cluster_id,))
    cur.execute("DELETE FROM place_cluster_candidates WHERE place_cluster_id = %s", (cluster_id,))

    for mention in cluster.get("mentions", []):
        cur.execute(
            """
            INSERT INTO place_cluster_mentions (
                lemma_id,
                place_cluster_id,
                text_form,
                normalized_form,
                mention_order,
                char_start,
                char_end,
                is_implicit,
                extracted_place_type,
                extracted_region,
                evidence_text,
                machine_notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                lemma_id,
                cluster_id,
                mention.get("text_form"),
                mention.get("normalized_form") or None,
                int(mention.get("mention_order") or 0),
                mention.get("char_start"),
                mention.get("char_end"),
                bool(mention.get("is_implicit")),
                mention.get("extracted_place_type") or None,
                mention.get("extracted_region") or None,
                mention.get("evidence_text") or None,
                mention.get("machine_notes") or None,
            ),
        )

    for candidate in cluster.get("candidates", []):
        cur.execute(
            """
            INSERT INTO place_cluster_candidates (
                place_cluster_id,
                source_name,
                external_id,
                label,
                description,
                place_type,
                region,
                url,
                score,
                rank_order,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (place_cluster_id, source_name, external_id) DO UPDATE SET
                label = EXCLUDED.label,
                description = EXCLUDED.description,
                place_type = EXCLUDED.place_type,
                region = EXCLUDED.region,
                url = EXCLUDED.url,
                score = EXCLUDED.score,
                rank_order = EXCLUDED.rank_order,
                metadata_json = EXCLUDED.metadata_json
            """,
            (
                cluster_id,
                candidate["source_name"],
                candidate["external_id"],
                candidate.get("label") or None,
                candidate.get("description") or None,
                candidate.get("place_type") or None,
                candidate.get("region") or None,
                candidate.get("url") or None,
                candidate.get("score"),
                int(candidate.get("rank_order") or 0),
                Json(candidate.get("metadata_json") or {}),
            ),
        )


def build_cluster_records(headword: str, clusters: list[dict]) -> list[dict]:
    records: list[dict] = []
    for cluster in clusters:
        try:
            raw_candidates = query_wikidata_places(
                cluster.get("candidate_query_text") or cluster.get("inferred_canonical_name") or headword,
                None,
            )
        except Exception as exc:
            print(f"    Warning: candidate lookup failed for {cluster['display_label']}: {exc}")
            raw_candidates = []

        candidate_rows = rank_place_candidates(cluster, build_wikidata_candidates(cluster, raw_candidates))
        machine_choice = preferred_machine_choice(candidate_rows)
        record = dict(cluster)
        record["candidates"] = candidate_rows[:8]
        record.update(machine_choice)
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract per-lemma place clusters for named-entity review.")
    parser.add_argument("--limit", type=int, default=None, help="Legacy alias for --daily-limit")
    parser.add_argument("--daily-limit", type=int, default=None, help="Maximum number of lemmas to process in this run")
    parser.add_argument(
        "--daily-token-limit",
        type=int,
        default=None,
        help="Stop once this many extraction tokens have been used in the current run",
    )
    parser.add_argument("--lemma-id", type=int, default=None, help="Process a single lemma ID")
    parser.add_argument("--model", default="gpt-5.6-luna", help="OpenAI model to use for extraction")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between lemmas")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Re-run extraction for already analyzed lemmas. Existing human review fields are preserved.",
    )
    args = parser.parse_args()
    effective_limit = args.daily_limit if args.daily_limit is not None else args.limit

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "place_clusters"):
        raise RuntimeError("place_clusters table missing. Apply migrations first.")

    lemma_rows = load_lemma_rows(cur, limit=effective_limit, lemma_id=args.lemma_id, rebuild=args.rebuild)
    if not lemma_rows:
        print("No lemmas need place-cluster extraction.")
        conn.close()
        return 0

    total_tokens = 0
    print(f"Extracting place clusters for {len(lemma_rows)} lemmas...")

    for index, (lemma_id, headword, greek_text, english_translation) in enumerate(lemma_rows, start=1):
        if args.daily_token_limit is not None and total_tokens >= args.daily_token_limit:
            print(f"Reached daily token limit ({args.daily_token_limit:,}); stopping.")
            break

        if not (greek_text or "").strip():
            cur.execute(
                """
                UPDATE assembled_lemmas
                SET place_clusters_analyzed = TRUE,
                    place_clusters_analyzed_at = %s
                WHERE id = %s
                """,
                (datetime.now(timezone.utc), lemma_id),
            )
            conn.commit()
            continue

        print(f"  [{index}/{len(lemma_rows)}] {headword}...", end=" ", flush=True)
        try:
            clusters, tokens = extract_place_clusters_for_lemma(
                client,
                headword=headword,
                greek_text=greek_text,
                english_translation=english_translation or "",
                model=args.model,
            )
            total_tokens += tokens
            records = build_cluster_records(headword, clusters)

            for record in records:
                cluster_id = upsert_cluster(cur, lemma_id, record)
                replace_mentions_and_candidates(cur, lemma_id, cluster_id, record)

            cur.execute(
                """
                UPDATE assembled_lemmas
                SET place_clusters_analyzed = TRUE,
                    place_clusters_analyzed_at = %s
                WHERE id = %s
                """,
                (datetime.now(timezone.utc), lemma_id),
            )
            conn.commit()
            print(f"OK ({len(records)} clusters, {tokens} tokens)")
        except Exception as exc:
            conn.rollback()
            print(f"ERROR: {exc}")

        if args.delay > 0:
            time.sleep(args.delay)

    conn.close()
    print(f"\nPlace-cluster extraction complete. Total tokens used: {total_tokens:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
