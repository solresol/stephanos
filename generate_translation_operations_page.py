#!/usr/bin/env python3
"""Generate translation queue and model-cost operations page."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from db import get_connection
from model_pricing import MODEL_PRICING, PRICING_AS_OF, pricing_for_model
from site_navigation import render_site_breadcrumbs, render_site_navigation, site_navigation_styles
from source_documents import public_source_document_list_sql, source_document_priority_sql


OUTPUT_PATH = Path("reference_site/statistics/translation_operations.html")
SUCCESSFUL_TRANSLATION_STATUSES = ("completed", "approved", "blocked", "hidden")


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


def approved_human_expr(cur, assembled_alias: str = "a") -> str:
    if table_exists(cur, "human_translations"):
        human_clause = f"""
            OR EXISTS (
                SELECT 1
                FROM human_translations ht
                WHERE ht.lemma_id = {assembled_alias}.id
                  AND ht.status = 'approved'
                  AND ht.stage IN ('reviewed', 'final')
                  AND COALESCE(ht.translation_text, '') <> ''
            )
        """
    else:
        human_clause = ""
    return f"""
        (
            COALESCE({assembled_alias}.reviewed_english_translation, '') <> ''
            {human_clause}
        )
    """


def text_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return escape(text)


def int_cell(value: object) -> str:
    return f"{int(value or 0):,}"


def number_cell(value: object, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}"


def percent_cell(part: object, total: object) -> str:
    total_value = float(total or 0)
    if total_value <= 0:
        return "-"
    return f"{(float(part or 0) / total_value) * 100:,.1f}%"


def money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.4f}"


def token_cell(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.0f}"


def estimate_cost(model: str | None, input_tokens: float | None, output_tokens: float | None) -> float | None:
    pricing = pricing_for_model(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return pricing.estimate(input_tokens=int(round(input_tokens)), output_tokens=int(round(output_tokens)))


def short_datetime(value: object) -> str:
    if value is None:
        return "-"
    return str(value).split(".")[0]


def request_expr(cur, request_column: str, version_column: str, fallback: str) -> str:
    request_has = column_exists(cur, "translation_run_requests", request_column)
    version_has = column_exists(cur, "translation_prompt_profile_versions", version_column)
    if request_has and version_has:
        return f"COALESCE(NULLIF(trr.{request_column}::text, ''), NULLIF(pv.{version_column}::text, ''), {fallback})"
    if request_has:
        return f"COALESCE(NULLIF(trr.{request_column}::text, ''), {fallback})"
    if version_has:
        return f"COALESCE(NULLIF(pv.{version_column}::text, ''), {fallback})"
    return fallback


def numeric_request_expr(cur, request_column: str, version_column: str) -> str:
    request_has = column_exists(cur, "translation_run_requests", request_column)
    version_has = column_exists(cur, "translation_prompt_profile_versions", version_column)
    if request_has and version_has:
        return f"COALESCE(trr.{request_column}, pv.{version_column})"
    if request_has:
        return f"trr.{request_column}"
    if version_has:
        return f"pv.{version_column}"
    return "NULL"


def fetch_queue_summary(cur) -> list[dict[str, object]]:
    if not table_exists(cur, "translation_run_requests"):
        return []
    priority_expr = "COALESCE(trr.priority, 100)" if column_exists(cur, "translation_run_requests", "priority") else "100"
    model_expr = request_expr(cur, "model", "default_model", "'gpt-5.5'")
    api_mode_expr = request_expr(cur, "api_mode", "default_api_mode", "'chat_completions'")
    reasoning_expr = request_expr(cur, "reasoning_effort", "default_reasoning_effort", "''")
    temperature_expr = numeric_request_expr(cur, "temperature", "default_temperature")
    top_p_expr = numeric_request_expr(cur, "top_p", "default_top_p")
    approved_expr = approved_human_expr(cur)
    cur.execute(
        f"""
        SELECT
            CASE WHEN {approved_expr} THEN 'approved-human' ELSE 'other' END AS queue_class,
            trr.status,
            {priority_expr} AS priority,
            p.name AS profile_name,
            pv.version AS profile_version,
            {model_expr} AS model,
            {api_mode_expr} AS api_mode,
            {reasoning_expr} AS reasoning_effort,
            {temperature_expr} AS temperature,
            {top_p_expr} AS top_p,
            COUNT(*) AS request_count,
            MIN(trr.created_at) AS oldest_request,
            MAX(trr.created_at) AS newest_request
        FROM translation_run_requests trr
        JOIN translation_prompt_profiles p ON p.id = trr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = trr.profile_version_id
        JOIN assembled_lemmas a ON a.id = trr.lemma_id
        WHERE trr.status IN ('pending', 'running')
        GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
        ORDER BY 1 ASC, 3 ASC, 11 DESC, 4 ASC, 5 ASC
        """,
    )
    keys = [
        "queue_class",
        "status",
        "priority",
        "profile_name",
        "profile_version",
        "model",
        "api_mode",
        "reasoning_effort",
        "temperature",
        "top_p",
        "request_count",
        "oldest_request",
        "newest_request",
    ]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def fetch_profile_controls(cur) -> list[dict[str, object]]:
    if not table_exists(cur, "translation_prompt_profile_versions"):
        return []
    approved_col = (
        "COALESCE(pv.approved_human_only, FALSE)"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only")
        else "FALSE"
    )
    model_col = (
        "pv.default_model"
        if column_exists(cur, "translation_prompt_profile_versions", "default_model")
        else "NULL::text"
    )
    temperature_col = (
        "pv.default_temperature"
        if column_exists(cur, "translation_prompt_profile_versions", "default_temperature")
        else "NULL::double precision"
    )
    top_p_col = (
        "pv.default_top_p"
        if column_exists(cur, "translation_prompt_profile_versions", "default_top_p")
        else "NULL::double precision"
    )
    api_col = (
        "pv.default_api_mode"
        if column_exists(cur, "translation_prompt_profile_versions", "default_api_mode")
        else "'chat_completions'::text"
    )
    reasoning_col = (
        "pv.default_reasoning_effort"
        if column_exists(cur, "translation_prompt_profile_versions", "default_reasoning_effort")
        else "NULL::text"
    )
    requested_runs_col = (
        "pv.default_requested_runs"
        if column_exists(cur, "translation_prompt_profile_versions", "default_requested_runs")
        else "1"
    )
    priority_col = (
        "pv.approved_human_queue_priority"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_queue_priority")
        else "5"
    )
    cur.execute(
        f"""
        WITH request_counts AS (
            SELECT
                profile_version_id,
                COUNT(*) FILTER (WHERE status IN ('pending', 'running')) AS queued_requests,
                COUNT(*) FILTER (WHERE status = 'running') AS running_requests
            FROM translation_run_requests
            GROUP BY profile_version_id
        ),
        run_counts AS (
            SELECT
                profile_version_id,
                COUNT(*) FILTER (WHERE status IN ('completed', 'approved', 'blocked', 'hidden')) AS completed_runs,
                AVG(NULLIF(tokens_used, 0)) AS avg_tokens
            FROM translation_runs
            GROUP BY profile_version_id
        )
        SELECT
            p.name,
            pv.version,
            pv.active,
            {approved_col} AS approved_human_only,
            {model_col} AS default_model,
            {temperature_col} AS default_temperature,
            {top_p_col} AS default_top_p,
            {api_col} AS default_api_mode,
            {reasoning_col} AS default_reasoning_effort,
            {requested_runs_col} AS default_requested_runs,
            {priority_col} AS approved_human_queue_priority,
            COALESCE(request_counts.queued_requests, 0) AS queued_requests,
            COALESCE(request_counts.running_requests, 0) AS running_requests,
            COALESCE(run_counts.completed_runs, 0) AS completed_runs,
            run_counts.avg_tokens
        FROM translation_prompt_profile_versions pv
        JOIN translation_prompt_profiles p ON p.id = pv.profile_id
        LEFT JOIN request_counts ON request_counts.profile_version_id = pv.id
        LEFT JOIN run_counts ON run_counts.profile_version_id = pv.id
        WHERE p.active = TRUE
        ORDER BY
            CASE WHEN {approved_col} THEN 0 ELSE 1 END,
            p.name,
            pv.version
        """,
    )
    keys = [
        "profile_name",
        "profile_version",
        "active",
        "approved_human_only",
        "default_model",
        "default_temperature",
        "default_top_p",
        "default_api_mode",
        "default_reasoning_effort",
        "default_requested_runs",
        "approved_human_queue_priority",
        "queued_requests",
        "running_requests",
        "completed_runs",
        "avg_tokens",
    ]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def fetch_model_costs(cur) -> list[dict[str, object]]:
    if not table_exists(cur, "translation_runs"):
        return []
    api_col = "COALESCE(NULLIF(api_mode, ''), 'chat_completions')" if column_exists(cur, "translation_runs", "api_mode") else "'chat_completions'"
    reasoning_col = "COALESCE(NULLIF(reasoning_effort, ''), '')" if column_exists(cur, "translation_runs", "reasoning_effort") else "''"
    input_col = "input_tokens" if column_exists(cur, "translation_runs", "input_tokens") else "0"
    output_col = "output_tokens" if column_exists(cur, "translation_runs", "output_tokens") else "0"
    reasoning_tokens_col = "reasoning_tokens" if column_exists(cur, "translation_runs", "reasoning_tokens") else "0"
    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(model, ''), 'unknown') AS model,
            {api_col} AS api_mode,
            {reasoning_col} AS reasoning_effort,
            COUNT(*) AS total_runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            COALESCE(SUM({input_col}), 0) AS input_tokens,
            COALESCE(SUM({output_col}), 0) AS output_tokens,
            COALESCE(SUM({reasoning_tokens_col}), 0) AS reasoning_tokens,
            COALESCE(SUM(tokens_used), 0) AS total_tokens,
            AVG(NULLIF(tokens_used, 0)) AS avg_tokens,
            MAX(completed_at) AS last_completed
        FROM translation_runs
        WHERE status IN ('completed', 'approved', 'blocked', 'hidden')
        GROUP BY 1, 2, 3
        ORDER BY total_runs DESC, model, api_mode, reasoning_effort
        """,
    )
    rows = []
    keys = [
        "model",
        "api_mode",
        "reasoning_effort",
        "total_runs",
        "priced_runs",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "avg_tokens",
        "last_completed",
    ]
    for raw in cur.fetchall():
        row = dict(zip(keys, raw))
        pricing = pricing_for_model(str(row["model"]))
        estimated_cost = None
        avg_cost = None
        if pricing and int(row["priced_runs"] or 0) > 0:
            estimated_cost = pricing.estimate(
                input_tokens=int(row["input_tokens"] or 0),
                output_tokens=int(row["output_tokens"] or 0),
            )
            avg_cost = estimated_cost / int(row["priced_runs"])
        row["pricing"] = pricing
        row["estimated_cost"] = estimated_cost
        row["avg_cost"] = avg_cost
        rows.append(row)
    rows.sort(key=lambda row: (-(row["estimated_cost"] or 0), -int(row["total_runs"] or 0), str(row["model"])))
    return rows


