#!/usr/bin/env python3
"""
Merge Meineke-only duplicate assembled_lemmas rows into their Billerbeck targets.

This targets the Feb 2026 contamination pattern where:
  - a lemma row has ONLY Meineke scan images attached (no Billerbeck images)
  - greek_text/human_greek_text are empty (legacy assembly artifact)

The merge attaches the Meineke scan images to the target lemma (via lemma_images),
moves Meineke source text versions (lemma_source_text_versions) onto the target,
and deletes the source lemma row.

Important rule:
  - If the target lemma already has a current Meineke source text version
    (source_document='meineke' AND is_current=TRUE), we DO NOT override it.
    Moved versions are kept as non-current in that case.

Usage:
  uv run merge_meineke_only_duplicates.py --mapping-file meineke_only_merge_candidates.agree_hi.tsv   # dry run
  uv run merge_meineke_only_duplicates.py --apply                                                   # apply default mapping

This script executes SQL on raksasa via `ssh ... psql ...` and does not require
psycopg2 connectivity from the local machine.

Safety:
  - Source lemmas are filtered to have NO human translations.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB_HOST = "raksasa"
DEFAULT_DB_NAME = "stephanos"
DEFAULT_MAPPING_FILE = Path("meineke_only_merge_candidates.agree_hi.tsv")


@dataclass(frozen=True)
class MergePair:
    source_lemma_id: int
    target_lemma_id: int


def _parse_int(value: str, *, field: str, context: str) -> int:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{context}: missing {field}")
    try:
        return int(text)
    except ValueError as e:
        raise ValueError(f"{context}: invalid integer {field}={value!r}") from e


def load_mapping_pairs(mapping_file: Path, *, limit: int | None) -> list[MergePair]:
    mapping_file = mapping_file.expanduser().resolve()
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")

    with mapping_file.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = reader.fieldnames or []

        if "source_lemma_id" in fieldnames and "target_lemma_id" in fieldnames:
            src_col = "source_lemma_id"
            tgt_col = "target_lemma_id"
        elif "mineke_lemma_id" in fieldnames and "biller_match_lemma_id" in fieldnames:
            src_col = "mineke_lemma_id"
            tgt_col = "biller_match_lemma_id"
        elif "mineke_lemma_id" in fieldnames and "match_billerbeck_lemma_id" in fieldnames:
            src_col = "mineke_lemma_id"
            tgt_col = "match_billerbeck_lemma_id"
        else:
            raise ValueError(
                f"Unrecognized mapping headers in {mapping_file.name}: {', '.join(fieldnames)}. "
                "Expected (source_lemma_id,target_lemma_id) or (mineke_lemma_id,biller_match_lemma_id) "
                "or (mineke_lemma_id,match_billerbeck_lemma_id)."
            )

        pairs_by_source: dict[int, int] = {}
        parsed: list[MergePair] = []
        for idx, row in enumerate(reader, start=2):
            if limit is not None and len(parsed) >= int(limit):
                break
            context = f"{mapping_file.name}:{idx}"
            src = _parse_int(row.get(src_col, ""), field=src_col, context=context)
            tgt = _parse_int(row.get(tgt_col, ""), field=tgt_col, context=context)
            if src == tgt:
                continue

            existing = pairs_by_source.get(src)
            if existing is not None and existing != tgt:
                raise ValueError(f"{context}: source_lemma_id {src} maps to multiple targets ({existing}, {tgt})")
            pairs_by_source[src] = tgt
            parsed.append(MergePair(source_lemma_id=src, target_lemma_id=tgt))

    # Preserve file order while deduplicating by source.
    seen_sources: set[int] = set()
    deduped: list[MergePair] = []
    for pair in parsed:
        if pair.source_lemma_id in seen_sources:
            continue
        seen_sources.add(pair.source_lemma_id)
        deduped.append(pair)
    return deduped


def run_remote_psql(ssh_host: str, sql: str, *, db_name: str) -> str:
    cmd = [
        "ssh",
        ssh_host,
        "psql",
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-X",
        "-q",
        "-At",
    ]
    proc = subprocess.run(
        cmd,
        input=sql,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Remote psql failed.\n"
            f"ssh_host={ssh_host} db={db_name}\n"
            f"exit={proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}\n"
        )
    return proc.stdout or ""


def _sql_insert_merge_map(pairs: list[MergePair]) -> str:
    if not pairs:
        return ""

    chunks: list[str] = []
    chunk: list[str] = []
    for pair in pairs:
        chunk.append(f"({pair.source_lemma_id}, {pair.target_lemma_id})")
        if len(chunk) >= 500:
            chunks.append(
                "INSERT INTO merge_map (source_lemma_id, target_lemma_id) VALUES\n  "
                + ",\n  ".join(chunk)
                + ";\n"
            )
            chunk = []
    if chunk:
        chunks.append(
            "INSERT INTO merge_map (source_lemma_id, target_lemma_id) VALUES\n  "
            + ",\n  ".join(chunk)
            + ";\n"
        )
    return "".join(chunks)


def build_dry_run_sql(pairs: list[MergePair]) -> str:
    inserts = _sql_insert_merge_map(pairs)
    return f"""
