#!/usr/bin/env python3
"""Export external Claude workspaces for the 100-row Kappa paper corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from claude_variant_config import (
    parse_model_variants,
    parse_prompt_versions,
)
from paper_corpus import (
    DEFAULT_PAPER_CORPUS,
    corpus_label,
    normalize_corpus,
    paper_kappa_review_cte_body,
)
from source_documents import (
    PREFERRED_GREEK_SOURCE_DOCUMENTS,
    PREFERRED_SOURCE_DOCUMENT,
    normalize_source_document,
    public_source_document_list_sql,
    source_document_priority_sql,
)


def load_translation_guidance_helpers():
    from translate_lemmas import fetch_guidance_context, format_context_sections

    return fetch_guidance_context, format_context_sections


def row_to_dict(cur, row) -> dict[str, object]:
    return {desc[0]: value for desc, value in zip(cur.description, row)}


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


def source_lateral_sql(source_document: str) -> tuple[str, list[object]]:
    source_document = normalize_source_document(source_document)
    if source_document == PREFERRED_SOURCE_DOCUMENT:
        return (
            f"""
            JOIN LATERAL (
                SELECT stv.id, stv.source_document, stv.text_body
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = a.id
                  AND stv.source_document IN ({public_source_document_list_sql()})
                  AND stv.is_current = TRUE
                  AND COALESCE(stv.text_body, '') <> ''
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            """,
            [],
        )
    return (
        """
        JOIN LATERAL (
            SELECT stv.id, stv.source_document, stv.text_body
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = a.id
              AND stv.source_document = %s
              AND stv.is_current = TRUE
              AND COALESCE(stv.text_body, '') <> ''
            ORDER BY stv.id DESC
            LIMIT 1
        ) stv ON TRUE
        """,
        [source_document],
    )


def fetch_profile_version(cur, *, profile_name: str, version: int) -> dict[str, object]:
    uses_guidance_select = (
        "COALESCE(pv.uses_guidance_context, FALSE)"
        if column_exists(cur, "translation_prompt_profile_versions", "uses_guidance_context")
        else "FALSE"
    )
    model_select = (
        "COALESCE(NULLIF(pv.default_model, ''), '')"
        if column_exists(cur, "translation_prompt_profile_versions", "default_model")
        else "''"
    )
    cur.execute(
        f"""
        SELECT
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version,
            pv.prompt_text,
            COALESCE(pv.notes, '') AS notes,
            {uses_guidance_select} AS uses_guidance_context,
            {model_select} AS default_model
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.name = %s
          AND pv.version = %s
          AND p.active = TRUE
          AND COALESCE(pv.active, TRUE) = TRUE
        LIMIT 1
        """,
        (profile_name, int(version)),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(
            f"Missing active profile/version {profile_name} v{version}; "
            "run seed_claude_translation_profiles.py first."
        )
    return row_to_dict(cur, row)


def fetch_paper_entries(cur, *, corpus: str, source_document: str) -> list[dict[str, object]]:
    corpus = normalize_corpus(corpus)
    if corpus != DEFAULT_PAPER_CORPUS:
        raise ValueError("Only paper_kappa_review is currently supported for Claude workspace export.")
    source_join, params = source_lateral_sql(source_document)
    cur.execute(
        f"""
        WITH {paper_kappa_review_cte_body("paper_corpus")}
        SELECT
            pc.corpus_order,
            pc.corpus_source_row_id,
            pc.kappa_review_row_id,
            pc.human_translation_id,
            a.id AS lemma_id,
            a.lemma,
            a.entry_number,
            a.version AS lemma_version,
            stv.id AS source_text_version_id,
            stv.source_document,
            stv.text_body AS source_text
        FROM paper_corpus pc
        JOIN assembled_lemmas a ON a.id = pc.lemma_id
        {source_join}
        ORDER BY pc.corpus_order
        """,
        params,
    )
    return [row_to_dict(cur, row) for row in cur.fetchall()]


def slugify_ascii(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "entry"


def entry_filename(row: dict[str, object]) -> str:
    order = int(row["corpus_order"])
    entry_number = int(row["entry_number"] or row["corpus_source_row_id"] or 0)
    lemma_id = int(row["lemma_id"])
    return f"{order:03d}-entry-{entry_number:04d}-lemma-{lemma_id}.md"


def frontmatter(metadata: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = '""'
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines)


def render_claude_md(
    *,
    display_name: str,
    profile_version: dict[str, object],
    corpus: str,
    entry_count: int,
    source_document: str,
) -> str:
    guidance_note = (
        "Entry files include a recognizer-guidance section when matched guidance rows are available."
        if bool(profile_version["uses_guidance_context"])
        else "Entry files intentionally do not include recognizer-guidance sections for this prompt variant."
    )
    return f"""# {display_name} / Prompt v{profile_version['version']}

This is an external Stephanos translation workspace generated from the local
PostgreSQL database. Keep Claude's edits and outputs in this directory, outside
the Stephanos repository.

Corpus: {corpus_label(corpus)}
Entries: {entry_count}
Source document selection: {source_document}
Database profile: `{profile_version['profile_name']}` v{profile_version['version']}
Profile version id: `{profile_version['profile_version_id']}`

Use the prompt below as the governing translation instruction. Each numbered
entry file contains one Greek source text to translate. Do not use any approved
human translation as input; those are intentionally not included in these files.
{guidance_note}

## Prompt

{profile_version['prompt_text'].strip()}
"""


def render_entry_file(
    *,
    row: dict[str, object],
    profile_version: dict[str, object],
    display_name: str,
    guidance_context: list[dict[str, object]],
    format_context_sections_func,
) -> str:
    metadata = {
        "corpus_order": int(row["corpus_order"]),
        "corpus_source_row_id": int(row["corpus_source_row_id"]),
        "kappa_review_row_id": int(row["kappa_review_row_id"]),
        "lemma_id": int(row["lemma_id"]),
        "human_translation_id": int(row["human_translation_id"]),
        "headword": row["lemma"],
        "entry_number": int(row["entry_number"] or 0),
        "source_text_version_id": int(row["source_text_version_id"]),
        "source_document": row["source_document"],
        "profile_name": profile_version["profile_name"],
        "profile_version_id": int(profile_version["profile_version_id"]),
        "prompt_version": int(profile_version["version"]),
        "claude_variant": display_name,
        "uses_guidance_context": bool(profile_version["uses_guidance_context"]),
        "guidance_match_count": len(guidance_context),
    }
    guidance_text = ""
    if bool(profile_version["uses_guidance_context"]):
        formatted = format_context_sections_func(guidance_context, [])
        guidance_text = formatted or "No matched recognizer guidance rows were available for this entry."

    guidance_section = ""
    if bool(profile_version["uses_guidance_context"]):
        guidance_section = f"""
## Recognizer Guidance

{guidance_text}
"""

    return f"""{frontmatter(metadata)}

# {int(row['corpus_order']):03d}. {row['lemma']}

Translate this Stephanos entry according to `CLAUDE.md`.

## Source Metadata

- Headword: {row['lemma']}
- Entry number: {row['entry_number'] or 0}
- Lemma ID: {row['lemma_id']}
- Source text version ID: {row['source_text_version_id']}
- Source document: {row['source_document']}

## Greek Source Text

{str(row['source_text']).strip()}
{guidance_section}
## Claude Translation

"""


def write_workspace(
    *,
    folder: Path,
    display_name: str,
    profile_version: dict[str, object],
    entries: list[dict[str, object]],
    source_document: str,
    format_context_sections_func,
    force: bool,
    dry_run: bool,
) -> dict[str, int]:
    entry_count = 0
    guidance_entry_count = 0
    if dry_run:
        return {
            "entry_files": len(entries),
            "guidance_entry_files": sum(1 for row in entries if row.get("_guidance_context")),
        }

    if folder.exists() and any(folder.iterdir()) and not force:
        raise RuntimeError(f"Target folder already exists and is non-empty: {folder}. Use --force to overwrite.")

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CLAUDE.md").write_text(
        render_claude_md(
            display_name=display_name,
            profile_version=profile_version,
            corpus=DEFAULT_PAPER_CORPUS,
            entry_count=len(entries),
            source_document=source_document,
        ),
        encoding="utf-8",
    )

    manifest_path = folder / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for row in entries:
            guidance_context = row.get("_guidance_context") or []
            if guidance_context:
                guidance_entry_count += 1
            filename = entry_filename(row)
            (folder / filename).write_text(
                render_entry_file(
                    row=row,
                    profile_version=profile_version,
                    display_name=display_name,
                    guidance_context=guidance_context,
                    format_context_sections_func=format_context_sections_func,
                ),
                encoding="utf-8",
            )
            entry_count += 1
            manifest.write(
                json.dumps(
                    {
                        "filename": filename,
                        "corpus_order": int(row["corpus_order"]),
                        "corpus_source_row_id": int(row["corpus_source_row_id"]),
                        "kappa_review_row_id": int(row["kappa_review_row_id"]),
                        "lemma_id": int(row["lemma_id"]),
                        "human_translation_id": int(row["human_translation_id"]),
                        "source_text_version_id": int(row["source_text_version_id"]),
                        "source_document": row["source_document"],
                        "headword": row["lemma"],
                        "profile_name": profile_version["profile_name"],
                        "profile_version_id": int(profile_version["profile_version_id"]),
                        "prompt_version": int(profile_version["version"]),
                        "uses_guidance_context": bool(profile_version["uses_guidance_context"]),
                        "guidance_match_count": len(guidance_context),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    (folder / "EXPORT_METADATA.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "variant": display_name,
                "profile_name": profile_version["profile_name"],
                "profile_version_id": int(profile_version["profile_version_id"]),
                "prompt_version": int(profile_version["version"]),
                "entry_count": entry_count,
                "guidance_entry_count": guidance_entry_count,
                "source_document": source_document,
                "corpus": DEFAULT_PAPER_CORPUS,
                "corpus_label": corpus_label(DEFAULT_PAPER_CORPUS),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {"entry_files": entry_count, "guidance_entry_files": guidance_entry_count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="all", help="Comma/space model list: sonnet-5, opus-4-8, fable-5, or all.")
    parser.add_argument("--versions", default="1,2,3", help="Comma/space prompt versions to export.")
    parser.add_argument("--output-root", default=str(Path.home() / "Documents" / "devel"))
    parser.add_argument("--folder-prefix", default="stephanos-claude")
    parser.add_argument(
        "--source-document",
        default=PREFERRED_SOURCE_DOCUMENT,
        choices=(PREFERRED_SOURCE_DOCUMENT, *PREFERRED_GREEK_SOURCE_DOCUMENTS),
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing non-empty target folders.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        model_variants = parse_model_variants(args.models)
        versions = parse_prompt_versions(args.versions)
    except ValueError as exc:
        parser.error(str(exc))

    output_root = Path(args.output_root).expanduser()
    from db import get_connection

    fetch_guidance_context_func, format_context_sections_func = load_translation_guidance_helpers()

    conn = get_connection()
    cur = conn.cursor()
    for table_name in (
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "assembled_lemmas",
        "human_translations",
        "lemma_source_text_versions",
        "kappa_review_imports",
        "kappa_review_rows",
    ):
        if not table_exists(cur, table_name):
            raise RuntimeError(f"Missing required table: {table_name}")

    base_entries = fetch_paper_entries(cur, corpus=DEFAULT_PAPER_CORPUS, source_document=args.source_document)
    if len(base_entries) != 100:
        raise RuntimeError(f"Expected 100 paper-corpus entries, found {len(base_entries)}")

    total_entry_files = 0
    for variant in model_variants:
        for version in versions:
            profile_version = fetch_profile_version(cur, profile_name=variant.db_profile_name, version=version)
            entries: list[dict[str, Any]] = []
            for row in base_entries:
                item = dict(row)
                guidance_context: list[dict[str, object]] = []
                if bool(profile_version["uses_guidance_context"]):
                    guidance_context = fetch_guidance_context_func(
                        cur,
                        lemma_id=int(item["lemma_id"]),
                        source_text_version_id=int(item["source_text_version_id"]),
                    )
                item["_guidance_context"] = guidance_context
                entries.append(item)
            folder = output_root / f"{args.folder_prefix}-{variant.slug}-v{version}"
            stats = write_workspace(
                folder=folder,
                display_name=variant.display_name,
                profile_version=profile_version,
                entries=entries,
                source_document=args.source_document,
                format_context_sections_func=format_context_sections_func,
                force=args.force,
                dry_run=args.dry_run,
            )
            total_entry_files += stats["entry_files"]
            print(
                f"{'Would write' if args.dry_run else 'Wrote'} {folder}: "
                f"{stats['entry_files']} entry files, "
                f"{stats['guidance_entry_files']} with guidance"
            )

    conn.close()
    print(f"{'Would export' if args.dry_run else 'Exported'} {total_entry_files} entry files.")


if __name__ == "__main__":
    main()
