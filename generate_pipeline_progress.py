#!/usr/bin/env python3
"""
Generate pipeline progress monitoring page.

This script collects statistics from all pipeline stages and estimates
completion times based on processing rates.

Usage:
  uv run generate_pipeline_progress.py
"""
import json
import html as html_module
from datetime import datetime, timedelta
from pathlib import Path

import db
from generate_spelling_variants import generate_variants
from translation_guidance_coverage import (
    CURRENT_DETECTOR_VERSION,
    PROMPT_GUIDANCE_KINDS,
    required_guidance_rules_sql,
)

NIGHTLY_GUIDANCE_CHECK_LIMIT = 2000
BILLERBECK_GERMAN_OCR_NIGHTLY_LIMIT = 3
BILLERBECK_GERMAN_TRANSLATE_NIGHTLY_LIMIT = 5


def pg_table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def pg_column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
        )
        """,
        (table_name, column_name),
    )
    return bool(cur.fetchone()[0])


def get_progress_stats(conn) -> dict:
    """Collect progress statistics from all pipeline stages."""
    cur = conn.cursor()
    stats = {}

    # 1. Translation
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN COALESCE(translation, '') != '' THEN 1 END) as translated,
            COUNT(CASE WHEN reviewed_english_translation IS NOT NULL THEN 1 END) as human_reviewed,
            COUNT(CASE WHEN corrected_english_translation IS NOT NULL THEN 1 END) as human_edited
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL
    """)
    row = cur.fetchone()
    total_with_billerbeck = row[0]
    translated_total = row[1]
    stats["translation_ai"] = {
        "name": "AI Translation",
        "total": total_with_billerbeck,
        "completed": translated_total,
        "pending": total_with_billerbeck - translated_total,
        "unit": "entries",
    }
    human_reviewed_total = row[2] + row[3]
    stats["translation_human"] = {
        "name": "Human Review",
        "total": translated_total,
        "completed": min(human_reviewed_total, translated_total),  # reviewed or edited
        "pending": max(translated_total - human_reviewed_total, 0),
        "unit": "entries",
    }

    # Translation rate (last 7 days)
    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL
          AND translated_at > NOW() - INTERVAL '7 days'
    """)
    stats["translation_ai"]["rate_7d"] = cur.fetchone()[0]

    if pg_table_exists(cur, "images") and pg_column_exists(cur, "images", "source_document"):
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE processed = 1) AS completed,
                COUNT(*) FILTER (WHERE processed = 0) AS pending
            FROM images
            WHERE COALESCE(source_document, 'billerbeck') = 'meineke'
        """)
        row = cur.fetchone()
        cur.execute("""
            SELECT COUNT(*)
            FROM images
            WHERE COALESCE(source_document, 'billerbeck') = 'meineke'
              AND processed = 1
              AND processed_at > NOW() - INTERVAL '7 days'
        """)
        stats["meineke_page_ocr"] = {
            "name": "Meineke Page OCR",
            "total": row[0],
            "completed": row[1],
            "pending": row[2],
            "unit": "pages",
            "rate_7d": cur.fetchone()[0],
            "detail": "Queued missing-page OCR for the public Meineke source text",
        }

    # Human review rate (last 7 days)
    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL
          AND reviewed_at > NOW() - INTERVAL '7 days'
          AND (
            reviewed_english_translation IS NOT NULL
            OR corrected_english_translation IS NOT NULL
          )
    """)
    stats["translation_human"]["rate_7d"] = cur.fetchone()[0]

    # 2. Proper noun extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN proper_nouns_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE translated = 1
          AND greek_text IS NOT NULL
          AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["proper_nouns"] = {
        "name": "Proper Noun Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE translated = 1
          AND proper_nouns_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["proper_nouns"]["rate_7d"] = cur.fetchone()[0]

    # 3. Structured source-citation extraction
    cur.execute("""
        SELECT COUNT(DISTINCT lemma_id)
        FROM effective_proper_nouns
        WHERE role = 'source'
    """)
    source_lemma_total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT lemma_id)
        FROM lemma_source_citation_mentions
    """)
    source_lemma_completed = cur.fetchone()[0]

    stats["source_citations"] = {
        "name": "Structured Source Citations",
        "total": source_lemma_total,
        "completed": min(source_lemma_completed, source_lemma_total),
        "pending": max(source_lemma_total - source_lemma_completed, 0),
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(DISTINCT lemma_id)
        FROM lemma_source_citation_mentions
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    stats["source_citations"]["rate_7d"] = cur.fetchone()[0]

    # 4. Wikidata linking - sources
    cur.execute("""
        WITH grouped AS (
            SELECT
                lemma_form,
                english_translation,
                MAX(wikidata_qid) AS wikidata_qid,
                MAX(wikidata_confidence) AS wikidata_confidence,
                MAX(COALESCE(human_resolution_status, '')) AS human_resolution_status
            FROM proper_nouns
            WHERE role = 'source'
            GROUP BY lemma_form, english_translation
        )
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE wikidata_qid IS NOT NULL
                   OR wikidata_confidence IS NOT NULL
                   OR human_resolution_status IN ('approved', 'corrected', 'not_alignable', 'added')
            ) AS processed
        FROM grouped
    """)
    row = cur.fetchone()
    stats["wikidata_sources"] = {
        "name": "Wikidata Sources",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "sources",
    }

    cur.execute("""
        WITH grouped AS (
            SELECT
                lemma_form,
                english_translation,
                MAX(COALESCE(human_resolved_at, wikidata_linked_at)) AS resolved_at,
                MAX(wikidata_qid) AS wikidata_qid,
                MAX(wikidata_confidence) AS wikidata_confidence,
                MAX(COALESCE(human_resolution_status, '')) AS human_resolution_status
            FROM proper_nouns
            WHERE role = 'source'
            GROUP BY lemma_form, english_translation
        )
        SELECT COUNT(*)
        FROM grouped
        WHERE resolved_at > NOW() - INTERVAL '7 days'
          AND (
              wikidata_qid IS NOT NULL
              OR wikidata_confidence IS NOT NULL
              OR human_resolution_status IN ('approved', 'corrected', 'not_alignable', 'added')
          )
    """)
    stats["wikidata_sources"]["rate_7d"] = cur.fetchone()[0]

    # 5. Etymology extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN etymologies_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE translated = 1
          AND greek_text IS NOT NULL
          AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["etymologies"] = {
        "name": "Etymology Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE translated = 1
          AND etymologies_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["etymologies"]["rate_7d"] = cur.fetchone()[0]

    # 6. Alias extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN aliases_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE proper_nouns_analyzed = TRUE
          AND greek_text IS NOT NULL
          AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["aliases"] = {
        "name": "Alias Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE proper_nouns_analyzed = TRUE
          AND aliases_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["aliases"]["rate_7d"] = cur.fetchone()[0]

    # 7. Spelling variant generation
    cur.execute("""
        SELECT DISTINCT id, english_translation
        FROM effective_proper_nouns
        WHERE COALESCE(english_translation, '') != ''
        ORDER BY id
    """)
    spelling_variant_ids = [
        proper_noun_id
        for proper_noun_id, english_name in cur.fetchall()
        if generate_variants(english_name)
    ]
    spelling_total = len(spelling_variant_ids)

    if spelling_variant_ids:
        cur.execute("""
            SELECT COUNT(DISTINCT proper_noun_id)
            FROM proper_noun_aliases
            WHERE alias_type = 'spelling_variant'
              AND proper_noun_id = ANY(%s)
        """, (spelling_variant_ids,))
        spelling_completed = cur.fetchone()[0]
    else:
        spelling_completed = 0

    stats["spelling_variants"] = {
        "name": "Spelling Variants",
        "total": spelling_total,
        "completed": min(spelling_completed, spelling_total),
        "pending": max(spelling_total - spelling_completed, 0),
        "unit": "entities",
    }

    if spelling_variant_ids:
        cur.execute("""
            SELECT COUNT(DISTINCT proper_noun_id)
            FROM proper_noun_aliases
            WHERE alias_type = 'spelling_variant'
              AND created_at > NOW() - INTERVAL '7 days'
              AND proper_noun_id = ANY(%s)
        """, (spelling_variant_ids,))
        stats["spelling_variants"]["rate_7d"] = cur.fetchone()[0]
    else:
        stats["spelling_variants"]["rate_7d"] = 0

    # 8. Human review of named-entity resolutions
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN human_resolution_status IS NOT NULL THEN 1 END) as reviewed
        FROM proper_nouns
    """)
    row = cur.fetchone()
    stats["entity_resolution_human"] = {
        "name": "Human Entity Review",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "mentions",
    }

    cur.execute("""
        SELECT COUNT(*) FROM proper_nouns
        WHERE human_resolved_at > NOW() - INTERVAL '7 days'
    """)
    stats["entity_resolution_human"]["rate_7d"] = cur.fetchone()[0]

    # 9. Wikidata linking - places
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(
                CASE
                    WHEN wikidata_place_qid IS NOT NULL
                      OR wikidata_place_confidence IS NOT NULL
                      OR wikidata_place_linked_at IS NOT NULL
                    THEN 1
                END
            ) as processed
        FROM assembled_lemmas
        WHERE type IN ('place', 'city', 'region', 'island', 'country', 'village',
                       'mountain', 'river', 'lake', 'spring', 'promontory', 'fortress')
    """)
    row = cur.fetchone()
    stats["wikidata_places"] = {
        "name": "Wikidata Places",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "places",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE wikidata_place_linked_at > NOW() - INTERVAL '7 days'
    """)
    stats["wikidata_places"]["rate_7d"] = cur.fetchone()[0]

    # 10. Meineke difference analysis
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN analyzed_at IS NOT NULL THEN 1 END) as analyzed
        FROM meineke_text_differences
        WHERE normalized_class = 'different'
    """)
    row = cur.fetchone()
    stats["meineke_differences"] = {
        "name": "Meineke Difference Analysis",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "pairs",
    }

    cur.execute("""
        SELECT COUNT(*) FROM meineke_text_differences
        WHERE normalized_class = 'different'
          AND analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["meineke_differences"]["rate_7d"] = cur.fetchone()[0]

    # 11. Text-pair sync
    cur.execute("""
        WITH current_pairs AS (
            SELECT b.id AS billerbeck_text_version_id, m.id AS meineke_text_version_id
            FROM assembled_lemmas a
            JOIN lemma_source_text_versions b
              ON b.lemma_id = a.id
             AND b.source_document = 'billerbeck'
             AND b.is_current = TRUE
            JOIN lemma_source_text_versions m
              ON m.lemma_id = a.id
             AND m.source_document = 'meineke'
             AND m.is_current = TRUE
        )
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM text_pair_differences t
                    WHERE t.billerbeck_text_version_id = current_pairs.billerbeck_text_version_id
                      AND t.meineke_text_version_id = current_pairs.meineke_text_version_id
                )
            ) AS synced
        FROM current_pairs
    """)
    row = cur.fetchone()
    stats["text_pair_sync"] = {
        "name": "Text Pair Sync",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "pairs",
    }

    cur.execute("""
        WITH current_pairs AS (
            SELECT b.id AS billerbeck_text_version_id, m.id AS meineke_text_version_id
            FROM assembled_lemmas a
            JOIN lemma_source_text_versions b
              ON b.lemma_id = a.id
             AND b.source_document = 'billerbeck'
             AND b.is_current = TRUE
            JOIN lemma_source_text_versions m
              ON m.lemma_id = a.id
             AND m.source_document = 'meineke'
             AND m.is_current = TRUE
        )
        SELECT COUNT(*)
        FROM current_pairs
        JOIN text_pair_differences t
          ON t.billerbeck_text_version_id = current_pairs.billerbeck_text_version_id
         AND t.meineke_text_version_id = current_pairs.meineke_text_version_id
        WHERE t.updated_at > NOW() - INTERVAL '7 days'
    """)
    stats["text_pair_sync"]["rate_7d"] = cur.fetchone()[0]

    # 12. Translation risk sync
    cur.execute("""
        SELECT COUNT(DISTINCT lemma_id)
        FROM translation_risk_flags
        WHERE risk_code = 'billerbeck_likely_translation_change'
          AND variant_kind = 'legacy_assembled'
          AND variant_id = 'translation'
    """)
    translation_risk_completed = cur.fetchone()[0]
    stats["translation_risk"] = {
        "name": "Translation Risk Sync",
        "total": translated_total,
        "completed": min(translation_risk_completed, translated_total),
        "pending": max(translated_total - translation_risk_completed, 0),
        "unit": "entries",
    }

    cur.execute("""
        SELECT COUNT(DISTINCT lemma_id)
        FROM translation_risk_flags
        WHERE risk_code = 'billerbeck_likely_translation_change'
          AND variant_kind = 'legacy_assembled'
          AND variant_id = 'translation'
          AND updated_at > NOW() - INTERVAL '7 days'
    """)
    stats["translation_risk"]["rate_7d"] = cur.fetchone()[0]

    # 13. Translation-guidance scan coverage
    if all(
        pg_table_exists(cur, table_name)
        for table_name in (
            "translation_guidance_rules",
            "translation_guidance_rule_revisions",
            "translation_guidance_matches",
            "translation_guidance_scan_queue",
            "lemma_source_text_versions",
        )
    ):
        required_rules_cte = required_guidance_rules_sql()
        cur.execute(
            f"""
            WITH required_rules AS (
                {required_rules_cte}
            ),
            current_sources AS (
                SELECT stv.id AS source_text_version_id
                FROM assembled_lemmas a
                JOIN lemma_source_text_versions stv
                  ON stv.lemma_id = a.id
                 AND stv.source_document = 'meineke'
                 AND stv.is_current = TRUE
                WHERE COALESCE(stv.text_body, '') <> ''
                  AND COALESCE(a.quarantined, FALSE) = FALSE
            ),
            matched_checks AS (
                SELECT DISTINCT
                    m.source_text_version_id,
                    m.rule_revision_id
                FROM translation_guidance_matches m
                JOIN current_sources cs
                  ON cs.source_text_version_id = m.source_text_version_id
                JOIN required_rules rr
                  ON rr.revision_id = m.rule_revision_id
                WHERE m.detector_version = %s
            ),
            recent_checks AS (
                SELECT DISTINCT
                    m.source_text_version_id,
                    m.rule_revision_id
                FROM translation_guidance_matches m
                JOIN current_sources cs
                  ON cs.source_text_version_id = m.source_text_version_id
                JOIN required_rules rr
                  ON rr.revision_id = m.rule_revision_id
                WHERE m.detector_version = %s
                  AND m.updated_at > NOW() - INTERVAL '7 days'
            ),
            queue_counts AS (
                SELECT
                    COUNT(*) FILTER (WHERE q.status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE q.status = 'running') AS running,
                    COUNT(*) FILTER (WHERE q.status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE q.status = 'failed') AS failed,
                    COUNT(*) FILTER (WHERE q.status = 'cancelled') AS cancelled,
                    COALESCE(SUM(q.tokens_used), 0) AS total_tokens,
                    COALESCE(SUM(q.tokens_used) FILTER (
                        WHERE q.finished_at > NOW() - INTERVAL '7 days'
                    ), 0) AS recent_tokens
                FROM translation_guidance_scan_queue q
                JOIN current_sources cs
                  ON cs.source_text_version_id = q.source_text_version_id
                JOIN required_rules rr
                  ON rr.revision_id = q.rule_revision_id
            )
            SELECT
                (SELECT COUNT(*) FROM current_sources) AS headword_count,
                (SELECT COUNT(*) FROM required_rules) AS rule_count,
                (SELECT COUNT(*) FROM matched_checks) AS completed_checks,
                (SELECT COUNT(*) FROM recent_checks) AS recent_checks,
                COALESCE(qc.pending, 0) AS queued_pending,
                COALESCE(qc.running, 0) AS queued_running,
                COALESCE(qc.completed, 0) AS queued_completed,
                COALESCE(qc.failed, 0) AS queued_failed,
                COALESCE(qc.cancelled, 0) AS queued_cancelled,
                COALESCE(qc.total_tokens, 0) AS total_tokens,
                COALESCE(qc.recent_tokens, 0) AS recent_tokens
            FROM queue_counts qc
            """,
            (
                list(PROMPT_GUIDANCE_KINDS),
                CURRENT_DETECTOR_VERSION,
                CURRENT_DETECTOR_VERSION,
            ),
        )
        row = cur.fetchone()
        guidance_headword_total = int(row[0] or 0)
        guidance_rule_total = int(row[1] or 0)
        guidance_potential_total = guidance_headword_total * guidance_rule_total
        guidance_checked_total = int(row[2] or 0)
        guidance_checked_rate = int(row[3] or 0)
        queue_pending = int(row[4] or 0)
        queue_running = int(row[5] or 0)
        queue_completed = int(row[6] or 0)
        queue_failed = int(row[7] or 0)
        queue_cancelled = int(row[8] or 0)
        total_tokens = int(row[9] or 0)
        recent_tokens = int(row[10] or 0)
        queue_detail = (
            f"; queue pending/running/completed/failed/cancelled: "
            f"{queue_pending:,}/{queue_running:,}/{queue_completed:,}/{queue_failed:,}/{queue_cancelled:,}"
        )
        guidance_token_detail = (
            f"; {total_tokens:,} guidance AI tokens recorded, {recent_tokens:,} in the last 7 days"
        )
        kind_detail = ", ".join(PROMPT_GUIDANCE_KINDS)

        stats["translation_guidance_checks"] = {
            "name": "Prompt Guidance Checks",
            "total": guidance_potential_total,
            "completed": min(guidance_checked_total, guidance_potential_total),
            "pending": max(guidance_potential_total - guidance_checked_total, 0),
            "unit": "rule/headword checks",
            "rate_7d": guidance_checked_rate,
            "planned_rate_per_day": NIGHTLY_GUIDANCE_CHECK_LIMIT,
            "detail": (
                f"{guidance_headword_total:,} current Meineke headwords x "
                f"{guidance_rule_total:,} prompt guidance rules "
                f"({kind_detail}; {CURRENT_DETECTOR_VERSION})"
                f"; default nightly limit {NIGHTLY_GUIDANCE_CHECK_LIMIT:,} checks"
                f"{queue_detail}{guidance_token_detail}"
            ),
        }

    # 14. Billerbeck German reference lane, kept internal and low priority
    if pg_table_exists(cur, "images") and pg_table_exists(cur, "billerbeck_german_pages"):
        cur.execute("""
            WITH pending_candidates AS (
                SELECT i.id
                FROM images i
                LEFT JOIN billerbeck_german_pages bgp ON bgp.image_id = i.id
                WHERE bgp.image_id IS NULL
                  AND COALESCE(i.source_document, 'billerbeck') IN ('billerbeck', 'billerbeck_german')
                  AND (
                        COALESCE(i.source_document, 'billerbeck') = 'billerbeck_german'
                        OR (
                            i.lemma_json IS NOT NULL
                            AND i.lemma_json::text LIKE '%%"status": "non_greek_error"%%'
                        )
                        OR i.page_number IS NOT NULL
                  )
            ),
            processed_pages AS (
                SELECT *
                FROM billerbeck_german_pages
            )
            SELECT
                (SELECT COUNT(*) FROM pending_candidates) AS pending,
                COUNT(*) AS processed,
                COUNT(*) FILTER (WHERE processed_at > NOW() - INTERVAL '7 days') AS processed_7d,
                COUNT(*) FILTER (WHERE status = 'entries_present') AS entries_present,
                COUNT(*) FILTER (WHERE status = 'no_headword_entries') AS no_headword_entries,
                COUNT(*) FILTER (WHERE status = 'not_german') AS not_german,
                COUNT(*) FILTER (
                    WHERE status NOT IN ('entries_present', 'no_headword_entries', 'not_german')
                ) AS other_status,
                COALESCE(SUM(ocr_tokens), 0) AS total_tokens
            FROM processed_pages
        """)
        row = cur.fetchone()
        german_pending = int(row[0] or 0)
        german_processed = int(row[1] or 0)
        german_rate = int(row[2] or 0)
        entries_present = int(row[3] or 0)
        no_headword_entries = int(row[4] or 0)
        not_german = int(row[5] or 0)
        other_status = int(row[6] or 0)
        german_tokens = int(row[7] or 0)
        stats["billerbeck_german_page_ocr"] = {
            "name": "Billerbeck German Page OCR",
            "total": german_pending + german_processed,
            "completed": german_processed,
            "pending": german_pending,
            "unit": "candidate pages",
            "rate_7d": german_rate,
            "planned_rate_per_day": BILLERBECK_GERMAN_OCR_NIGHTLY_LIMIT,
            "detail": (
                "Internal reference lane only; statuses entries/no-headword/not-German/other: "
                f"{entries_present:,}/{no_headword_entries:,}/{not_german:,}/{other_status:,}; "
                f"default nightly limit {BILLERBECK_GERMAN_OCR_NIGHTLY_LIMIT:,} pages; "
                f"{german_tokens:,} OCR tokens recorded"
            ),
        }

    if pg_table_exists(cur, "lemma_billerbeck_german_refs"):
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE COALESCE(german_text, '') <> '') AS total,
                COUNT(*) FILTER (
                    WHERE COALESCE(german_text, '') <> ''
                      AND translation_status = 'completed'
                      AND COALESCE(english_translation, '') <> ''
                ) AS completed,
                COUNT(*) FILTER (
                    WHERE COALESCE(german_text, '') <> ''
                      AND translation_status = 'failed'
                ) AS failed,
                COUNT(*) FILTER (
                    WHERE COALESCE(german_text, '') <> ''
                      AND translated_at > NOW() - INTERVAL '7 days'
                ) AS translated_7d,
                COALESCE(SUM(translation_tokens), 0) AS total_tokens,
                COALESCE(SUM(translation_tokens) FILTER (
                    WHERE translated_at > NOW() - INTERVAL '7 days'
                ), 0) AS recent_tokens
            FROM lemma_billerbeck_german_refs
        """)
        row = cur.fetchone()
        german_translation_total = int(row[0] or 0)
        german_translation_completed = int(row[1] or 0)
        german_translation_failed = int(row[2] or 0)
        german_translation_rate = int(row[3] or 0)
        german_translation_tokens = int(row[4] or 0)
        german_translation_recent_tokens = int(row[5] or 0)
        stats["billerbeck_german_translation"] = {
            "name": "Billerbeck German Translation",
            "total": german_translation_total,
            "completed": german_translation_completed,
            "pending": max(german_translation_total - german_translation_completed, 0),
            "unit": "reference rows",
            "rate_7d": german_translation_rate,
            "planned_rate_per_day": BILLERBECK_GERMAN_TRANSLATE_NIGHTLY_LIMIT,
            "detail": (
                "Internal reference lane only; not public and not part of the main translation queue; "
                f"failed: {german_translation_failed:,}; "
                f"default nightly limit {BILLERBECK_GERMAN_TRANSLATE_NIGHTLY_LIMIT:,} refs; "
                f"{german_translation_tokens:,} tokens recorded, {german_translation_recent_tokens:,} in the last 7 days"
            ),
        }

    if pg_table_exists(cur, "meineke_word_lemma_documents"):
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('completed', 'skipped')) AS completed,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'processing') AS processing,
                COUNT(*) FILTER (WHERE status = 'error') AS error,
                COUNT(*) FILTER (
                    WHERE status IN ('completed', 'skipped')
                      AND processed_at > NOW() - INTERVAL '7 days'
                ) AS completed_7d,
                COALESCE(SUM(tokens_used), 0) AS total_tokens,
                COALESCE(SUM(tokens_used) FILTER (
                    WHERE processed_at > NOW() - INTERVAL '7 days'
                ), 0) AS recent_tokens
            FROM meineke_word_lemma_documents
        """)
        row = cur.fetchone()
        word_lemma_total = int(row[0] or 0)
        word_lemma_completed = int(row[1] or 0)
        word_lemma_pending = int(row[2] or 0)
        word_lemma_processing = int(row[3] or 0)
        word_lemma_error = int(row[4] or 0)
        word_lemma_rate = int(row[5] or 0)
        word_lemma_tokens = int(row[6] or 0)
        word_lemma_recent_tokens = int(row[7] or 0)
        stats["meineke_word_lemmatization"] = {
            "name": "Meineke Word Lemmatization",
            "total": word_lemma_total,
            "completed": word_lemma_completed,
            "pending": max(word_lemma_total - word_lemma_completed, 0),
            "unit": "documents",
            "rate_7d": word_lemma_rate,
            "detail": (
                f"status pending/processing/error: "
                f"{word_lemma_pending:,}/{word_lemma_processing:,}/{word_lemma_error:,}; "
                f"{word_lemma_tokens:,} tokens recorded, {word_lemma_recent_tokens:,} in the last 7 days"
            ),
        }

    # 15. nodegoat sync
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN last_synced_to_nodegoat_at IS NOT NULL THEN 1 END) as synced
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL AND billerbeck_id != ''
    """)
    row = cur.fetchone()
    stats["nodegoat_sync"] = {
        "name": "nodegoat Sync",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "entries",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE last_synced_to_nodegoat_at > NOW() - INTERVAL '7 days'
    """)
    stats["nodegoat_sync"]["rate_7d"] = cur.fetchone()[0]

    return stats


def estimate_completion(pending: int, rate_7d: int, planned_rate_per_day: int | None = None) -> str:
    """Estimate days to completion based on observed rate or configured nightly capacity."""
    if pending == 0:
        return "complete"
    observed_rate_per_day = rate_7d / 7 if rate_7d > 0 else 0
    configured_rate_per_day = planned_rate_per_day or 0
    effective_rate_per_day = max(observed_rate_per_day, configured_rate_per_day)
    if effective_rate_per_day <= 0:
        return "stalled"

    days = pending / effective_rate_per_day
    if days < 1:
        return "< 1 day"
    elif days < 7:
        return f"{days:.1f} days"
    elif days < 30:
        return f"{days/7:.1f} weeks"
    elif days < 365:
        return f"{days/30:.1f} months"
    else:
        return f"{days/365:.1f} years"


def generate_html(stats: dict) -> str:
    """Generate HTML progress page."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for key, data in stats.items():
        total = data["total"]
        completed = data["completed"]
        pending = data["pending"]
        rate_7d = data.get("rate_7d", 0)

        pct = (completed / total * 100) if total > 0 else 0
        bar_pct = max(0, min(pct, 100))
        eta = estimate_completion(pending, rate_7d, data.get("planned_rate_per_day"))

        # Color based on progress
        if pct >= 100:
            color = "#22c55e"  # green
        elif pct >= 75:
            color = "#3b82f6"  # blue
        elif pct >= 50:
            color = "#eab308"  # yellow
        elif pct >= 25:
            color = "#f97316"  # orange
        else:
            color = "#ef4444"  # red

        stage_cell = f"<strong>{html_module.escape(str(data['name']))}</strong>"
        if data.get("detail"):
            detail = html_module.escape(str(data["detail"]))
            stage_cell += f'<div style="color: #6b7280; font-size: 0.85em; margin-top: 3px;">{detail}</div>'

        rows.append(f"""
        <tr>
            <td>{stage_cell}</td>
            <td style="text-align: right;">{completed:,}</td>
            <td style="text-align: right;">{total:,}</td>
            <td>
                <div style="background: #e5e7eb; border-radius: 4px; overflow: hidden; height: 20px;">
                    <div style="background: {color}; width: {bar_pct:.1f}%; height: 100%;"></div>
                </div>
            </td>
            <td style="text-align: right;">{pct:.1f}%</td>
            <td style="text-align: right;">{rate_7d:,}/week</td>
            <td style="text-align: right;"><em>{eta}</em></td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos Pipeline Progress</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f9fafb;
        }}
        h1 {{
            color: #1f2937;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }}
        .updated {{
            color: #6b7280;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: #1f2937;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }}
        tr:hover {{
            background: #f9fafb;
        }}
        .note {{
            margin-top: 20px;
            padding: 15px;
            background: #fef3c7;
            border-radius: 8px;
            color: #92400e;
        }}
        a {{
            color: #2563eb;
        }}
    </style>
</head>
<body>
    <h1>Stephanos Pipeline Progress</h1>
    <p class="updated">Last updated: {now}</p>

    <table>
        <thead>
            <tr>
                <th>Stage</th>
                <th style="text-align: right;">Done</th>
                <th style="text-align: right;">Total</th>
                <th style="width: 200px;">Progress</th>
                <th style="text-align: right;">%</th>
                <th style="text-align: right;">Rate</th>
                <th style="text-align: right;">ETA</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>

    <div class="note">
        <strong>Note:</strong> ETA estimates use the faster of the observed 7-day rate and any configured
        nightly cron limit known to this page. "Stalled" means no observed progress and no configured
        nightly rate is known. Proper-noun and etymology extraction
        are measured over translated lemmas, matching the nightly jobs. Wikidata stages count
        rows once they have a recorded outcome, including not-found, ambiguous, and
        human-reviewed cases. Retired Greek Billerbeck OCR stages are intentionally omitted;
        the active German-reference lane is internal and reported separately when present.
    </div>

    <p style="margin-top: 20px;">
        <a href="index.html">&larr; Back to main site</a> |
        <a href="statistics.html">Statistics</a> |
        <a href="downloads.html">Downloads</a>
    </p>
</body>
</html>
"""
    return html


def main():
    print("Generating pipeline progress page...")

    conn = db.get_connection()
    stats = get_progress_stats(conn)
    conn.close()

    html = generate_html(stats)

    # Write to reference_site
    output_path = Path("reference_site/pipeline.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    print(f"Written to {output_path}")

    # Also write JSON for potential API use
    json_path = Path("reference_site/pipeline.json")
    json_path.write_text(json.dumps(stats, indent=2, default=str))
    print(f"JSON written to {json_path}")

    # Print summary
    print("\nPipeline Status:")
    print("-" * 60)
    for key, data in stats.items():
        pct = (data["completed"] / data["total"] * 100) if data["total"] > 0 else 0
        eta = estimate_completion(data["pending"], data.get("rate_7d", 0), data.get("planned_rate_per_day"))
        print(f"  {data['name']:25} {pct:5.1f}%  ({eta})")


if __name__ == "__main__":
    main()