def _numeric(value: object) -> float | None:
    return None if value is None else float(value)


def fetch_token_sample_stats(cur) -> dict[str, object]:
    if not table_exists(cur, "translation_runs"):
        return {
            "profile": {},
            "model_exact": {},
            "model": {},
            "global": None,
            "legacy_v3": None,
        }
    api_col = "COALESCE(NULLIF(tr.api_mode, ''), 'chat_completions')" if column_exists(cur, "translation_runs", "api_mode") else "'chat_completions'"
    reasoning_col = "COALESCE(NULLIF(tr.reasoning_effort, ''), '')" if column_exists(cur, "translation_runs", "reasoning_effort") else "''"
    input_col = "tr.input_tokens" if column_exists(cur, "translation_runs", "input_tokens") else "0"
    output_col = "tr.output_tokens" if column_exists(cur, "translation_runs", "output_tokens") else "0"
    reasoning_tokens_col = "tr.reasoning_tokens" if column_exists(cur, "translation_runs", "reasoning_tokens") else "0"
    status_list = list(SUCCESSFUL_TRANSLATION_STATUSES)

    def stat_from_row(row) -> dict[str, object]:
        return {
            "runs": int(row[0] or 0),
            "priced_runs": int(row[1] or 0),
            "avg_input": _numeric(row[2]),
            "avg_output": _numeric(row[3]),
            "avg_reasoning": _numeric(row[4]),
            "avg_total": _numeric(row[5]),
        }

    cur.execute(
        f"""
        SELECT
            tr.profile_version_id,
            COALESCE(NULLIF(tr.model, ''), 'unknown') AS model,
            {api_col} AS api_mode,
            {reasoning_col} AS reasoning_effort,
            COUNT(*) AS runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            AVG(NULLIF({input_col}, 0)) AS avg_input,
            AVG(NULLIF({output_col}, 0)) AS avg_output,
            AVG(NULLIF({reasoning_tokens_col}, 0)) AS avg_reasoning,
            AVG(NULLIF(tr.tokens_used, 0)) AS avg_total
        FROM translation_runs tr
        WHERE tr.status = ANY(%s)
          AND COALESCE(tr.translation_text, '') <> ''
        GROUP BY tr.profile_version_id, model, api_mode, reasoning_effort
        """,
        (status_list,),
    )
    profile_stats = {}
    for row in cur.fetchall():
        profile_stats[int(row[0])] = stat_from_row(row[4:])

    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(tr.model, ''), 'unknown') AS model,
            {api_col} AS api_mode,
            {reasoning_col} AS reasoning_effort,
            COUNT(*) AS runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            AVG(NULLIF({input_col}, 0)) AS avg_input,
            AVG(NULLIF({output_col}, 0)) AS avg_output,
            AVG(NULLIF({reasoning_tokens_col}, 0)) AS avg_reasoning,
            AVG(NULLIF(tr.tokens_used, 0)) AS avg_total
        FROM translation_runs tr
        WHERE tr.status = ANY(%s)
          AND COALESCE(tr.translation_text, '') <> ''
        GROUP BY model, api_mode, reasoning_effort
        """,
        (status_list,),
    )
    model_exact_stats = {}
    for row in cur.fetchall():
        model_exact_stats[(row[0] or "", row[1] or "", row[2] or "")] = stat_from_row(row[3:])

    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(tr.model, ''), 'unknown') AS model,
            COUNT(*) AS runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            AVG(NULLIF({input_col}, 0)) AS avg_input,
            AVG(NULLIF({output_col}, 0)) AS avg_output,
            AVG(NULLIF({reasoning_tokens_col}, 0)) AS avg_reasoning,
            AVG(NULLIF(tr.tokens_used, 0)) AS avg_total
        FROM translation_runs tr
        WHERE tr.status = ANY(%s)
          AND COALESCE(tr.translation_text, '') <> ''
        GROUP BY model
        """,
        (status_list,),
    )
    model_stats = {}
    for row in cur.fetchall():
        model_stats[row[0] or ""] = stat_from_row(row[1:])

    cur.execute(
        f"""
        SELECT
            COUNT(*) AS runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            AVG(NULLIF({input_col}, 0)) AS avg_input,
            AVG(NULLIF({output_col}, 0)) AS avg_output,
            AVG(NULLIF({reasoning_tokens_col}, 0)) AS avg_reasoning,
            AVG(NULLIF(tr.tokens_used, 0)) AS avg_total
        FROM translation_runs tr
        WHERE tr.status = ANY(%s)
          AND COALESCE(tr.translation_text, '') <> ''
        """,
        (status_list,),
    )
    global_stat = stat_from_row(cur.fetchone())

    cur.execute(
        f"""
        SELECT
            COUNT(*) AS runs,
            COUNT(*) FILTER (WHERE COALESCE({input_col}, 0) > 0 OR COALESCE({output_col}, 0) > 0) AS priced_runs,
            AVG(NULLIF({input_col}, 0)) AS avg_input,
            AVG(NULLIF({output_col}, 0)) AS avg_output,
            AVG(NULLIF({reasoning_tokens_col}, 0)) AS avg_reasoning,
            AVG(NULLIF(tr.tokens_used, 0)) AS avg_total
        FROM translation_runs tr
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        WHERE tr.status = ANY(%s)
          AND COALESCE(tr.translation_text, '') <> ''
          AND p.name = 'legacy_scholarly'
          AND pv.version = 3
        """,
        (status_list,),
    )
    legacy_v3_stat = stat_from_row(cur.fetchone())

    return {
        "profile": profile_stats,
        "model_exact": model_exact_stats,
        "model": model_stats,
        "global": global_stat,
        "legacy_v3": legacy_v3_stat,
    }


