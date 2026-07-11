#!/usr/bin/env python3
"""
Refresh the current canonical authority projection from entity sources.

This does not replace the source-specific review tables. It copies their current
effective IDs into a shared authority/entity surface so we can answer questions
like "which Wikidata/ToposText/Pleiades/RE IDs do we currently know about?"
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass

from psycopg2.extras import Json

from generate_topostext_intake_report import DEFAULT_SOURCE_NAME


REAL_AUTHORITY_NAMESPACES = {
    "wikidata",
    "topostext",
    "pleiades",
    "re",
    "manto",
    "brady_local",
    "topostext_pending",
    "topostext_new",
}
MAX_INLINE_PRUNE_ROWS = 100_000


@dataclass(frozen=True)
class RefreshStats:
    topostext_mentions: int = 0
    place_clusters: int = 0
    proper_nouns: int = 0
    authority_records: int = 0
    canonical_entities: int = 0
    authority_links: int = 0
    canonical_mentions: int = 0


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def normalized_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", clean_text(value))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def normalize_authority(namespace: str, authority_id: str) -> tuple[str, str]:
    namespace = clean_text(namespace).casefold()
    authority_id = clean_text(authority_id)
    if namespace == "wikidata" and authority_id:
        authority_id = authority_id.upper()
    if namespace == "pleiades" and authority_id.lower().startswith("p") and authority_id[1:].isdigit():
        authority_id = authority_id[1:]
    return namespace, authority_id


def is_real_authority(namespace: str, authority_id: str) -> bool:
    namespace, authority_id = normalize_authority(namespace, authority_id)
    if namespace not in REAL_AUTHORITY_NAMESPACES:
        return False
    if not authority_id or authority_id.casefold() == "zzz":
        return False
    return True


def authority_uri(namespace: str, authority_id: str, fallback: str = "") -> str:
    namespace, authority_id = normalize_authority(namespace, authority_id)
    if fallback:
        return fallback
    if namespace == "wikidata":
        return f"https://www.wikidata.org/wiki/{authority_id}"
    if namespace == "pleiades":
        return f"https://pleiades.stoa.org/places/{authority_id}"
    if namespace == "topostext":
        return f"https://topostext.org/place/{authority_id}"
    return ""


def entity_kind_from_topostext(row: dict) -> str:
    if clean_text(row.get("place_type_kind")):
        return clean_text(row["place_type_kind"])
    tag_name = clean_text(row.get("tag_name")).casefold()
    if tag_name in {"place", "ethnic", "person", "demonym", "patnym"}:
        return tag_name
    if tag_name == "prn":
        return "entity"
    return tag_name or "entity"


def canonical_status(source_status: str, has_authority: bool) -> str:
    status = clean_text(source_status).casefold()
    if status in {"approved", "corrected", "added", "confirmed", "linked"}:
        return "confirmed"
    if status == "not_alignable":
        return "not_alignable"
    if status in {"removed", "rejected"}:
        return "rejected"
    if has_authority:
        return "candidate"
    return "needs_review"


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    if isinstance(row, dict):
        return bool(next(iter(row.values())))
    return bool(row and row[0])


def latest_topostext_snapshot_id(cur, source_name: str) -> int | None:
    cur.execute(
        """
        SELECT s.id
        FROM entity_source_snapshots s
        JOIN topostext_intake_entries e
          ON e.snapshot_id = s.id
        WHERE s.source_name = %s
        GROUP BY s.id, s.fetched_at
        ORDER BY s.fetched_at DESC, s.id DESC
        LIMIT 1
        """,
        (source_name,),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def upsert_authority_record(
    cur,
    *,
    namespace: str,
    authority_id: str,
    label: str,
    description: str = "",
    entity_kind: str = "",
    uri: str = "",
    source_name: str,
    metadata: dict | None = None,
) -> int:
    namespace, authority_id = normalize_authority(namespace, authority_id)
    cur.execute(
        """
        INSERT INTO authority_records (
            namespace,
            authority_id,
            authority_uri,
            display_label,
            description,
            entity_kind,
            source_name,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (namespace, authority_id) DO UPDATE SET
            authority_uri = COALESCE(NULLIF(EXCLUDED.authority_uri, ''), authority_records.authority_uri),
            display_label = COALESCE(NULLIF(EXCLUDED.display_label, ''), authority_records.display_label),
            description = COALESCE(NULLIF(EXCLUDED.description, ''), authority_records.description),
            entity_kind = COALESCE(NULLIF(EXCLUDED.entity_kind, ''), authority_records.entity_kind),
            source_name = COALESCE(NULLIF(EXCLUDED.source_name, ''), authority_records.source_name),
            last_seen_at = now(),
            metadata = authority_records.metadata || EXCLUDED.metadata,
            updated_at = now()
        RETURNING id
        """,
        (
            namespace,
            authority_id,
            authority_uri(namespace, authority_id, uri),
            clean_text(label),
            clean_text(description),
            clean_text(entity_kind),
            source_name,
            Json(metadata or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_canonical_entity(
    cur,
    *,
    entity_key: str,
    label: str,
    entity_kind: str,
    resolution_status: str,
    preferred_authority_record_id: int | None,
    source_name: str,
    metadata: dict | None = None,
) -> int:
    cur.execute(
        """
        INSERT INTO canonical_entities (
            entity_key,
            display_label,
            normalized_label,
            entity_kind,
            resolution_status,
            preferred_authority_record_id,
            source_name,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (entity_key) DO UPDATE SET
            display_label = COALESCE(NULLIF(EXCLUDED.display_label, ''), canonical_entities.display_label),
            normalized_label = COALESCE(NULLIF(EXCLUDED.normalized_label, ''), canonical_entities.normalized_label),
            entity_kind = COALESCE(NULLIF(EXCLUDED.entity_kind, ''), canonical_entities.entity_kind),
            resolution_status = EXCLUDED.resolution_status,
            preferred_authority_record_id = COALESCE(
                EXCLUDED.preferred_authority_record_id,
                canonical_entities.preferred_authority_record_id
            ),
            source_name = COALESCE(NULLIF(EXCLUDED.source_name, ''), canonical_entities.source_name),
            metadata = canonical_entities.metadata || EXCLUDED.metadata,
            updated_at = now()
        RETURNING id
        """,
        (
            clean_text(entity_key),
            clean_text(label),
            normalized_label(label),
            clean_text(entity_kind),
            resolution_status,
            preferred_authority_record_id,
            source_name,
            Json(metadata or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_authority_link(
    cur,
    *,
    canonical_entity_id: int,
    authority_record_id: int,
    link_status: str,
    confidence: str,
    source_table: str,
    source_id: str,
    source_snapshot_id: int | None = None,
    evidence_text: str = "",
    metadata: dict | None = None,
) -> int:
    cur.execute(
        """
        INSERT INTO canonical_entity_authority_links (
            canonical_entity_id,
            authority_record_id,
            link_status,
            confidence,
            source_table,
            source_id,
            source_snapshot_id,
            evidence_text,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (canonical_entity_id, authority_record_id, source_table, source_id)
        DO UPDATE SET
            link_status = EXCLUDED.link_status,
            confidence = COALESCE(NULLIF(EXCLUDED.confidence, ''), canonical_entity_authority_links.confidence),
            source_snapshot_id = COALESCE(EXCLUDED.source_snapshot_id, canonical_entity_authority_links.source_snapshot_id),
            is_current = true,
            evidence_text = COALESCE(NULLIF(EXCLUDED.evidence_text, ''), canonical_entity_authority_links.evidence_text),
            metadata = canonical_entity_authority_links.metadata || EXCLUDED.metadata,
            updated_at = now()
        RETURNING id
        """,
        (
            canonical_entity_id,
            authority_record_id,
            link_status,
            confidence,
            source_table,
            source_id,
            source_snapshot_id,
            clean_text(evidence_text),
            Json(metadata or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_mention(
    cur,
    *,
    canonical_entity_id: int | None,
    authority_record_id: int | None,
    source_table: str,
    source_id: str,
    source_snapshot_id: int | None,
    work: str = "",
    paragraph_id: str = "",
    entry_key: str = "",
    tag_name: str = "",
    tag_id: str = "",
    mention_text: str = "",
    context: str = "",
    action_status: str = "",
    metadata: dict | None = None,
) -> int:
    cur.execute(
        """
        INSERT INTO canonical_entity_mentions (
            canonical_entity_id,
            authority_record_id,
            source_table,
            source_id,
            source_snapshot_id,
            work,
            paragraph_id,
            entry_key,
            tag_name,
            tag_id,
            mention_text,
            context,
            action_status,
            is_current,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s)
        ON CONFLICT (source_table, source_id) DO UPDATE SET
            canonical_entity_id = EXCLUDED.canonical_entity_id,
            authority_record_id = EXCLUDED.authority_record_id,
            source_snapshot_id = EXCLUDED.source_snapshot_id,
            work = EXCLUDED.work,
            paragraph_id = EXCLUDED.paragraph_id,
            entry_key = EXCLUDED.entry_key,
            tag_name = EXCLUDED.tag_name,
            tag_id = EXCLUDED.tag_id,
            mention_text = EXCLUDED.mention_text,
            context = EXCLUDED.context,
            action_status = EXCLUDED.action_status,
            is_current = true,
            metadata = canonical_entity_mentions.metadata || EXCLUDED.metadata,
            observed_at = now(),
            updated_at = now()
        RETURNING id
        """,
        (
            canonical_entity_id,
            authority_record_id,
            source_table,
            source_id,
            source_snapshot_id,
            clean_text(work),
            clean_text(paragraph_id),
            clean_text(entry_key),
            clean_text(tag_name),
            clean_text(tag_id),
            clean_text(mention_text),
            clean_text(context),
            clean_text(action_status),
            Json(metadata or {}),
        ),
    )
    return int(cur.fetchone()["id"])


def authority_entity_key(namespace: str, authority_id: str) -> str:
    namespace, authority_id = normalize_authority(namespace, authority_id)
    return f"{namespace}:{authority_id}"


def deactivate_current_source_rows(
    cur,
    *,
    link_source_table: str,
    mention_source_table: str | None = None,
) -> Counter[str]:
    """Deactivate only rows that can transition from current to historical."""
    stats: Counter[str] = Counter()
    cur.execute(
        """
        UPDATE canonical_entity_authority_links
        SET is_current = false, updated_at = now()
        WHERE source_table = %s
          AND is_current
        """,
        (link_source_table,),
    )
    stats["deactivated_authority_links"] += max(cur.rowcount, 0)
    if mention_source_table:
        cur.execute(
            """
            UPDATE canonical_entity_mentions
            SET is_current = false, updated_at = now()
            WHERE source_table = %s
              AND is_current
            """,
            (mention_source_table,),
        )
        stats["deactivated_canonical_mentions"] += max(cur.rowcount, 0)
    return stats


def prune_inactive_source_rows(
    cur,
    *,
    link_source_table: str,
    mention_source_table: str | None = None,
) -> Counter[str]:
    """Remove inactive projection rows after their current replacements exist."""
    stats: Counter[str] = Counter()
    counts = []
    for table_name, source_table in (
        ("canonical_entity_authority_links", link_source_table),
        ("canonical_entity_mentions", mention_source_table),
    ):
        if not source_table:
            continue
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE source_table = %s
              AND NOT is_current
            """,
            (source_table,),
        )
        counts.append((table_name, int(cur.fetchone()["count"])))
    oversized = [(table_name, count) for table_name, count in counts if count > MAX_INLINE_PRUNE_ROWS]
    if oversized:
        details = ", ".join(f"{table_name}={count}" for table_name, count in oversized)
        raise RuntimeError(
            f"Inline canonical-history prune is too large ({details}); "
            "run prune_canonical_authority_history.py first"
        )

    cur.execute(
        """
        DELETE FROM canonical_entity_authority_links
        WHERE source_table = %s
          AND NOT is_current
        """,
        (link_source_table,),
    )
    stats["pruned_authority_links"] += max(cur.rowcount, 0)
    if mention_source_table:
        cur.execute(
            """
            DELETE FROM canonical_entity_mentions
            WHERE source_table = %s
              AND NOT is_current
            """,
            (mention_source_table,),
        )
        stats["pruned_canonical_mentions"] += max(cur.rowcount, 0)
    return stats


def refresh_topostext_mentions(cur, source_name: str, snapshot_id: int | None) -> Counter[str]:
    if snapshot_id is None:
        snapshot_id = latest_topostext_snapshot_id(cur, source_name)
    stats: Counter[str] = Counter()
    if snapshot_id is None:
        return stats

    stats.update(
        deactivate_current_source_rows(
            cur,
            link_source_table="topostext_intake_mentions",
            mention_source_table="topostext_intake_mentions",
        )
    )
    cur.execute(
        """
        SELECT
            m.id,
            m.snapshot_id,
            m.work,
            m.paragraph_id,
            m.entry_key,
            m.tag_name,
            m.tag_id,
            m.authority_namespace,
            m.authority_id,
            m.authority_url,
            m.action_status,
            m.mention_text,
            m.context,
            m.mention_fingerprint,
            m.re_short_definition,
            m.place_type_kind,
            e.title AS entry_title
        FROM topostext_intake_mentions m
        JOIN topostext_intake_entries e
          ON e.id = m.entry_id
        WHERE m.snapshot_id = %s
        ORDER BY m.id
        """,
        (snapshot_id,),
    )
    for row in cur.fetchall():
        stats["topostext_mentions"] += 1
        authority_record_id = None
        canonical_entity_id = None
        namespace = clean_text(row.get("authority_namespace"))
        authority_id = clean_text(row.get("authority_id"))
        kind = entity_kind_from_topostext(row)
        label = clean_text(row.get("mention_text") or row.get("entry_title"))
        if is_real_authority(namespace, authority_id):
            authority_record_id = upsert_authority_record(
                cur,
                namespace=namespace,
                authority_id=authority_id,
                label=label,
                description=row.get("re_short_definition") or "",
                entity_kind=kind,
                uri=row.get("authority_url") or "",
                source_name="topostext_intake",
                metadata={"latest_topostext_snapshot_id": snapshot_id},
            )
            stats["authority_records"] += 1
            canonical_entity_id = upsert_canonical_entity(
                cur,
                entity_key=authority_entity_key(namespace, authority_id),
                label=label,
                entity_kind=kind,
                resolution_status=canonical_status(row.get("action_status") or "", True),
                preferred_authority_record_id=authority_record_id,
                source_name="topostext_intake",
                metadata={"source": "topostext_intake_mentions"},
            )
            stats["canonical_entities"] += 1
            upsert_authority_link(
                cur,
                canonical_entity_id=canonical_entity_id,
                authority_record_id=authority_record_id,
                link_status=canonical_status(row.get("action_status") or "", True),
                confidence="",
                source_table="topostext_intake_mentions",
                source_id=str(row["mention_fingerprint"]),
                source_snapshot_id=snapshot_id,
                evidence_text=row.get("context") or "",
                metadata={
                    "tag_name": row.get("tag_name") or "",
                    "source_mention_id": row["id"],
                },
            )
            stats["authority_links"] += 1
        upsert_mention(
            cur,
            canonical_entity_id=canonical_entity_id,
            authority_record_id=authority_record_id,
            source_table="topostext_intake_mentions",
            source_id=str(row["mention_fingerprint"]),
            source_snapshot_id=snapshot_id,
            work=row.get("work") or "",
            paragraph_id=row.get("paragraph_id") or "",
            entry_key=row.get("entry_key") or "",
            tag_name=row.get("tag_name") or "",
            tag_id=row.get("tag_id") or "",
            mention_text=row.get("mention_text") or "",
            context=row.get("context") or "",
            action_status=row.get("action_status") or "",
            metadata={
                "entry_title": row.get("entry_title") or "",
                "source_mention_id": row["id"],
            },
        )
        stats["canonical_mentions"] += 1
    return stats


def refresh_place_clusters(cur) -> Counter[str]:
    stats: Counter[str] = Counter()
    if not table_exists(cur, "effective_place_clusters"):
        return stats
    cur.execute(
        """
        SELECT
            id,
            effective_display_label,
            effective_canonical_name,
            effective_place_type,
            effective_region,
            effective_preferred_external_id_type,
            effective_preferred_external_id_value,
            effective_wikidata_qid,
            effective_topostext_id,
            effective_pleiades_id,
            effective_manto_id,
            effective_resolution_status,
            effective_resolution_source
        FROM effective_place_clusters
        ORDER BY id
        """
    )
    for row in cur.fetchall():
        stats["place_clusters"] += 1
        label = clean_text(row.get("effective_display_label") or row.get("effective_canonical_name") or f"place cluster {row['id']}")
        kind = clean_text(row.get("effective_place_type") or "place")
        authority_specs = []
        for namespace, column in (
            ("wikidata", "effective_wikidata_qid"),
            ("topostext", "effective_topostext_id"),
            ("pleiades", "effective_pleiades_id"),
            ("manto", "effective_manto_id"),
        ):
            value = clean_text(row.get(column))
            if value:
                authority_specs.append((namespace, value))
        preferred = (
            normalize_authority(row.get("effective_preferred_external_id_type") or "", row.get("effective_preferred_external_id_value") or "")
            if row.get("effective_preferred_external_id_type") and row.get("effective_preferred_external_id_value")
            else None
        )
        if preferred not in authority_specs:
            preferred = authority_specs[0] if authority_specs else None
        authority_ids = {}
        for namespace, authority_id in authority_specs:
            record_id = upsert_authority_record(
                cur,
                namespace=namespace,
                authority_id=authority_id,
                label=label,
                description=row.get("effective_region") or "",
                entity_kind=kind,
                uri="",
                source_name="place_clusters",
                metadata={"place_cluster_id": row["id"]},
            )
            stats["authority_records"] += 1
            authority_ids[normalize_authority(namespace, authority_id)] = record_id
        preferred_record_id = authority_ids.get(preferred) if preferred else None
        entity_key = authority_entity_key(*preferred) if preferred else f"place_cluster:{row['id']}"
        entity_id = upsert_canonical_entity(
            cur,
            entity_key=entity_key,
            label=label,
            entity_kind=kind,
            resolution_status=canonical_status(row.get("effective_resolution_status") or "", bool(authority_specs)),
            preferred_authority_record_id=preferred_record_id,
            source_name="place_clusters",
            metadata={"place_cluster_id": row["id"], "region": row.get("effective_region") or ""},
        )
        stats["canonical_entities"] += 1
        for (namespace, authority_id), record_id in authority_ids.items():
            upsert_authority_link(
                cur,
                canonical_entity_id=entity_id,
                authority_record_id=record_id,
                link_status=canonical_status(row.get("effective_resolution_status") or "", True),
                confidence=row.get("effective_resolution_source") or "",
                source_table="effective_place_clusters",
                source_id=str(row["id"]),
                evidence_text=label,
                metadata={"preferred": [namespace, authority_id] == list(preferred or ())},
            )
            stats["authority_links"] += 1
    return stats


def refresh_proper_nouns(cur) -> Counter[str]:
    stats: Counter[str] = Counter()
    if not table_exists(cur, "effective_proper_nouns"):
        return stats
    cur.execute(
        """
        SELECT
            id,
            proper_noun,
            lemma_form,
            noun_type,
            role,
            effective_wikidata_qid,
            effective_wikidata_confidence,
            effective_resolution_status,
            effective_resolution_source
        FROM effective_proper_nouns
        ORDER BY id
        """
    )
    for row in cur.fetchall():
        stats["proper_nouns"] += 1
        label = clean_text(row.get("proper_noun") or row.get("lemma_form") or f"proper noun {row['id']}")
        kind = "source" if clean_text(row.get("role")) == "source" else clean_text(row.get("noun_type") or "entity")
        qid = clean_text(row.get("effective_wikidata_qid"))
        authority_record_id = None
        if qid:
            authority_record_id = upsert_authority_record(
                cur,
                namespace="wikidata",
                authority_id=qid,
                label=label,
                entity_kind=kind,
                source_name="proper_nouns",
                metadata={"proper_noun_id": row["id"]},
            )
            stats["authority_records"] += 1
        entity_key = authority_entity_key("wikidata", qid) if qid else f"proper_noun:{row['id']}"
        entity_id = upsert_canonical_entity(
            cur,
            entity_key=entity_key,
            label=label,
            entity_kind=kind,
            resolution_status=canonical_status(row.get("effective_resolution_status") or "", bool(qid)),
            preferred_authority_record_id=authority_record_id,
            source_name="proper_nouns",
            metadata={"proper_noun_id": row["id"], "role": row.get("role") or ""},
        )
        stats["canonical_entities"] += 1
        if authority_record_id:
            upsert_authority_link(
                cur,
                canonical_entity_id=entity_id,
                authority_record_id=authority_record_id,
                link_status=canonical_status(row.get("effective_resolution_status") or "", True),
                confidence=row.get("effective_wikidata_confidence") or "",
                source_table="effective_proper_nouns",
                source_id=str(row["id"]),
                evidence_text=label,
                metadata={"resolution_source": row.get("effective_resolution_source") or ""},
            )
            stats["authority_links"] += 1
        upsert_mention(
            cur,
            canonical_entity_id=entity_id,
            authority_record_id=authority_record_id,
            source_table="proper_nouns",
            source_id=str(row["id"]),
            source_snapshot_id=None,
            tag_name=kind,
            tag_id=qid,
            mention_text=label,
            action_status=row.get("effective_resolution_status") or "",
            metadata={"role": row.get("role") or ""},
        )
        stats["canonical_mentions"] += 1
    return stats


def write_summary_event(cur, stats: Counter[str], *, snapshot_id: int | None) -> None:
    cur.execute(
        """
        INSERT INTO entity_change_events (
            event_kind,
            event_status,
            source_table,
            source_snapshot_id,
            payload,
            created_by
        )
        VALUES ('authority_refresh', 'completed', 'refresh_canonical_authority_layer.py', %s, %s, 'pipeline')
        """,
        (snapshot_id, Json(dict(stats))),
    )


def refresh_authority_layer(
    *,
    source_name: str,
    snapshot_id: int | None,
    dry_run: bool = False,
    skip_topostext: bool = False,
    prune_history: bool = False,
) -> Counter[str]:
    from db import get_connection

    conn = get_connection(dict_cursor=True)
    try:
        cur = conn.cursor()
        for table_name in (
            "authority_records",
            "canonical_entities",
            "canonical_entity_authority_links",
            "canonical_entity_mentions",
            "entity_change_events",
        ):
            if not table_exists(cur, table_name):
                raise RuntimeError(f"Required table public.{table_name} does not exist; apply migrations first")
        resolved_snapshot_id = snapshot_id if snapshot_id is not None else latest_topostext_snapshot_id(cur, source_name)
        stats = Counter()
        if skip_topostext:
            stats["topostext_skipped"] = 1
        else:
            started_at = time.monotonic()
            stats.update(refresh_topostext_mentions(cur, source_name, resolved_snapshot_id))
            stats["topostext_refresh_milliseconds"] = round((time.monotonic() - started_at) * 1000)
            if prune_history:
                started_at = time.monotonic()
                stats.update(
                    prune_inactive_source_rows(
                        cur,
                        link_source_table="topostext_intake_mentions",
                        mention_source_table="topostext_intake_mentions",
                    )
                )
                stats["topostext_prune_milliseconds"] = round((time.monotonic() - started_at) * 1000)

        started_at = time.monotonic()
        stats.update(refresh_place_clusters(cur))
        stats["place_cluster_refresh_milliseconds"] = round((time.monotonic() - started_at) * 1000)
        started_at = time.monotonic()
        stats.update(refresh_proper_nouns(cur))
        stats["proper_noun_refresh_milliseconds"] = round((time.monotonic() - started_at) * 1000)
        write_summary_event(cur, stats, snapshot_id=resolved_snapshot_id)
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh canonical authority tables from current source-specific entity rows.")
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--snapshot-id", type=int, help="ToposText snapshot id to treat as current")
    parser.add_argument("--skip-topostext", action="store_true", help="Refresh place/proper-noun sources only")
    parser.add_argument(
        "--prune-history",
        action="store_true",
        help="Delete inactive ToposText canonical mentions and authority links after refresh",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    stats = refresh_authority_layer(
        source_name=args.source_name,
        snapshot_id=args.snapshot_id,
        dry_run=args.dry_run,
        skip_topostext=args.skip_topostext,
        prune_history=args.prune_history,
    )
    for key, value in sorted(stats.items()):
        print(f"{key}={value}")
    if args.dry_run:
        print("dry_run=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
