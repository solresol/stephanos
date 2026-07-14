#!/usr/bin/env python3
"""Small helpers for durable OpenAI Batch API jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from openai import OpenAI
from psycopg2.extras import Json


CHAT_COMPLETIONS_BATCH_ENDPOINT = "/v1/chat/completions"
RESPONSES_BATCH_ENDPOINT = "/v1/responses"
BATCH_ENDPOINT = CHAT_COMPLETIONS_BATCH_ENDPOINT
BATCH_ENDPOINTS = {
    CHAT_COMPLETIONS_BATCH_ENDPOINT,
    RESPONSES_BATCH_ENDPOINT,
}
BATCH_DIR = Path("tmp/openai_batches")


def normalize_batch_endpoint(endpoint: str | None) -> str:
    value = (endpoint or BATCH_ENDPOINT).strip()
    if value not in BATCH_ENDPOINTS:
        raise ValueError(f"Unsupported OpenAI Batch endpoint: {value}")
    return value


def ensure_openai_batch_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS openai_batch_jobs (
            id SERIAL PRIMARY KEY,
            purpose TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            model TEXT,
            openai_batch_id TEXT UNIQUE,
            input_file_id TEXT,
            output_file_id TEXT,
            error_file_id TEXT,
            status TEXT NOT NULL DEFAULT 'creating',
            request_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            input_path TEXT,
            output_path TEXT,
            error_path TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            submitted_at TIMESTAMPTZ,
            last_polled_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT openai_batch_jobs_purpose_check
                CHECK (purpose IN ('translation', 'translation_guidance_scan')),
            CONSTRAINT openai_batch_jobs_request_count_check CHECK (request_count >= 0),
            CONSTRAINT openai_batch_jobs_completed_count_check CHECK (completed_count >= 0),
            CONSTRAINT openai_batch_jobs_failed_count_check CHECK (failed_count >= 0)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS openai_batch_items (
            id SERIAL PRIMARY KEY,
            batch_job_id INTEGER NOT NULL REFERENCES openai_batch_jobs(id) ON DELETE CASCADE,
            custom_id TEXT NOT NULL UNIQUE,
            purpose TEXT NOT NULL,
            local_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted',
            tokens_used INTEGER NOT NULL DEFAULT 0,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            response_json JSONB,
            error_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT openai_batch_items_purpose_check
                CHECK (purpose IN ('translation', 'translation_guidance_scan')),
            CONSTRAINT openai_batch_items_status_check
                CHECK (status IN ('submitted', 'completed', 'failed', 'expired')),
            CONSTRAINT openai_batch_items_tokens_used_check CHECK (tokens_used >= 0)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS openai_batch_jobs_purpose_status_idx
        ON openai_batch_jobs (purpose, status, created_at DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS openai_batch_items_job_status_idx
        ON openai_batch_items (batch_job_id, status, local_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS openai_batch_items_purpose_local_idx
        ON openai_batch_items (purpose, local_id, created_at DESC)
        """
    )


def create_batch_job(
    cur,
    *,
    purpose: str,
    model: str | None,
    endpoint: str = BATCH_ENDPOINT,
    metadata: dict | None = None,
) -> int:
    endpoint = normalize_batch_endpoint(endpoint)
    cur.execute(
        """
        INSERT INTO openai_batch_jobs (purpose, endpoint, model, metadata, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        RETURNING id
        """,
        (purpose, endpoint, model, Json(metadata or {})),
    )
    return int(cur.fetchone()[0])


def batch_path(job_id: int, suffix: str) -> Path:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    return BATCH_DIR / f"openai_batch_{job_id}.{suffix}"


def write_batch_input(job_id: int, records: Iterable[dict]) -> Path:
    path = batch_path(job_id, "input.jsonl")
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")
    return path