def choose_token_stat(
    sample_stats: dict[str, object],
    *,
    profile_version_id: int | None,
    model: str | None,
    api_mode: str | None,
    reasoning_effort: str | None,
) -> tuple[dict[str, object] | None, str]:
    profile_stats = sample_stats.get("profile") or {}
    if profile_version_id is not None and profile_stats.get(int(profile_version_id), {}).get("avg_total"):
        return profile_stats[int(profile_version_id)], "same prompt version"

    model_key = ((model or "").strip(), (api_mode or "").strip(), (reasoning_effort or "").strip())
    model_exact_stats = sample_stats.get("model_exact") or {}
    if model_exact_stats.get(model_key, {}).get("avg_total"):
        return model_exact_stats[model_key], "same model/API/reasoning"

    model_stats = sample_stats.get("model") or {}
    if model_stats.get((model or "").strip(), {}).get("avg_total"):
        return model_stats[(model or "").strip()], "same model"

    legacy_v3_stat = sample_stats.get("legacy_v3")
    if legacy_v3_stat and legacy_v3_stat.get("avg_total"):
        return legacy_v3_stat, "legacy_scholarly v3 average"

    global_stat = sample_stats.get("global")
    if global_stat and global_stat.get("avg_total"):
        return global_stat, "all translation runs"

    return None, "no token sample"


