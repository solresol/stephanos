#!/usr/bin/env python3
"""Import completed external Claude workspace translations into translation_runs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from psycopg2.extras import Json

from claude_variant_config import parse_model_variants, parse_prompt_versions
from paper_corpus import DEFAULT_PAPER_CORPUS, corpus_label, paper_kappa_review_cte_body


TRANSLATION_MARKER_RE = re.compile(r"## Claude Translation\s*\n(.*)\Z", re.S)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
SCRIPT_NAME = "import_claude_translation_workspaces.py"
DEFAULT_PUBLIC_BLOCK_REASON = "external Claude import; kept out of public translation selection"


@dataclass(frozen=True)
class Workspace:
    folder: Path
    model_slug: str
    display_name: str
    profile_name: str
    version: int
    default_model: str
    total_files: int
    translated_files: int


@dataclass(frozen=True)
class ClaudeEntry:
    path: Path
    folder_name: str
    metadata: dict[str, Any]
    translation_text: str
    file_sha256: str
    translation_sha256: str


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def parse_scalar(value: str) -> object:
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value == '""':
        return ""
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        return value


def parse_frontmatter(text: str, *, path: Path) -> dict[str, Any]:
    match = FRONTMATTER_RE.search(text)
    if not match:
        raise ValueError(f"{path} has no YAML-style frontmatter")
    metadata: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = parse_scalar(value)
    return metadata


def read_entry_file(path: Path) -> ClaudeEntry:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    metadata = parse_frontmatter(text, path=path)
    match = TRANSLATION_MARKER_RE.search(text)
    translation_text = (match.group(1) if match else "").strip()
    return ClaudeEntry(
        path=path,
        folder_name=path.parent.name,
        metadata=metadata,
        translation_text=translation_text,
        file_sha256=hashlib.sha256(raw).hexdigest(),
        translation_sha256=hashlib.sha256(translation_text.encode("utf-8")).hexdigest(),
    )


def workspace_entry_paths(folder: Path) -> list[Path]:
    return sorted(path for path in folder.glob("*.md") if path.name != "CLAUDE.md")


def translated_count(folder: Path) -> tuple[int, int]:
    total = 0
    translated = 0
    for path in workspace_entry_paths(folder):
        total += 1
        if read_entry_file(path).translation_text:
            translated += 1
    return total, translated


def discover_workspaces(args) -> list[Workspace]:
    workspace_root = Path(args.workspace_root).expanduser()
    model_variants = parse_model_variants(args.models)
    versions = parse_prompt_versions(args.versions)
    workspaces: list[Workspace] = []
    for variant in model_variants:
        for version in versions:
            folder = workspace_root / f"{args.folder_prefix}-{variant.slug}-v{version}"
            if not folder.is_dir():
                continue
            total, translated = translated_count(folder)
            workspaces.append(
                Workspace(
                    folder=folder,
                    model_slug=variant.slug,
                    display_name=variant.display_name,
                    profile_name=variant.db_profile_name,
                    version=version,
                    default_model=variant.default_model,
                    total_files=total,
                    translated_files=translated,
                )
            )
    return workspaces


def load_profile_version(cur, workspace: Workspace) -> dict[str, Any]:
    cur.execute(
        """
        SELECT
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version,
            COALESCE(NULLIF(pv.default_model, ''), %s) AS default_model,
            COALESCE(pv.uses_guidance_context, FALSE) AS uses_guidance_context
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.name = %s
          AND pv.version = %s
          AND p.active = TRUE
          AND COALESCE(pv.active, TRUE) = TRUE
        LIMIT 1
        """,
        (workspace.default_model, workspace.profile_name, workspace.version),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Missing active DB profile/version for {workspace.profile_name} v{workspace.version}")
    keys = ("profile_id", "profile_name", "profile_version_id", "version", "default_model", "uses_guidance_context")
    return dict(zip(keys, row))


def load_paper_corpus(cur) -> dict[int, dict[str, Any]]:
    cur.execute(
        f"""
        WITH {paper_kappa_review_cte_body("paper_corpus")}
        SELECT
            corpus_order,
            corpus_source_row_id,
            kappa_review_row_id,
            lemma_id,
            human_translation_id
        FROM paper_corpus
        """
    )
    rows: dict[int, dict[str, Any]] = {}
    keys = ("corpus_order", "corpus_source_row_id", "kappa_review_row_id", "lemma_id", "human_translation_id")
    for row in cur.fetchall():
        item = dict(zip(keys, row))
        rows[int(item["corpus_source_row_id"])] = item
    return rows


def existing_import(cur, *, external_file: str, profile_version_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            tr.id,
            tr.request_id,
            tr.translation_text,
            tr.status
        FROM translation_runs tr
        WHERE tr.profile_version_id = %s
          AND tr.request_payload_json->>'external_file' = %s
        ORDER BY tr.id DESC
        LIMIT 1
        """,
        (int(profile_version_id), external_file),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "run_id": int(row[0]),
        "request_id": int(row[1]),
        "translation_text": row[2] or "",
        "status": row[3] or "",
    }