def insert_batch_item(
    cur,
    *,
    batch_job_id: int,
    custom_id: str,
    purpose: str,
    local_id: int,
    metadata: dict | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO openai_batch_items (
            batch_job_id, custom_id, purpose, local_id, metadata, updated_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (custom_id) DO NOTHING
        """,
        (batch_job_id, custom_id, purpose, int(local_id), Json(metadata or {})),
    )


def submit_batch(
    client: OpenAI,
    cur,
    *,
    job_id: int,
    records: list[dict],
    endpoint: str = BATCH_ENDPOINT,
) -> str:
    endpoint = normalize_batch_endpoint(endpoint)
    record_endpoints = {str(record.get("url") or "").strip() for record in records}
    if record_endpoints != {endpoint}:
        raise ValueError(
            "Every OpenAI Batch record must target the job endpoint "
            f"{endpoint}; found {sorted(record_endpoints)}"
        )
    input_path = write_batch_input(job_id, records)
    with input_path.open("rb") as fh:
        input_file = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=input_file.id,
        endpoint=endpoint,
        completion_window="24h",
        metadata={"stephanos_batch_job_id": str(job_id)},
    )
    cur.execute(
        """
        UPDATE openai_batch_jobs
        SET openai_batch_id = %s,
            input_file_id = %s,
            status = %s,
            request_count = %s,
            input_path = %s,
            submitted_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (batch.id, input_file.id, batch.status, len(records), str(input_path), job_id),
    )
    return batch.id


def update_batch_status(cur, *, job_id: int, batch) -> None:
    counts = getattr(batch, "request_counts", None)
    completed_count = int(getattr(counts, "completed", 0) or 0) if counts else 0
    failed_count = int(getattr(counts, "failed", 0) or 0) if counts else 0
    completed_at = getattr(batch, "completed_at", None)
    cur.execute(
        """
        UPDATE openai_batch_jobs
        SET status = %s,
            output_file_id = %s,
            error_file_id = %s,
            completed_count = %s,
            failed_count = %s,
            completed_at = CASE WHEN %s IS NOT NULL THEN to_timestamp(%s) ELSE completed_at END,
            last_polled_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            batch.status,
            getattr(batch, "output_file_id", None),
            getattr(batch, "error_file_id", None),
            completed_count,
            failed_count,
            completed_at,
            completed_at,
            job_id,
        ),
    )


def get_batch_job(cur, *, job_id: int | None = None, openai_batch_id: str | None = None):
    if job_id is not None:
        cur.execute("SELECT * FROM openai_batch_jobs WHERE id = %s", (int(job_id),))
    elif openai_batch_id:
        cur.execute("SELECT * FROM openai_batch_jobs WHERE openai_batch_id = %s", (openai_batch_id,))
    else:
        raise ValueError("job_id or openai_batch_id is required")
    return cur.fetchone()


def get_recoverable_batch_job_ids(cur, *, purpose: str) -> list[int]:
    cur.execute(
        """
        SELECT DISTINCT j.id
        FROM openai_batch_jobs j
        WHERE j.purpose = %s
          AND j.openai_batch_id IS NOT NULL
          AND (
              j.status NOT IN ('completed', 'failed', 'expired', 'cancelled')
              OR EXISTS (
                  SELECT 1
                  FROM openai_batch_items i
                  WHERE i.batch_job_id = j.id
                    AND i.status = 'submitted'
              )
          )
        ORDER BY j.id
        """,
        (purpose,),
    )
    return [int(row[0]) for row in cur.fetchall()]


def get_batch_items(cur, *, job_id: int) -> dict[str, dict]:
    cur.execute(
        """
        SELECT custom_id, local_id, status, metadata
        FROM openai_batch_items
        WHERE batch_job_id = %s
        """,
        (int(job_id),),
    )
    return {
        row[0]: {
            "local_id": int(row[1]),
            "status": row[2],
            "metadata": row[3] or {},
        }
        for row in cur.fetchall()
    }


def file_content_text(client: OpenAI, file_id: str) -> str:
    response = client.files.content(file_id)
    if hasattr(response, "text"):
        return response.text
    if hasattr(response, "read"):
        data = response.read()
    elif hasattr(response, "content"):
        data = response.content
    else:
        data = response
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


def write_batch_output(job_id: int, *, kind: str, text: str) -> Path:
    path = batch_path(job_id, f"{kind}.jsonl")
    path.write_text(text, encoding="utf-8")
    return path


def iter_jsonl(text: str):
    for line_number, raw_line in enumerate((text or "").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            yield line_number, json.loads(line)
        except json.JSONDecodeError as exc:
            yield line_number, {"custom_id": f"invalid-json-line-{line_number}", "error": {"message": str(exc)}}


def mark_batch_item(
    cur,
    *,
    custom_id: str,
    status: str,
    tokens_used: int = 0,
    response_json: dict | None = None,
    error_json: dict | None = None,
) -> None:
    cur.execute(
        """
        UPDATE openai_batch_items
        SET status = %s,
            tokens_used = %s,
            response_json = %s::jsonb,
            error_json = %s::jsonb,
            updated_at = NOW()
        WHERE custom_id = %s
        """,
        (
            status,
            int(tokens_used or 0),
            Json(response_json) if response_json is not None else None,
            Json(error_json) if error_json is not None else None,
            custom_id,
        ),
    )


def mark_batch_job_error(cur, *, job_id: int, status: str, error_message: str) -> None:
    cur.execute(
        """
        UPDATE openai_batch_jobs
        SET status = %s,
            error_message = %s,
            last_polled_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (status, error_message, int(job_id)),
    )