def add_projection_estimates(row: dict[str, object], stat: dict[str, object] | None) -> None:
    remaining_runs = int(row.get("remaining_runs") or 0)
    if not stat or not stat.get("avg_total"):
        row.update(
            {
                "avg_input": None,
                "avg_output": None,
                "avg_reasoning": None,
                "avg_total": None,
                "sample_runs": 0,
                "expected_input_tokens": None,
                "expected_output_tokens": None,
                "expected_reasoning_tokens": None,
                "expected_total_tokens": None,
                "expected_cost": None,
            }
        )
        return

    avg_input = stat.get("avg_input")
    avg_output = stat.get("avg_output")
    avg_reasoning = stat.get("avg_reasoning")
    avg_total = stat.get("avg_total")
    expected_input = float(avg_input) * remaining_runs if avg_input is not None else None
    expected_output = float(avg_output) * remaining_runs if avg_output is not None else None
    expected_reasoning = float(avg_reasoning) * remaining_runs if avg_reasoning is not None else None
    expected_total = float(avg_total) * remaining_runs if avg_total is not None else None
    row.update(
        {
            "avg_input": avg_input,
            "avg_output": avg_output,
            "avg_reasoning": avg_reasoning,
            "avg_total": avg_total,
            "sample_runs": int(stat.get("runs") or 0),
            "expected_input_tokens": expected_input,
            "expected_output_tokens": expected_output,
            "expected_reasoning_tokens": expected_reasoning,
            "expected_total_tokens": expected_total,
            "expected_cost": estimate_cost(str(row.get("model") or ""), expected_input, expected_output),
        }
    )


def fetch_approved_human_projection(cur, sample_stats: dict[str, object]) -> list[dict[str, object]]:
    if not table_exists(cur, "human_translations"):
        return []
    approved_col = (
        "COALESCE(pv.approved_human_only, FALSE)"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only")
        else "FALSE"
    )
    model_col = (
        "COALESCE(NULLIF(pv.default_model, ''), 'gpt-5.5')"
        if column_exists(cur, "translation_prompt_profile_versions", "default_model")
        else "'gpt-5.5'"
    )
    api_col = (
        "COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions')"
        if column_exists(cur, "translation_prompt_profile_versions", "default_api_mode")
        else "'chat_completions'"
    )
    reasoning_col = (
        "COALESCE(NULLIF(pv.default_reasoning_effort, ''), '')"
        if column_exists(cur, "translation_prompt_profile_versions", "default_reasoning_effort")
        else "''"
    )
    requested_runs_col = (
        "GREATEST(COALESCE(pv.default_requested_runs, 1), 1)"
        if column_exists(cur, "translation_prompt_profile_versions", "default_requested_runs")
        else "1"
    )
    priority_col = (
        "GREATEST(COALESCE(pv.approved_human_queue_priority, 5), 0)"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_queue_priority")
        else "5"
    )
    approved_expr = approved_human_expr(cur)
    status_list = list(SUCCESSFUL_TRANSLATION_STATUSES)
    cur.execute(
        f"""
        WITH target_profiles AS (
            SELECT
                p.id AS profile_id,
                p.name AS profile_name,
                pv.id AS profile_version_id,
                pv.version AS profile_version,
                {approved_col} AS approved_human_only,
                {model_col} AS model,
                {api_col} AS api_mode,
                {reasoning_col} AS reasoning_effort,
                {requested_runs_col} AS requested_runs,
                {priority_col} AS priority
            FROM translation_prompt_profiles p
            JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
            WHERE ({approved_col} AND {priority_col} <= 4)
               OR (p.name = 'legacy_scholarly' AND pv.version IN (1, 2, 3))
        ),
        approved_sources AS (
            SELECT
                a.id AS lemma_id,
                stv.id AS source_text_version_id
            FROM assembled_lemmas a
            JOIN LATERAL (
                SELECT stv.id, stv.source_document
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = a.id
                  AND stv.source_document IN ({public_source_document_list_sql()})
                  AND stv.is_current = TRUE
                  AND COALESCE(stv.text_body, '') <> ''
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            WHERE {approved_expr}
              AND COALESCE(a.quarantined, FALSE) = FALSE
        ),
        completed AS (
            SELECT
                tr.lemma_id,
                tr.profile_id,
                tr.profile_version_id,
                tr.source_text_version_id,
                COUNT(*) AS completed_runs
            FROM translation_runs tr
            WHERE tr.status = ANY(%s)
              AND COALESCE(tr.translation_text, '') <> ''
            GROUP BY tr.lemma_id, tr.profile_id, tr.profile_version_id, tr.source_text_version_id
        ),
        open_requests AS (
            SELECT profile_version_id, COUNT(*) AS open_requests
            FROM translation_run_requests
            WHERE status IN ('pending', 'running')
            GROUP BY profile_version_id
        )
        SELECT
            tp.profile_id,
            tp.profile_name,
            tp.profile_version_id,
            tp.profile_version,
            tp.model,
            tp.api_mode,
            tp.reasoning_effort,
            tp.priority,
            COUNT(*) AS target_pairs,
            COUNT(*) FILTER (WHERE COALESCE(c.completed_runs, 0) >= tp.requested_runs) AS complete_pairs,
            COUNT(*) FILTER (WHERE COALESCE(c.completed_runs, 0) < tp.requested_runs) AS remaining_pairs,
            SUM(GREATEST(tp.requested_runs - COALESCE(c.completed_runs, 0), 0)) AS remaining_runs,
            COALESCE(MAX(oq.open_requests), 0) AS open_requests
        FROM target_profiles tp
        CROSS JOIN approved_sources s
        LEFT JOIN completed c
          ON c.lemma_id = s.lemma_id
         AND c.profile_id = tp.profile_id
         AND c.profile_version_id = tp.profile_version_id
         AND c.source_text_version_id = s.source_text_version_id
        LEFT JOIN open_requests oq ON oq.profile_version_id = tp.profile_version_id
        GROUP BY
            tp.profile_id, tp.profile_name, tp.profile_version_id, tp.profile_version,
            tp.model, tp.api_mode, tp.reasoning_effort, tp.priority
        ORDER BY tp.priority, tp.profile_name, tp.profile_version
        """,
        (status_list,),
    )
    keys = [
        "profile_id",
        "profile_name",
        "profile_version_id",
        "profile_version",
        "model",
        "api_mode",
        "reasoning_effort",
        "priority",
        "target_pairs",
        "complete_pairs",
        "remaining_pairs",
        "remaining_runs",
        "open_requests",
    ]
    rows = []
    for raw in cur.fetchall():
        row = dict(zip(keys, raw))
        stat, basis = choose_token_stat(
            sample_stats,
            profile_version_id=int(row["profile_version_id"]),
            model=str(row["model"]),
            api_mode=str(row["api_mode"]),
            reasoning_effort=str(row.get("reasoning_effort") or ""),
        )
        row["sample_basis"] = basis
        add_projection_estimates(row, stat)
        rows.append(row)
    return rows


