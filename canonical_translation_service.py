#!/usr/bin/env python3
"""
Resolve and set canonical public translations for lemmas.

Usage:
  uv run canonical_translation_service.py get --lemma-id 123 --json
  uv run canonical_translation_service.py set --lemma-id 123 --variant-kind human_translation --variant-id 456 --json
  uv run canonical_translation_service.py set --headword "Καδμεία" --translation-text "..." --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from db import get_connection
import canonical_variants


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def require_tables(cur):
    missing = []
    for table_name in (
        "assembled_lemmas",
        "lemma_canonical_variants",
    ):
        if not table_exists(cur, table_name):
            missing.append(table_name)
    if missing:
        raise RuntimeError(f"Missing required tables: {', '.join(missing)}")


def resolve_lemma(cur, lemma_id: int | None, headword: str | None) -> tuple[int, str]:
    if lemma_id is not None:
        cur.execute(
            """
            SELECT id, COALESCE(lemma, '')
            FROM assembled_lemmas
            WHERE id = %s
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Lemma id {lemma_id} not found")
        return int(row[0]), row[1] or ""

    if not headword:
        raise RuntimeError("Provide --lemma-id or --headword")

    cur.execute(
        """
        SELECT id, COALESCE(lemma, '')
        FROM assembled_lemmas
        WHERE lemma = %s
        ORDER BY CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        (headword,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Headword not found: {headword}")
    return int(row[0]), row[1] or ""


def fetch_primary_membership(cur, lemma_id: int) -> dict | None:
    if not table_exists(cur, "lemma_canonical_variants"):
        return None
    cur.execute(
        """
        SELECT variant_kind, variant_id
        FROM lemma_canonical_variants
        WHERE lemma_id = %s
          AND is_active = TRUE
          AND is_primary = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"kind": row[0], "id": str(row[1])}

def resolve_variant(cur, lemma_id: int, variant_kind: str, variant_id: str) -> dict:
    return canonical_variants.resolve_variant(
        cur, lemma_id=lemma_id, variant_kind=variant_kind, variant_id=variant_id
    )


def resolve_fallback_variant(cur, lemma_id: int) -> dict | None:
    return canonical_variants.resolve_fallback_variant(cur, lemma_id=lemma_id)


def resolve_canonical(cur, lemma_id: int, lemma_text: str) -> dict:
    pointer = fetch_primary_membership(cur, lemma_id)

    notes: list[str] = []

    selected = canonical_variants.select_pointer_variant(cur, lemma_id=lemma_id)
    if pointer:
        pointer_variant = resolve_variant(cur, lemma_id, pointer["kind"], pointer["id"])
        if not pointer_variant.get("publishable") and selected is not None:
            notes.append("Canonical pointer is not publishable; using fallback selection")

    return {
        "lemma_id": lemma_id,
        "lemma": lemma_text,
        "canonical_pointer": pointer or {},
        "selected_variant": {
            "kind": selected.get("kind", "") if selected else "",
            "id": selected.get("id", "") if selected else "",
            "status": selected.get("status", "") if selected else "",
            "source_document": selected.get("source_document", "") if selected else "",
            "source_text_version_id": selected.get("source_text_version_id", "") if selected else "",
        },
        "translation_text": selected.get("translation_text", "") if selected else "",
        "translation_blocked": bool(not selected),
        "translation_block_reason": "No publishable translation variant found" if not selected else "",
        "notes": notes,
    }


