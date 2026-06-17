#!/usr/bin/env python3
"""Backfill stored translation request payloads from OpenAI Batch input files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from psycopg2.extras import Json

from db import get_connection
from translate_lemmas import (
    build_translation_request_artifact,
    fetch_guidance_context,
    fetch_source_passage_context,
)

CHAT_COMPLETIONS_ENDPOINT = "/v1/chat/completions"


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def prompt_version_guidance_expr(cur, alias: str = "pv") -> str:
    if column_exists(cur, "translation_prompt_profile_versions", "uses_guidance_context"):
        return f"COALESCE({alias}.uses_guidance_context, FALSE)"
    return "FALSE"


def ensure_request_payload_column(cur) -> None:
    if column_exists(cur, "translation_runs", "request_payload_json"):
        return
    cur.execute(
        """
        ALTER TABLE public.translation_runs
            ADD COLUMN IF NOT EXISTS request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )


def load_batch_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL record: {exc}") from exc
            custom_id = str(record.get("custom_id") or "")
            if custom_id:
                records[custom_id] = record
    return records


def fetch_backfill_candidates(cur, limit: int | None) -> list[dict]:
    query = """
        SELECT
            tr.id AS run_id,
            tr.request_id,
            tr.run_index,
            i.custom_id,
            j.input_path,
            j.created_at
        FROM translation_runs tr
        JOIN openai_batch_items i
          ON i.purpose = 'translation'
         AND i.local_id = tr.request_id
         AND CASE
                WHEN COALESCE(i.metadata->>'run_index', '') ~ '^[0-9]+$'
                    THEN (i.metadata->>'run_index')::integer
                ELSE 0
             END = tr.run_index
        JOIN openai_batch_jobs j ON j.id = i.batch_job_id
        WHERE COALESCE(tr.request_payload_json, '{{}}'::jsonb) = '{{}}'::jsonb
          AND COALESCE(j.input_path, '') <> ''
        ORDER BY tr.id
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query)
    return [
        {
            "run_id": int(row[0]),
            "request_id": int(row[1]),
            "run_index": int(row[2]),
            "custom_id": row[3] or "",
            "input_path": row[4] or "",
            "batch_created_at": row[5],
        }
        for row in cur.fetchall()
    ]


def build_request_payload(candidate: dict, batch_record: dict) -> dict:
    batch_created_at = candidate.get("batch_created_at")
    if hasattr(batch_created_at, "isoformat"):
        captured_at = batch_created_at.isoformat()
    else:
        captured_at = str(batch_created_at or "")
    return {
        "api": "openai.chat.completions",
        "method": batch_record.get("method") or "POST",
        "url": batch_record.get("url") or CHAT_COMPLETIONS_ENDPOINT,
        "transport": "openai_batch",
        "exact_payload": True,
        "custom_id": candidate["custom_id"],
        "captured_at": captured_at,
        "backfilled_at": datetime.now(timezone.utc).isoformat(),
        "backfill_source": {
            "kind": "openai_batch_input_file",
            "input_path": candidate["input_path"],
        },
        "body": batch_record.get("body") or {},
    }


def fetch_reconstruct_candidates(cur, headwords: list[str]) -> list[dict]:
    if not headwords:
        return []
    uses_guidance_context_expr = prompt_version_guidance_expr(cur, alias="pv")
    cur.execute(
        f"""
        SELECT
            tr.id AS run_id,
            tr.request_id,
            tr.run_index,
            tr.model,
            tr.temperature,
            tr.top_p,
            pv.prompt_text,
            stv.id AS source_text_version_id,
            stv.text_body AS source_text,
            stv.source_document,
            a.id AS lemma_id,
            a.lemma,
            a.entry_number,
            {uses_guidance_context_expr} AS uses_guidance_context
        FROM translation_runs tr
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
        JOIN assembled_lemmas a ON a.id = tr.lemma_id
        WHERE COALESCE(tr.request_payload_json, '{{}}'::jsonb) = '{{}}'::jsonb
          AND a.lemma = ANY(%s)
        ORDER BY a.lemma, tr.created_at DESC, tr.id DESC
        """,
        (headwords,),
    )
    return [
        {
            "run_id": int(row[0]),
            "request_id": int(row[1]),
            "run_index": int(row[2]),
            "model": row[3] or "",
            "temperature": float(row[4]) if row[4] is not None else 1.0,
            "top_p": float(row[5]) if row[5] is not None else 1.0,
            "prompt_text": row[6] or "",
            "source_text_version_id": int(row[7]),
            "source_text": row[8] or "",
            "source_document": row[9] or "",
            "lemma_id": int(row[10]),
            "lemma": row[11] or "",
            "entry_number": int(row[12]) if row[12] is not None else None,
            "uses_guidance_context": bool(row[13]),
        }
        for row in cur.fetchall()
    ]


def reconstruct_request_payload(cur, candidate: dict) -> dict:
    guidance_context = []
    if candidate.get("uses_guidance_context"):
        guidance_context = fetch_guidance_context(
            cur,
            lemma_id=candidate["lemma_id"],
            source_text_version_id=candidate["source_text_version_id"],
        )
    source_passage_context = fetch_source_passage_context(
        cur,
        lemma_id=candidate["lemma_id"],
        source_text_version_id=candidate["source_text_version_id"],
    )
    artifact = build_translation_request_artifact(
        model=candidate["model"],
        temperature=candidate["temperature"],
        top_p=candidate["top_p"],
        system_prompt=candidate["prompt_text"],
        lemma=candidate["lemma"],
        entry_number=candidate["entry_number"],
        source_text=candidate["source_text"],
        guidance_context=guidance_context,
        source_passage_context=source_passage_context,
        transport="reconstructed",
        exact_payload=False,
    )
    artifact["reconstructed_at"] = datetime.now(timezone.utc).isoformat()
    artifact["backfill_source"] = {
        "kind": "translation_run_metadata",
        "run_id": candidate["run_id"],
        "request_id": candidate["request_id"],
        "run_index": candidate["run_index"],
        "note": "Reconstructed from the stored prompt profile, source text, and current context tables because the original synchronous API request was not captured.",
    }
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill translation_runs.request_payload_json from saved OpenAI Batch request files."
    )
    parser.add_argument("--limit", type=int, help="Maximum runs to inspect")
    parser.add_argument("--dry-run", action="store_true", help="Report possible updates without writing")
    parser.add_argument(
        "--reconstruct-missing",
        action="store_true",
        help="For explicitly named headwords, reconstruct missing synchronous request artifacts from current metadata.",
    )
    parser.add_argument(
        "--headword",
        action="append",
        default=[],
        help="Headword to reconstruct when --reconstruct-missing is set; may be repeated.",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    required_tables = ["translation_runs", "openai_batch_items", "openai_batch_jobs"]
    missing = [table for table in required_tables if not table_exists(cur, table)]
    if missing:
        print("Missing required tables; no backfill performed:")
        for table in missing:
            print(f"  - {table}")
        conn.close()
        return

    if args.dry_run:
        if not column_exists(cur, "translation_runs", "request_payload_json"):
            print("translation_runs.request_payload_json is missing; apply migrations before backfilling.")
            conn.close()
            return
    else:
        ensure_request_payload_column(cur)
        conn.commit()

    candidates = fetch_backfill_candidates(cur, args.limit)
    print(f"Candidate translation runs missing request payloads: {len(candidates)}")

    records_by_path: dict[str, dict[str, dict]] = {}
    updated = 0
    missing_files = 0
    missing_records = 0

    for candidate in candidates:
        input_path = candidate["input_path"]
        path = Path(input_path)
        if not path.exists():
            missing_files += 1
            continue
        if input_path not in records_by_path:
            records_by_path[input_path] = load_batch_records(path)
        batch_record = records_by_path[input_path].get(candidate["custom_id"])
        if not batch_record:
            missing_records += 1
            continue
        request_payload = build_request_payload(candidate, batch_record)
        if args.dry_run:
            updated += 1
            continue
        cur.execute(
            """
            UPDATE translation_runs
            SET request_payload_json = %s::jsonb
            WHERE id = %s
              AND COALESCE(request_payload_json, '{}'::jsonb) = '{}'::jsonb
            """,
            (Json(request_payload), candidate["run_id"]),
        )
        updated += cur.rowcount

    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()

    action = "would update" if args.dry_run else "updated"
    print(
        f"Backfill {action}: {updated}; missing files: {missing_files}; "
        f"missing batch records: {missing_records}"
    )

    if args.reconstruct_missing:
        candidates = fetch_reconstruct_candidates(cur, args.headword)
        reconstructed = 0
        for candidate in candidates:
            request_payload = reconstruct_request_payload(cur, candidate)
            if args.dry_run:
                reconstructed += 1
                continue
            cur.execute(
                """
                UPDATE translation_runs
                SET request_payload_json = %s::jsonb
                WHERE id = %s
                  AND COALESCE(request_payload_json, '{}'::jsonb) = '{}'::jsonb
                """,
                (Json(request_payload), candidate["run_id"]),
            )
            reconstructed += cur.rowcount
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
        print(f"Reconstructed missing request artifacts: {reconstructed}")

    conn.close()


if __name__ == "__main__":
    main()