def fetch_v3_whole_projection(cur, sample_stats: dict[str, object]) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT p.id, pv.id, COALESCE(NULLIF(pv.default_model, ''), 'gpt-5.5')
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.name = 'legacy_scholarly'
          AND pv.version = 3
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None
    profile_id, profile_version_id, model = int(row[0]), int(row[1]), row[2]
    status_list = list(SUCCESSFUL_TRANSLATION_STATUSES)
    cur.execute(
        f"""
        WITH preferred_sources AS (
            SELECT
                a.id AS lemma_id,
                stv.id AS source_text_version_id
            FROM assembled_lemmas a
            JOIN LATERAL (
                SELECT stv.id, stv.source_document
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = a.id
                  AND stv.source_document IN ({public_source_document_list_sql()})
                  AND stv.is_current = TRUE
                  AND COALESCE(stv.text_body, '') <> ''
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            WHERE COALESCE(a.quarantined, FALSE) = FALSE
        ),
        completed AS (
            SELECT DISTINCT tr.lemma_id, tr.source_text_version_id
            FROM translation_runs tr
            WHERE tr.profile_id = %s
              AND tr.profile_version_id = %s
              AND tr.status = ANY(%s)
              AND COALESCE(tr.translation_text, '') <> ''
        )
        SELECT
            COUNT(*) AS total_targets,
            COUNT(*) FILTER (WHERE c.lemma_id IS NOT NULL) AS completed_targets,
            COUNT(*) FILTER (WHERE c.lemma_id IS NULL) AS remaining_targets
        FROM preferred_sources ps
        LEFT JOIN completed c
          ON c.lemma_id = ps.lemma_id
         AND c.source_text_version_id = ps.source_text_version_id
        """,
        (profile_id, profile_version_id, status_list),
    )
    total_targets, completed_targets, remaining_targets = cur.fetchone()
    stat, basis = choose_token_stat(
        sample_stats,
        profile_version_id=profile_version_id,
        model=model,
        api_mode="chat_completions",
        reasoning_effort="",
    )
    projection = {
        "profile_id": profile_id,
        "profile_version_id": profile_version_id,
        "model": model,
        "total_targets": int(total_targets or 0),
        "completed_targets": int(completed_targets or 0),
        "remaining_targets": int(remaining_targets or 0),
        "remaining_runs": int(remaining_targets or 0),
        "sample_basis": basis,
    }
    add_projection_estimates(projection, stat)
    if stat and stat.get("avg_total"):
        projection["expected_whole_total_tokens"] = float(stat["avg_total"]) * int(total_targets or 0)
        projection["expected_whole_input_tokens"] = (
            float(stat["avg_input"]) * int(total_targets or 0) if stat.get("avg_input") is not None else None
        )
        projection["expected_whole_output_tokens"] = (
            float(stat["avg_output"]) * int(total_targets or 0) if stat.get("avg_output") is not None else None
        )
        projection["expected_whole_cost"] = estimate_cost(
            model,
            projection.get("expected_whole_input_tokens"),
            projection.get("expected_whole_output_tokens"),
        )
    else:
        projection["expected_whole_total_tokens"] = None
        projection["expected_whole_input_tokens"] = None
        projection["expected_whole_output_tokens"] = None
        projection["expected_whole_cost"] = None
    return projection


def token_totals_from_cost_rows(cost_rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "runs": sum(int(row.get("total_runs") or 0) for row in cost_rows),
        "priced_runs": sum(int(row.get("priced_runs") or 0) for row in cost_rows),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in cost_rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in cost_rows),
        "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in cost_rows),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in cost_rows),
        "estimated_cost": sum(float(row.get("estimated_cost") or 0) for row in cost_rows),
    }