def choose_default_source_text_version(cur, lemma_id: int) -> int | None:
    if not table_exists(cur, "lemma_source_text_versions"):
        return None
    cur.execute(
        """
        SELECT id
        FROM lemma_source_text_versions
        WHERE lemma_id = %s
          AND is_current = TRUE
        ORDER BY
          CASE source_document
            WHEN 'meineke' THEN 0
            WHEN 'billerbeck' THEN 1
            ELSE 2
          END,
          id DESC
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def refresh_legacy_cache(cur, lemma_id: int, selected_variant: dict):
    selected_text = (selected_variant.get("translation_text") or "").strip()
    if not selected_text:
        return

    kind = selected_variant.get("kind", "")
    status = selected_variant.get("status", "")

    corrected_value = selected_text if kind == "human_translation" else None
    reviewed_value = selected_text if (kind == "human_translation" and status == "approved") else None

    cur.execute(
        """
        UPDATE assembled_lemmas
        SET translation = %s,
            corrected_english_translation = COALESCE(%s, corrected_english_translation),
            reviewed_english_translation = COALESCE(%s, reviewed_english_translation),
            translated = 1,
            translated_at = COALESCE(translated_at, NOW()),
            updated_at = NOW()
        WHERE id = %s
        """,
        (selected_text, corrected_value, reviewed_value, lemma_id),
    )


def create_human_translation_variant(
    cur,
    *,
    lemma_id: int,
    translation_text: str,
    updated_by: str,
    source_text_version_id: int | None,
    notes: str,
) -> tuple[str, str]:
    if not table_exists(cur, "human_translations"):
        raise RuntimeError("human_translations table is required to create text-based canonical variant")
    if source_text_version_id is None:
        source_text_version_id = choose_default_source_text_version(cur, lemma_id)

    cur.execute(
        """
        INSERT INTO human_translations (
            lemma_id,
            source_text_version_id,
            stage,
            status,
            translation_text,
            created_by,
            updated_by,
            reviewed_by,
            reviewed_at,
            created_at,
            updated_at,
            notes
        )
        VALUES (
            %s, %s, 'final', 'approved', %s, %s, %s, %s, NOW(), NOW(), NOW(), %s
        )
        RETURNING id
        """,
        (
            lemma_id,
            source_text_version_id,
            translation_text.strip(),
            updated_by,
            updated_by,
            updated_by,
            notes or "Created via canonical translation endpoint",
        ),
    )
    row = cur.fetchone()
    return "human_translation", str(row[0])


def command_get(cur, args) -> dict:
    lemma_id, lemma_text = resolve_lemma(cur, args.lemma_id, args.headword)
    return resolve_canonical(cur, lemma_id, lemma_text)


def command_set(cur, args) -> dict:
    lemma_id, lemma_text = resolve_lemma(cur, args.lemma_id, args.headword)

    variant_kind = (args.variant_kind or "").strip()
    variant_id = (args.variant_id or "").strip()

    if args.translation_text:
        variant_kind, variant_id = create_human_translation_variant(
            cur,
            lemma_id=lemma_id,
            translation_text=args.translation_text,
            updated_by=args.updated_by,
            source_text_version_id=args.source_text_version_id,
            notes=args.notes,
        )
    elif not variant_kind or not variant_id:
        raise RuntimeError("Provide --variant-kind and --variant-id, or --translation-text")

    candidate = resolve_variant(cur, lemma_id, variant_kind, variant_id)
    if not candidate.get("exists"):
        raise RuntimeError(candidate.get("block_reason", "Variant not found"))
    if not candidate.get("publishable"):
        raise RuntimeError(candidate.get("block_reason", "Variant is not publishable"))

    if not table_exists(cur, "lemma_canonical_variants"):
        raise RuntimeError("lemma_canonical_variants table is required to set canonical variants")

    # Ensure membership is active, set primary, clear other primaries.
    cur.execute(
        """
        INSERT INTO lemma_canonical_variants (
            lemma_id, variant_kind, variant_id, is_active, is_primary, updated_by, updated_at
        )
        VALUES (%s, %s, %s, TRUE, TRUE, %s, NOW())
        ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
            is_active = TRUE,
            is_primary = TRUE,
            updated_by = EXCLUDED.updated_by,
            updated_at = EXCLUDED.updated_at
        """,
        (lemma_id, variant_kind, str(variant_id), args.updated_by),
    )
    cur.execute(
        """
        UPDATE lemma_canonical_variants
        SET is_primary = FALSE,
            updated_by = %s,
            updated_at = NOW()
        WHERE lemma_id = %s
          AND is_primary = TRUE
          AND NOT (variant_kind = %s AND variant_id = %s)
        """,
        (args.updated_by, lemma_id, variant_kind, str(variant_id)),
    )

    pointer_choice = canonical_variants.select_pointer_variant(cur, lemma_id=lemma_id)
    selected_variant = {
        "kind": (pointer_choice["kind"] if pointer_choice else candidate["kind"]),
        "id": (pointer_choice["id"] if pointer_choice else candidate["id"]),
        "translation_text": (pointer_choice["translation_text"] if pointer_choice else candidate["translation_text"]),
        "status": (pointer_choice["status"] if pointer_choice else candidate.get("status", "")),
    }
    refresh_legacy_cache(cur, lemma_id, selected_variant)

    result = resolve_canonical(cur, lemma_id, lemma_text)
    result["set_pointer"] = {"kind": variant_kind, "id": str(variant_id)}
    result["updated_by"] = args.updated_by
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve and set canonical translation variants.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_get = subparsers.add_parser("get", help="Get canonical translation for a lemma")
    parser_get.add_argument("--lemma-id", type=int)
    parser_get.add_argument("--headword")
    parser_get.add_argument("--json", action="store_true")

    parser_set = subparsers.add_parser("set", help="Set canonical translation variant")
    parser_set.add_argument("--lemma-id", type=int)
    parser_set.add_argument("--headword")
    parser_set.add_argument("--variant-kind")
    parser_set.add_argument("--variant-id")
    parser_set.add_argument("--translation-text")
    parser_set.add_argument("--source-text-version-id", type=int)
    parser_set.add_argument("--updated-by", default="canonical_translation_service.py")
    parser_set.add_argument("--notes", default="")
    parser_set.add_argument("--json", action="store_true")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    # Keep imports/config resolution deterministic when invoked remotely.
    # (db.py imports config.py from project dir)
    import os
    os.chdir(project_dir)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        require_tables(cur)

        if args.command == "get":
            result = command_get(cur, args)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            conn.close()
            return

        if args.command == "set":
            result = command_set(cur, args)
            conn.commit()
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            conn.close()
            return

        raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        if conn is not None:
            conn.rollback()
            conn.close()
        error_payload = {"error": f"{type(exc).__name__}: {exc}"}
        if getattr(args, "json", False):
            print(json.dumps(error_payload, ensure_ascii=False))
        else:
            raise
        raise SystemExit(1)


if __name__ == "__main__":
    main()