BEGIN;

CREATE TEMP TABLE merge_map (
  source_lemma_id INTEGER PRIMARY KEY,
  target_lemma_id INTEGER NOT NULL
);

{inserts}

CREATE TEMP TABLE lemma_sources AS
SELECT
  a.id AS lemma_id,
  BOOL_OR(i.source_document='meineke') AS has_meineke,
  BOOL_OR(i.source_document='billerbeck') AS has_billerbeck
FROM assembled_lemmas a
LEFT JOIN lemma_images li ON li.lemma_id = a.id
LEFT JOIN images i ON i.id = li.image_id
GROUP BY a.id;

CREATE TEMP TABLE valid_map AS
SELECT
  mm.source_lemma_id,
  mm.target_lemma_id
FROM merge_map mm
JOIN assembled_lemmas src ON src.id = mm.source_lemma_id
JOIN assembled_lemmas tgt ON tgt.id = mm.target_lemma_id
JOIN lemma_sources ss ON ss.lemma_id = src.id
JOIN lemma_sources ts ON ts.lemma_id = tgt.id
WHERE COALESCE(ss.has_meineke, FALSE) = TRUE
  AND COALESCE(ss.has_billerbeck, FALSE) = FALSE
  AND COALESCE(ts.has_billerbeck, FALSE) = TRUE
  AND src.id <> tgt.id
  AND COALESCE(src.greek_text, '') = ''
  AND COALESCE(src.human_greek_text, '') = ''
  AND COALESCE(src.translated, 0) = 0
  AND NOT EXISTS (SELECT 1 FROM human_translations ht WHERE ht.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM translation_runs tr WHERE tr.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM proper_nouns pn WHERE pn.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM etymologies e WHERE e.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM lemma_publication_targets lpt WHERE lpt.lemma_id = src.id);

SELECT 'mapping_rows' AS metric, COUNT(*)::text AS value FROM merge_map
UNION ALL
SELECT 'valid_rows' AS metric, COUNT(*)::text AS value FROM valid_map
UNION ALL
SELECT 'skipped_rows' AS metric, (COUNT(*) - (SELECT COUNT(*) FROM valid_map))::text AS value FROM merge_map
UNION ALL
SELECT 'distinct_targets' AS metric, COUNT(DISTINCT target_lemma_id)::text AS value FROM valid_map
UNION ALL
SELECT 'targets_with_current_meineke' AS metric, COUNT(*)::text AS value
FROM (
  SELECT DISTINCT target_lemma_id
  FROM valid_map vm
  WHERE EXISTS (
    SELECT 1
    FROM lemma_source_text_versions stv
    WHERE stv.lemma_id = vm.target_lemma_id
      AND stv.source_document = 'meineke'
      AND stv.is_current = TRUE
  )
) x
UNION ALL
SELECT 'targets_without_current_meineke' AS metric, COUNT(*)::text AS value
FROM (
  SELECT DISTINCT target_lemma_id
  FROM valid_map vm
  WHERE NOT EXISTS (
    SELECT 1
    FROM lemma_source_text_versions stv
    WHERE stv.lemma_id = vm.target_lemma_id
      AND stv.source_document = 'meineke'
      AND stv.is_current = TRUE
  )
) x
UNION ALL
SELECT 'meineke_images_to_attach' AS metric, COUNT(*)::text AS value
FROM valid_map vm
JOIN lemma_images li ON li.lemma_id = vm.source_lemma_id
JOIN images i ON i.id = li.image_id
WHERE COALESCE(i.source_document, 'billerbeck') = 'meineke'
UNION ALL
SELECT 'meineke_versions_to_move' AS metric, COUNT(*)::text AS value
FROM valid_map vm
JOIN lemma_source_text_versions stv
  ON stv.lemma_id = vm.source_lemma_id
 AND stv.source_document = 'meineke';