def render_queue_summary(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{text_cell(row['queue_class'])}</td>"
            f"<td>{text_cell(row['status'])}</td>"
            f"<td>{int_cell(row['priority'])}</td>"
            f"<td>{text_cell(row['profile_name'])} v{text_cell(row['profile_version'])}</td>"
            f"<td>{text_cell(row['model'])}</td>"
            f"<td>{text_cell(row['api_mode'])}</td>"
            f"<td>{text_cell(row.get('reasoning_effort') or '-')}</td>"
            f"<td>{number_cell(row.get('temperature'), 2)}</td>"
            f"<td>{number_cell(row.get('top_p'), 2)}</td>"
            f"<td>{int_cell(row['request_count'])}</td>"
            f"<td>{text_cell(short_datetime(row['oldest_request']))}</td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="11">No pending or running translation requests.</td></tr>')
    return f"""
    <section>
      <h2>Scheduled Translation Queue</h2>
      <table>
        <thead>
          <tr>
            <th>Class</th><th>Status</th><th>Priority</th><th>Prompt</th><th>Model</th>
            <th>API</th><th>Reasoning</th><th>Temp</th><th>Top p</th><th>Requests</th><th>Oldest</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </section>
    """


def render_profile_controls(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{text_cell(row['profile_name'])}</td>"
            f"<td>{text_cell(row['profile_version'])}</td>"
            f"<td>{'yes' if row['active'] else 'no'}</td>"
            f"<td>{'yes' if row['approved_human_only'] else 'no'}</td>"
            f"<td>{text_cell(row.get('default_model') or '-')}</td>"
            f"<td>{text_cell(row.get('default_api_mode') or '-')}</td>"
            f"<td>{text_cell(row.get('default_reasoning_effort') or '-')}</td>"
            f"<td>{number_cell(row.get('default_temperature'), 2)}</td>"
            f"<td>{number_cell(row.get('default_top_p'), 2)}</td>"
            f"<td>{int_cell(row.get('default_requested_runs'))}</td>"
            f"<td>{int_cell(row.get('approved_human_queue_priority'))}</td>"
            f"<td>{int_cell(row.get('queued_requests'))}</td>"
            f"<td>{int_cell(row.get('completed_runs'))}</td>"
            f"<td>{number_cell(row.get('avg_tokens'), 0)}</td>"
            "</tr>"
        )
    return f"""
    <section>
      <h2>Prompt Version Controls</h2>
      <table>
        <thead>
          <tr>
            <th>Profile</th><th>v</th><th>Active</th><th>Approved only</th><th>Default model</th>
            <th>API</th><th>Reasoning</th><th>Temp</th><th>Top p</th><th>Runs</th>
            <th>Approved priority</th><th>Queued</th><th>Completed</th><th>Avg tokens</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </section>
    """


def render_token_totals(token_totals: dict[str, object]) -> str:
    return f"""
    <section>
      <h2>Recorded Token Usage Totals</h2>
      <div class="cards">
        <div class="metric"><span class="metric-label">Translation runs</span><span class="metric-value">{int_cell(token_totals.get('runs'))}</span></div>
        <div class="metric"><span class="metric-label">Total tokens</span><span class="metric-value">{int_cell(token_totals.get('total_tokens'))}</span></div>
        <div class="metric"><span class="metric-label">Input tokens</span><span class="metric-value">{int_cell(token_totals.get('input_tokens'))}</span></div>
        <div class="metric"><span class="metric-label">Output tokens</span><span class="metric-value">{int_cell(token_totals.get('output_tokens'))}</span></div>
        <div class="metric"><span class="metric-label">Reasoning tokens</span><span class="metric-value">{int_cell(token_totals.get('reasoning_tokens'))}</span></div>
        <div class="metric"><span class="metric-label">Estimated recorded cost</span><span class="metric-value">{money(token_totals.get('estimated_cost'))}</span></div>
      </div>
      <p class="note">Input/output token totals use rows where split usage is recorded. Total tokens use the historical translation_runs.tokens_used value, so it can cover older rows even when input/output split data is absent.</p>
    </section>
    """


def render_model_costs(rows: list[dict[str, object]], token_totals: dict[str, object]) -> str:
    body = []
    for row in rows:
        pricing = row.get("pricing")
        price_label = "-"
        if pricing:
            price_label = f"${pricing.input_per_million:g} / ${pricing.output_per_million:g}"
        body.append(
            "<tr>"
            f"<td>{text_cell(row['model'])}</td>"
            f"<td>{text_cell(row['api_mode'])}</td>"
            f"<td>{text_cell(row.get('reasoning_effort') or '-')}</td>"
            f"<td>{price_label}</td>"
            f"<td>{int_cell(row['total_runs'])}</td>"
            f"<td>{int_cell(row['priced_runs'])}</td>"
            f"<td>{int_cell(row['input_tokens'])}</td>"
            f"<td>{int_cell(row['output_tokens'])}</td>"
            f"<td>{int_cell(row['reasoning_tokens'])}</td>"
            f"<td>{percent_cell(row['total_tokens'], token_totals.get('total_tokens'))}</td>"
            f"<td>{number_cell(row['avg_tokens'], 0)}</td>"
            f"<td>{money(row['estimated_cost'])}</td>"
            f"<td>{money(row['avg_cost'])}</td>"
            f"<td>{text_cell(short_datetime(row['last_completed']))}</td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="14">No completed translation runs available.</td></tr>')
    return f"""
    <section>
      <h2>Model Cost Averages</h2>
      <p class="note">Prices are configured in model_pricing.py as of {escape(PRICING_AS_OF)}. Dollar estimates use rows with recorded input/output token splits; reasoning tokens are shown separately but already included in output-token billing.</p>
      <table>
        <thead>
          <tr>
            <th>Model</th><th>API</th><th>Reasoning</th><th>Input / output $ per 1M</th>
            <th>Runs</th><th>Priced runs</th><th>Input tokens</th><th>Output tokens</th>
            <th>Reasoning tokens</th><th>Token share</th><th>Avg tokens</th><th>Total est.</th><th>Avg est.</th><th>Last run</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </section>
    """


def render_approved_human_projection(rows: list[dict[str, object]]) -> str:
    expected_total = sum(float(row.get("expected_total_tokens") or 0) for row in rows)
    expected_input = sum(float(row.get("expected_input_tokens") or 0) for row in rows)
    expected_output = sum(float(row.get("expected_output_tokens") or 0) for row in rows)
    expected_cost = sum(float(row.get("expected_cost") or 0) for row in rows)
    remaining_runs = sum(int(row.get("remaining_runs") or 0) for row in rows)
    remaining_pairs = sum(int(row.get("remaining_pairs") or 0) for row in rows)
    missing_cost_rows = sum(1 for row in rows if int(row.get("remaining_runs") or 0) > 0 and row.get("expected_cost") is None)

    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{text_cell(row['profile_name'])} v{text_cell(row['profile_version'])}</td>"
            f"<td>{text_cell(row['model'])}</td>"
            f"<td>{text_cell(row['api_mode'])}</td>"
            f"<td>{text_cell(row.get('reasoning_effort') or '-')}</td>"
            f"<td>{int_cell(row.get('priority'))}</td>"
            f"<td>{int_cell(row.get('target_pairs'))}</td>"
            f"<td>{int_cell(row.get('complete_pairs'))}</td>"
            f"<td>{int_cell(row.get('remaining_pairs'))}</td>"
            f"<td>{int_cell(row.get('remaining_runs'))}</td>"
            f"<td>{int_cell(row.get('open_requests'))}</td>"
            f"<td>{token_cell(row.get('avg_total'))}</td>"
            f"<td>{token_cell(row.get('expected_input_tokens'))}</td>"
            f"<td>{token_cell(row.get('expected_output_tokens'))}</td>"
            f"<td>{token_cell(row.get('expected_reasoning_tokens'))}</td>"
            f"<td>{token_cell(row.get('expected_total_tokens'))}</td>"
            f"<td>{money(row.get('expected_cost'))}</td>"
            f"<td>{text_cell(row.get('sample_basis'))} ({int_cell(row.get('sample_runs'))})</td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="17">No approved-human priority projection rows available.</td></tr>')

    note = ""
    if missing_cost_rows:
        note = f" {missing_cost_rows} row(s) have token estimates but no dollar estimate because no configured pricing or split-token sample was available."
    return f"""
    <section>
      <h2>Approved-Human Priority Completion Estimate</h2>
      <div class="cards">
        <div class="metric"><span class="metric-label">Remaining target pairs</span><span class="metric-value">{remaining_pairs:,}</span></div>
        <div class="metric"><span class="metric-label">Remaining runs</span><span class="metric-value">{remaining_runs:,}</span></div>
        <div class="metric"><span class="metric-label">Expected total tokens</span><span class="metric-value">{token_cell(expected_total)}</span></div>
        <div class="metric"><span class="metric-label">Expected input tokens</span><span class="metric-value">{token_cell(expected_input)}</span></div>
        <div class="metric"><span class="metric-label">Expected output tokens</span><span class="metric-value">{token_cell(expected_output)}</span></div>
        <div class="metric"><span class="metric-label">Expected cost</span><span class="metric-value">{money(expected_cost)}</span></div>
      </div>
      <p class="note">This estimates the work to complete approved-human evaluation targets for the baseline legacy_scholarly v1/v2/v3 set plus approved-human-only prompt versions with queue priority 4 or better. Estimates use same-prompt averages when available, then same model/API/reasoning, same model, legacy_scholarly v3, or all translation runs as a fallback.{escape(note)}</p>
      <table>
        <thead>
          <tr>
            <th>Prompt</th><th>Model</th><th>API</th><th>Reasoning</th><th>Priority</th>
            <th>Targets</th><th>Complete</th><th>Remaining pairs</th><th>Remaining runs</th><th>Open</th>
            <th>Avg tokens</th><th>Exp. input</th><th>Exp. output</th><th>Exp. reasoning</th><th>Exp. total</th><th>Exp. cost</th><th>Sample basis</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </section>
    """


def render_v3_whole_projection(projection: dict[str, object] | None) -> str:
    if not projection:
        return """
        <section>
          <h2>Whole-Stephanos v3 Estimate</h2>
          <p class="note">legacy_scholarly v3 was not found, so no projection could be generated.</p>
        </section>
        """
    return f"""
    <section>
      <h2>Whole-Stephanos v3 Estimate</h2>
      <div class="cards">
        <div class="metric"><span class="metric-label">Preferred-source targets</span><span class="metric-value">{int_cell(projection.get('total_targets'))}</span></div>
        <div class="metric"><span class="metric-label">Already completed</span><span class="metric-value">{int_cell(projection.get('completed_targets'))}</span></div>
        <div class="metric"><span class="metric-label">Remaining</span><span class="metric-value">{int_cell(projection.get('remaining_targets'))}</span></div>
        <div class="metric"><span class="metric-label">Avg tokens/run</span><span class="metric-value">{token_cell(projection.get('avg_total'))}</span></div>
        <div class="metric"><span class="metric-label">Whole-corpus tokens</span><span class="metric-value">{token_cell(projection.get('expected_whole_total_tokens'))}</span></div>
        <div class="metric"><span class="metric-label">Whole-corpus cost</span><span class="metric-value">{money(projection.get('expected_whole_cost'))}</span></div>
      </div>
      <p class="note">This uses current preferred public Greek source text for every non-quarantined lemma. Cost uses the configured price for {text_cell(projection.get('model'))}; the sample basis is {text_cell(projection.get('sample_basis'))} ({int_cell(projection.get('sample_runs'))} runs).</p>
      <table>
        <thead>
          <tr>
            <th>Scope</th><th>Targets</th><th>Input tokens</th><th>Output tokens</th><th>Total tokens</th><th>Estimated cost</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>All preferred-source targets</td>
            <td>{int_cell(projection.get('total_targets'))}</td>
            <td>{token_cell(projection.get('expected_whole_input_tokens'))}</td>
            <td>{token_cell(projection.get('expected_whole_output_tokens'))}</td>
            <td>{token_cell(projection.get('expected_whole_total_tokens'))}</td>
            <td>{money(projection.get('expected_whole_cost'))}</td>
          </tr>
          <tr>
            <td>Remaining preferred-source targets</td>
            <td>{int_cell(projection.get('remaining_targets'))}</td>
            <td>{token_cell(projection.get('expected_input_tokens'))}</td>
            <td>{token_cell(projection.get('expected_output_tokens'))}</td>
            <td>{token_cell(projection.get('expected_total_tokens'))}</td>
            <td>{money(projection.get('expected_cost'))}</td>
          </tr>
        </tbody>
      </table>
    </section>
    """


def render_pricing_reference() -> str:
    rows = []
    for pricing in MODEL_PRICING.values():
        rows.append(
            "<tr>"
            f"<td>{escape(pricing.model)}</td>"
            f"<td>${pricing.input_per_million:g}</td>"
            f"<td>${pricing.output_per_million:g}</td>"
            f'<td><a href="{escape(pricing.source_url, quote=True)}">OpenAI pricing</a></td>'
            "</tr>"
        )
    return f"""
    <section>
      <h2>Configured Pricing</h2>
      <table>
        <thead><tr><th>Model</th><th>Input $/1M</th><th>Output $/1M</th><th>Source</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """


def render_page(queue_rows, profile_rows, cost_rows, approved_projection_rows, v3_projection) -> str:
    approved_pending = sum(int(row["request_count"] or 0) for row in queue_rows if row["queue_class"] == "approved-human")
    other_pending = sum(int(row["request_count"] or 0) for row in queue_rows if row["queue_class"] != "approved-human")
    response_pending = sum(int(row["request_count"] or 0) for row in queue_rows if row["api_mode"] == "responses")
    token_totals = token_totals_from_cost_rows(cost_rows)
    approved_expected_tokens = sum(float(row.get("expected_total_tokens") or 0) for row in approved_projection_rows)
    approved_expected_cost = sum(float(row.get("expected_cost") or 0) for row in approved_projection_rows)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Translation Operations & Cost</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      background: #f6f8fb;
      color: #1f2937;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 24px;
    }}
    main {{
      margin: 0 auto;
      max-width: 1500px;
    }}
    {site_navigation_styles()}
    h1 {{
      color: #10223f;
      font-size: 2rem;
      margin: 0 0 6px;
    }}
    h2 {{
      color: #17365f;
      font-size: 1.35rem;
      margin: 30px 0 12px;
    }}
    .lede, .note {{
      color: #536173;
      line-height: 1.5;
      margin: 0 0 16px;
    }}
    .cards {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      margin: 20px 0;
    }}
    .metric {{
      background: #fff;
      border: 1px solid #d8e0ec;
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .metric-label {{
      color: #617188;
      display: block;
      font-size: 0.82rem;
      font-weight: 650;
      text-transform: uppercase;
    }}
    .metric-value {{
      color: #10223f;
      display: block;
      font-size: 1.65rem;
      font-weight: 720;
      margin-top: 4px;
    }}
    table {{
      background: #fff;
      border-collapse: collapse;
      border: 1px solid #d8e0ec;
      box-shadow: 0 1px 3px rgba(16, 34, 63, 0.05);
      font-size: 0.9rem;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e4eaf3;
      padding: 8px 9px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #edf3fb;
      color: #26364d;
      font-weight: 700;
      white-space: nowrap;
    }}
    tr:nth-child(even) td {{
      background: #fafcff;
    }}
    a {{
      color: #0d47a1;
    }}
    @media (max-width: 900px) {{
      body {{
        padding: 14px;
      }}
      table {{
        display: block;
        overflow-x: auto;
        white-space: nowrap;
      }}
    }}
  </style>
</head>
<body>
<main>
  {render_site_navigation("operations", "translation_operations", depth=1)}
  {render_site_breadcrumbs([("Statistics", "statistics.html"), ("Translation Operations", None)], depth=1)}
  <h1>Translation Operations & Cost</h1>
  <p class="lede">Queue state, prompt-version controls, and estimated model cost for translation jobs. Generated {escape(generated_at)}.</p>
  <div class="cards">
    <div class="metric"><span class="metric-label">Approved-human queued</span><span class="metric-value">{approved_pending:,}</span></div>
    <div class="metric"><span class="metric-label">Other queued</span><span class="metric-value">{other_pending:,}</span></div>
    <div class="metric"><span class="metric-label">Responses queued</span><span class="metric-value">{response_pending:,}</span></div>
    <div class="metric"><span class="metric-label">All-model tokens used</span><span class="metric-value">{int_cell(token_totals.get('total_tokens'))}</span></div>
    <div class="metric"><span class="metric-label">Approved-human tokens left</span><span class="metric-value">{token_cell(approved_expected_tokens)}</span></div>
    <div class="metric"><span class="metric-label">Approved-human cost left</span><span class="metric-value">{money(approved_expected_cost)}</span></div>
    <div class="metric"><span class="metric-label">Priced model groups</span><span class="metric-value">{sum(1 for row in cost_rows if row.get("pricing")):,}</span></div>
  </div>
  {render_queue_summary(queue_rows)}
  {render_token_totals(token_totals)}
  {render_approved_human_projection(approved_projection_rows)}
  {render_v3_whole_projection(v3_projection)}
  {render_profile_controls(profile_rows)}
  {render_model_costs(cost_rows, token_totals)}
  {render_pricing_reference()}
</main>
</body>
</html>
"""


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    queue_rows = fetch_queue_summary(cur)
    profile_rows = fetch_profile_controls(cur)
    cost_rows = fetch_model_costs(cur)
    sample_stats = fetch_token_sample_stats(cur)
    approved_projection_rows = fetch_approved_human_projection(cur, sample_stats)
    v3_projection = fetch_v3_whole_projection(cur, sample_stats)
    conn.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        render_page(queue_rows, profile_rows, cost_rows, approved_projection_rows, v3_projection),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