def insert_request(
    cur,
    *,
    entry: ClaudeEntry,
    profile: dict[str, Any],
    model: str,
    created_by: str,
    priority: int,
) -> int:
    cur.execute(
        """
        INSERT INTO translation_run_requests (
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            requested_runs,
            model,
            status,
            created_by,
            started_at,
            finished_at,
            updated_at,
            priority,
            api_mode,
            reasoning_effort
        )
        VALUES (%s, %s, %s, %s, 1, %s, 'completed', %s, NOW(), NOW(), NOW(), %s, 'chat_completions', NULL)
        RETURNING id
        """,
        (
            int(entry.metadata["lemma_id"]),
            int(profile["profile_id"]),
            int(profile["profile_version_id"]),
            int(entry.metadata["source_text_version_id"]),
            model,
            created_by,
            int(priority),
        ),
    )
    return int(cur.fetchone()[0])


def import_payload(
    *,
    entry: ClaudeEntry,
    workspace: Workspace,
    profile: dict[str, Any],
    created_by: str,
) -> dict[str, Any]:
    return {
        "external_import": True,
        "external_provider": "anthropic",
        "external_workspace": workspace.folder.name,
        "external_file": str(entry.path.resolve()),
        "external_file_sha256": entry.file_sha256,
        "external_model_slug": workspace.model_slug,
        "external_model_display_name": workspace.display_name,
        "model": profile["default_model"],
        "corpus": DEFAULT_PAPER_CORPUS,
        "corpus_label": corpus_label(DEFAULT_PAPER_CORPUS),
        "corpus_order": int(entry.metadata["corpus_order"]),
        "corpus_source_row_id": int(entry.metadata["corpus_source_row_id"]),
        "kappa_review_row_id": int(entry.metadata["kappa_review_row_id"]),
        "human_translation_id": int(entry.metadata["human_translation_id"]),
        "source_text_version_id": int(entry.metadata["source_text_version_id"]),
        "profile_name": profile["profile_name"],
        "profile_version_id": int(profile["profile_version_id"]),
        "prompt_version": int(profile["version"]),
        "uses_guidance_context": bool(profile["uses_guidance_context"]),
        "translation_sha256": entry.translation_sha256,
        "imported_by": created_by,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def insert_run(
    cur,
    *,
    request_id: int,
    entry: ClaudeEntry,
    profile: dict[str, Any],
    model: str,
    payload: dict[str, Any],
    public_eligible: bool,
    public_block_reason: str,
) -> int:
    cur.execute(
        """
        INSERT INTO translation_runs (
            request_id,
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            run_index,
            model,
            temperature,
            top_p,
            translation_text,
            tokens_used,
            status,
            public_eligible,
            public_block_reason,
            reviewed_by,
            reviewed_at,
            review_notes,
            completed_at,
            request_payload_json,
            api_mode,
            reasoning_effort,
            input_tokens,
            output_tokens,
            reasoning_tokens
        )
        VALUES (
            %s, %s, %s, %s, %s, 1, %s, NULL, NULL, %s, 0, 'completed',
            %s, %s, NULL, NULL, %s, NOW(), %s, 'chat_completions', NULL, 0, 0, 0
        )
        RETURNING id
        """,
        (
            int(request_id),
            int(entry.metadata["lemma_id"]),
            int(profile["profile_id"]),
            int(profile["profile_version_id"]),
            int(entry.metadata["source_text_version_id"]),
            model,
            entry.translation_text,
            bool(public_eligible),
            public_block_reason if not public_eligible else None,
            f"Imported from external Claude workspace file {entry.path.resolve()}",
            Json(payload),
        ),
    )
    return int(cur.fetchone()[0])


def update_run(
    cur,
    *,
    existing: dict[str, Any],
    entry: ClaudeEntry,
    model: str,
    payload: dict[str, Any],
    public_eligible: bool,
    public_block_reason: str,
) -> int:
    run_id = int(existing["run_id"])
    cur.execute(
        """
        UPDATE translation_runs
        SET translation_text = %s,
            model = %s,
            tokens_used = 0,
            status = 'completed',
            public_eligible = %s,
            public_block_reason = %s,
            review_notes = %s,
            completed_at = NOW(),
            request_payload_json = %s,
            api_mode = 'chat_completions',
            reasoning_effort = NULL,
            input_tokens = 0,
            output_tokens = 0,
            reasoning_tokens = 0,
            error_message = NULL
        WHERE id = %s
        """,
        (
            entry.translation_text,
            model,
            bool(public_eligible),
            public_block_reason if not public_eligible else None,
            f"Updated from external Claude workspace file {entry.path.resolve()}",
            Json(payload),
            run_id,
        ),
    )
    cur.execute(
        """
        UPDATE translation_run_requests
        SET status = 'completed',
            model = %s,
            finished_at = NOW(),
            updated_at = NOW(),
            error_message = NULL
        WHERE id = %s
        """,
        (model, int(existing["request_id"])),
    )
    return run_id


def validate_entry(entry: ClaudeEntry, *, workspace: Workspace, profile: dict[str, Any], corpus_by_source_row: dict[int, dict[str, Any]]) -> None:
    metadata = entry.metadata
    source_row_id = int(metadata["corpus_source_row_id"])
    corpus_row = corpus_by_source_row.get(source_row_id)
    if not corpus_row:
        raise RuntimeError(f"{entry.path}: source row {source_row_id} is not in the live paper corpus")
    checks = {
        "corpus_order": int(corpus_row["corpus_order"]),
        "kappa_review_row_id": int(corpus_row["kappa_review_row_id"]),
        "lemma_id": int(corpus_row["lemma_id"]),
        "human_translation_id": int(corpus_row["human_translation_id"]),
        "profile_name": profile["profile_name"],
        "profile_version_id": int(profile["profile_version_id"]),
        "prompt_version": int(profile["version"]),
    }
    for key, expected in checks.items():
        actual = metadata.get(key)
        if actual != expected:
            raise RuntimeError(f"{entry.path}: metadata {key}={actual!r} does not match expected {expected!r}")
    expected_variant = workspace.display_name
    if metadata.get("claude_variant") != expected_variant:
        raise RuntimeError(f"{entry.path}: claude_variant={metadata.get('claude_variant')!r}, expected {expected_variant!r}")


def record_guidance(cur, *, run_id: int, entry: ClaudeEntry) -> int:
    from translate_lemmas import fetch_guidance_context, record_translation_run_guidance_matches
    from translation_guidance_coverage import refresh_translation_guidance_freshness

    cur.execute("DELETE FROM translation_run_guidance_matches WHERE run_id = %s", (int(run_id),))
    guidance_context = fetch_guidance_context(
        cur,
        lemma_id=int(entry.metadata["lemma_id"]),
        source_text_version_id=int(entry.metadata["source_text_version_id"]),
    )
    record_translation_run_guidance_matches(cur, int(run_id), guidance_context)
    refresh_translation_guidance_freshness(cur, run_id=int(run_id))
    return len(guidance_context)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="all", help="Comma/space model list: sonnet-5, opus-4-8, fable-5, or all.")
    parser.add_argument("--versions", default="1,2,3", help="Comma/space prompt versions to import.")
    parser.add_argument("--workspace-root", default=str(Path.home() / "Documents" / "devel"))
    parser.add_argument("--folder-prefix", default="stephanos-claude")
    parser.add_argument("--include-partial", action="store_true", help="Import translated files even if the folder is not 100%% complete.")
    parser.add_argument("--update-existing", action="store_true", help="Update already imported runs when the file translation changed.")
    parser.add_argument("--public-eligible", action="store_true", help="Allow imported Claude runs to be considered for public translation selection.")
    parser.add_argument("--public-block-reason", default=DEFAULT_PUBLIC_BLOCK_REASON)
    parser.add_argument("--created-by", default=SCRIPT_NAME)
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--no-guidance-provenance", action="store_true", help="Do not record translation_run_guidance_matches for guidance-enabled prompt versions.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        workspaces = discover_workspaces(args)
    except ValueError as exc:
        parser.error(str(exc))

    if not workspaces:
        raise RuntimeError("No matching Claude workspace folders found.")

    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    required_tables = [
        "translation_run_requests",
        "translation_runs",
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "assembled_lemmas",
        "lemma_source_text_versions",
        "human_translations",
        "kappa_review_imports",
        "kappa_review_rows",
    ]
    missing = [table for table in required_tables if not table_exists(cur, table)]
    if missing:
        raise RuntimeError(f"Missing required table(s): {', '.join(missing)}")
    corpus_by_source_row = load_paper_corpus(cur)

    totals = {
        "folders_seen": 0,
        "folders_imported": 0,
        "folders_skipped_incomplete": 0,
        "files_seen": 0,
        "translated_files_seen": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_existing": 0,
        "conflicts": 0,
        "guidance_links": 0,
    }

    for workspace in workspaces:
        totals["folders_seen"] += 1
        complete = workspace.total_files > 0 and workspace.total_files == workspace.translated_files
        if not complete and not args.include_partial:
            totals["folders_skipped_incomplete"] += 1
            print(
                f"Skipping {workspace.folder.name}: "
                f"{workspace.translated_files}/{workspace.total_files} translated; use --include-partial to import partial folders."
            )
            continue
        profile = load_profile_version(cur, workspace)
        totals["folders_imported"] += 1
        print(f"{'Scanning' if args.dry_run else 'Importing'} {workspace.folder.name}: {workspace.translated_files}/{workspace.total_files}")
        for path in workspace_entry_paths(workspace.folder):
            totals["files_seen"] += 1
            entry = read_entry_file(path)
            if not entry.translation_text:
                continue
            totals["translated_files_seen"] += 1
            validate_entry(entry, workspace=workspace, profile=profile, corpus_by_source_row=corpus_by_source_row)
            external_file = str(path.resolve())
            payload = import_payload(entry=entry, workspace=workspace, profile=profile, created_by=args.created_by)
            existing = existing_import(cur, external_file=external_file, profile_version_id=int(profile["profile_version_id"]))
            public_eligible = bool(args.public_eligible)
            public_block_reason = (args.public_block_reason or "").strip() or DEFAULT_PUBLIC_BLOCK_REASON
            model = str(profile["default_model"] or workspace.default_model)
            if existing:
                if existing["translation_text"].strip() == entry.translation_text.strip():
                    totals["skipped_existing"] += 1
                    continue
                if not args.update_existing:
                    totals["conflicts"] += 1
                    print(f"Conflict: {path} changed after prior import; rerun with --update-existing to update run {existing['run_id']}.")
                    continue
                if not args.dry_run:
                    run_id = update_run(
                        cur,
                        existing=existing,
                        entry=entry,
                        model=model,
                        payload=payload,
                        public_eligible=public_eligible,
                        public_block_reason=public_block_reason,
                    )
                    if bool(profile["uses_guidance_context"]) and not args.no_guidance_provenance:
                        totals["guidance_links"] += record_guidance(cur, run_id=run_id, entry=entry)
                totals["updated"] += 1
                continue
            if not args.dry_run:
                request_id = insert_request(
                    cur,
                    entry=entry,
                    profile=profile,
                    model=model,
                    created_by=args.created_by,
                    priority=args.priority,
                )
                run_id = insert_run(
                    cur,
                    request_id=request_id,
                    entry=entry,
                    profile=profile,
                    model=model,
                    payload=payload,
                    public_eligible=public_eligible,
                    public_block_reason=public_block_reason,
                )
                if bool(profile["uses_guidance_context"]) and not args.no_guidance_provenance:
                    totals["guidance_links"] += record_guidance(cur, run_id=run_id, entry=entry)
            totals["inserted"] += 1

    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    print(json.dumps(totals, indent=2, sort_keys=True))
    if args.dry_run:
        print("Dry run; no database rows were written.")


if __name__ == "__main__":
    main()