ROLLBACK;
""".lstrip()


def build_apply_sql(pairs: list[MergePair]) -> str:
    inserts = _sql_insert_merge_map(pairs)
    return f"""
BEGIN;

CREATE TEMP TABLE merge_map (
  source_lemma_id INTEGER PRIMARY KEY,
  target_lemma_id INTEGER NOT NULL
);

{inserts}

CREATE TEMP TABLE lemma_sources AS
SELECT
  a.id AS lemma_id,
  BOOL_OR(i.source_document='meineke') AS has_meineke,
  BOOL_OR(i.source_document='billerbeck') AS has_billerbeck
FROM assembled_lemmas a
LEFT JOIN lemma_images li ON li.lemma_id = a.id
LEFT JOIN images i ON i.id = li.image_id
GROUP BY a.id;

CREATE TEMP TABLE valid_map AS
SELECT
  mm.source_lemma_id,
  mm.target_lemma_id
FROM merge_map mm
JOIN assembled_lemmas src ON src.id = mm.source_lemma_id
JOIN assembled_lemmas tgt ON tgt.id = mm.target_lemma_id
JOIN lemma_sources ss ON ss.lemma_id = src.id
JOIN lemma_sources ts ON ts.lemma_id = tgt.id
WHERE COALESCE(ss.has_meineke, FALSE) = TRUE
  AND COALESCE(ss.has_billerbeck, FALSE) = FALSE
  AND COALESCE(ts.has_billerbeck, FALSE) = TRUE
  AND src.id <> tgt.id
  AND COALESCE(src.greek_text, '') = ''
  AND COALESCE(src.human_greek_text, '') = ''
  AND COALESCE(src.translated, 0) = 0
  AND NOT EXISTS (SELECT 1 FROM human_translations ht WHERE ht.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM translation_runs tr WHERE tr.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM proper_nouns pn WHERE pn.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM etymologies e WHERE e.lemma_id = src.id)
  AND NOT EXISTS (SELECT 1 FROM lemma_publication_targets lpt WHERE lpt.lemma_id = src.id);

-- Attach Meineke scan images to target lemmas (append after existing positions).
WITH target_max AS (
  SELECT lemma_id, COALESCE(MAX(position), -1) AS max_pos
  FROM lemma_images
  GROUP BY lemma_id
),
source_images AS (
  SELECT
    vm.target_lemma_id AS lemma_id,
    li.image_id,
    ROW_NUMBER() OVER (
      PARTITION BY vm.target_lemma_id
      ORDER BY vm.source_lemma_id, li.position, li.image_id
    ) AS rn
  FROM valid_map vm
  JOIN lemma_images li ON li.lemma_id = vm.source_lemma_id
  JOIN images i ON i.id = li.image_id
  WHERE COALESCE(i.source_document, 'billerbeck') = 'meineke'
),
ins AS (
  INSERT INTO lemma_images (lemma_id, image_id, position)
  SELECT
    si.lemma_id,
    si.image_id,
    COALESCE(tm.max_pos, -1) + si.rn AS position
  FROM source_images si
  LEFT JOIN target_max tm ON tm.lemma_id = si.lemma_id
  ON CONFLICT (lemma_id, image_id) DO UPDATE
    SET position = EXCLUDED.position
  RETURNING 1
)
SELECT 'images_attached' AS metric, COUNT(*)::text AS value FROM ins;

-- Capture and move Meineke source text versions onto target lemmas.
CREATE TEMP TABLE moved_meineke_versions AS
SELECT
  stv.id AS version_id,
  vm.target_lemma_id
FROM valid_map vm
JOIN lemma_source_text_versions stv
  ON stv.lemma_id = vm.source_lemma_id
 AND stv.source_document = 'meineke';

WITH moved AS (
  UPDATE lemma_source_text_versions stv
  SET lemma_id = mv.target_lemma_id,
      is_current = FALSE
  FROM moved_meineke_versions mv
  WHERE stv.id = mv.version_id
  RETURNING 1
)
SELECT 'meineke_versions_moved' AS metric, COUNT(*)::text AS value FROM moved;

-- If a target lemma lacks a current Meineke version, promote exactly one moved version.
WITH targets_needing_current AS (
  SELECT DISTINCT mv.target_lemma_id
  FROM moved_meineke_versions mv
  WHERE NOT EXISTS (
    SELECT 1
    FROM lemma_source_text_versions stv
    WHERE stv.lemma_id = mv.target_lemma_id
      AND stv.source_document = 'meineke'
      AND stv.is_current = TRUE
  )
),
chosen AS (
  SELECT
    mv.target_lemma_id,
    mv.version_id,
    ROW_NUMBER() OVER (
      PARTITION BY mv.target_lemma_id
      ORDER BY stv.created_at DESC, mv.version_id DESC
    ) AS rn
  FROM moved_meineke_versions mv
  JOIN lemma_source_text_versions stv ON stv.id = mv.version_id
  JOIN targets_needing_current t ON t.target_lemma_id = mv.target_lemma_id
),
promoted AS (
  UPDATE lemma_source_text_versions stv
  SET is_current = TRUE
  FROM chosen c
  WHERE stv.id = c.version_id
    AND c.rn = 1
  RETURNING 1
)
SELECT 'targets_backfilled_current' AS metric, COUNT(*)::text AS value FROM promoted;

-- Delete the source duplicate assembled_lemmas rows.
WITH del AS (
  DELETE FROM assembled_lemmas a
  USING valid_map vm
  WHERE a.id = vm.source_lemma_id
  RETURNING 1
)
SELECT 'source_lemmas_deleted' AS metric, COUNT(*)::text AS value FROM del;

COMMIT;
""".lstrip()


def parse_metrics(psql_output: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in (psql_output or "").splitlines():
        if not line.strip():
            continue
        if "|" not in line:
            continue
        key, value = line.split("|", 1)
        metrics[key.strip()] = value.strip()
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge Meineke-only duplicate lemma rows into Billerbeck targets.")
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=DEFAULT_MAPPING_FILE,
        help=f"TSV file with source/target lemma ids (default: {DEFAULT_MAPPING_FILE})",
    )
    parser.add_argument("--ssh-host", default=DEFAULT_DB_HOST, help=f"SSH host running PostgreSQL (default: {DEFAULT_DB_HOST})")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME, help=f"Database name on remote host (default: {DEFAULT_DB_NAME})")
    parser.add_argument("--limit", type=int, help="Process only the first N mapping rows")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    pairs = load_mapping_pairs(args.mapping_file, limit=args.limit)
    if not pairs:
        print("No mapping pairs found; nothing to do.")
        return 0

    sql = build_apply_sql(pairs) if args.apply else build_dry_run_sql(pairs)
    out = run_remote_psql(args.ssh_host, sql, db_name=args.db_name)
    metrics = parse_metrics(out)

    if args.apply:
        print("Applied merge.")
        for key in ("images_attached", "meineke_versions_moved", "targets_backfilled_current", "source_lemmas_deleted"):
            if key in metrics:
                print(f"{key}: {metrics[key]}")
    else:
        print("Dry run (no changes).")
        for key in (
            "mapping_rows",
            "valid_rows",
            "skipped_rows",
            "distinct_targets",
            "targets_with_current_meineke",
            "targets_without_current_meineke",
            "meineke_images_to_attach",
            "meineke_versions_to_move",
        ):
            if key in metrics:
                print(f"{key}: {metrics[key]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
