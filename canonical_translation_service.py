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


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def require_tables(cur):
    missing = []
    for table_name in (
        "assembled_lemmas",
        "lemma_publication_targets",
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


def fetch_current_pointer(cur, lemma_id: int) -> dict | None:
    cur.execute(
        """
        SELECT variant_kind, variant_id
        FROM lemma_publication_targets
        WHERE lemma_id = %s
          AND surface = 'public_translation'
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"kind": row[0], "id": str(row[1])}


def legacy_block_status(cur, lemma_id: int) -> tuple[bool, str]:
    if not table_exists(cur, "translation_risk_flags"):
        return False, ""
    cur.execute(
        """
        SELECT COALESCE(is_blocked, FALSE),
               COALESCE(details_json->>'summary', '')
        FROM translation_risk_flags
        WHERE lemma_id = %s
          AND variant_kind = 'legacy_assembled'
          AND variant_id = 'translation'
          AND risk_code = 'billerbeck_likely_translation_change'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return False, ""
    return bool(row[0]), (row[1] or "").strip()


def resolve_variant(cur, lemma_id: int, variant_kind: str, variant_id: str) -> dict:
    variant_kind = (variant_kind or "").strip()
    variant_id = str(variant_id or "").strip()

    if variant_kind == "translation_run":
        if not table_exists(cur, "translation_runs"):
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "translation_runs table missing",
            }
        cur.execute(
            """
            SELECT id,
                   COALESCE(translation_text, ''),
                   COALESCE(status, ''),
                   COALESCE(public_eligible, TRUE),
                   COALESCE(public_block_reason, ''),
                   source_text_version_id
            FROM translation_runs
            WHERE id = %s
              AND lemma_id = %s
            LIMIT 1
            """,
            (variant_id, lemma_id),
        )
        row = cur.fetchone()
        if not row:
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "translation run not found for lemma",
            }
        translation_text, status, public_eligible, public_block_reason = row[1], row[2], bool(row[3]), (row[4] or "").strip()
        publishable = (
            status == "approved"
            and public_eligible
            and not public_block_reason
            and bool((translation_text or "").strip())
        )
        block_reason = ""
        if not publishable:
            if status != "approved":
                block_reason = f"translation_run status is {status or 'unknown'}"
            elif not public_eligible:
                block_reason = "translation_run is not public_eligible"
            elif public_block_reason:
                block_reason = public_block_reason
            else:
                block_reason = "translation_run has empty translation_text"
        return {
            "exists": True,
            "publishable": publishable,
            "block_reason": block_reason,
            "translation_text": (translation_text or "").strip(),
            "status": status,
            "source_document": "billerbeck",
            "source_text_version_id": str(row[5] or ""),
            "kind": variant_kind,
            "id": variant_id,
        }

    if variant_kind == "human_translation":
        if not table_exists(cur, "human_translations"):
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "human_translations table missing",
            }
        cur.execute(
            """
            SELECT id,
                   COALESCE(translation_text, ''),
                   COALESCE(status, ''),
                   source_text_version_id
            FROM human_translations
            WHERE id = %s
              AND lemma_id = %s
            LIMIT 1
            """,
            (variant_id, lemma_id),
        )
        row = cur.fetchone()
        if not row:
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "human translation not found for lemma",
            }
        translation_text, status = row[1], row[2]
        publishable = status == "approved" and bool((translation_text or "").strip())
        block_reason = ""
        if not publishable:
            if status != "approved":
                block_reason = f"human_translation status is {status or 'unknown'}"
            else:
                block_reason = "human_translation has empty translation_text"
        return {
            "exists": True,
            "publishable": publishable,
            "block_reason": block_reason,
            "translation_text": (translation_text or "").strip(),
            "status": status,
            "source_document": "billerbeck",
            "source_text_version_id": str(row[3] or ""),
            "kind": variant_kind,
            "id": variant_id,
        }

    if variant_kind == "legacy_assembled":
        if variant_id not in ("translation", str(lemma_id), ""):
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "legacy_assembled variant_id must be 'translation' (or lemma id)",
            }
        cur.execute(
            """
            SELECT COALESCE(translation, ''),
                   COALESCE(corrected_english_translation, ''),
                   COALESCE(reviewed_english_translation, '')
            FROM assembled_lemmas
            WHERE id = %s
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if not row:
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "assembled lemma not found",
            }
        translation_text = (row[2] or row[1] or row[0] or "").strip()
        is_blocked, block_reason = legacy_block_status(cur, lemma_id)
        publishable = bool(translation_text) and not is_blocked
        if not block_reason and is_blocked:
            block_reason = "Legacy translation blocked by risk gating"
        if not block_reason and not translation_text:
            block_reason = "Legacy translation is empty"
        return {
            "exists": True,
            "publishable": publishable,
            "block_reason": block_reason,
            "translation_text": translation_text,
            "status": "approved" if publishable else "blocked",
            "source_document": "billerbeck",
            "source_text_version_id": "",
            "kind": "legacy_assembled",
            "id": "translation",
        }

    return {
        "exists": False,
        "publishable": False,
        "block_reason": f"unsupported variant_kind: {variant_kind}",
    }


def resolve_fallback_variant(cur, lemma_id: int) -> dict | None:
    best: dict | None = None

    if table_exists(cur, "human_translations"):
        cur.execute(
            """
            SELECT id::text,
                   COALESCE(translation_text, ''),
                   updated_at,
                   source_text_version_id
            FROM human_translations
            WHERE lemma_id = %s
              AND status = 'approved'
              AND COALESCE(translation_text, '') != ''
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if row:
            best = {
                "kind": "human_translation",
                "id": row[0],
                "translation_text": (row[1] or "").strip(),
                "status": "approved",
                "source_document": "billerbeck",
                "source_text_version_id": str(row[3] or ""),
                "sort_ts": row[2],
            }

    if table_exists(cur, "translation_runs"):
        cur.execute(
            """
            SELECT id::text,
                   COALESCE(translation_text, ''),
                   COALESCE(reviewed_at, completed_at, created_at) AS sort_ts,
                   source_text_version_id
            FROM translation_runs
            WHERE lemma_id = %s
              AND status = 'approved'
              AND public_eligible = TRUE
              AND COALESCE(public_block_reason, '') = ''
              AND COALESCE(translation_text, '') != ''
            ORDER BY COALESCE(reviewed_at, completed_at, created_at) DESC, id DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if row:
            run_choice = {
                "kind": "translation_run",
                "id": row[0],
                "translation_text": (row[1] or "").strip(),
                "status": "approved",
                "source_document": "billerbeck",
                "source_text_version_id": str(row[3] or ""),
                "sort_ts": row[2],
            }
            if best is None:
                best = run_choice
            else:
                best_ts = best.get("sort_ts")
                run_ts = run_choice.get("sort_ts")
                if run_ts is not None and (best_ts is None or run_ts > best_ts):
                    best = run_choice

    legacy_choice = resolve_variant(cur, lemma_id, "legacy_assembled", "translation")
    if legacy_choice.get("publishable"):
        if best is None:
            best = {
                "kind": legacy_choice["kind"],
                "id": legacy_choice["id"],
                "translation_text": legacy_choice["translation_text"],
                "status": legacy_choice.get("status", ""),
                "source_document": legacy_choice.get("source_document", ""),
                "source_text_version_id": legacy_choice.get("source_text_version_id", ""),
                "sort_ts": None,
            }

    if not best:
        return None
    best.pop("sort_ts", None)
    return best


def resolve_canonical(cur, lemma_id: int, lemma_text: str) -> dict:
    pointer = fetch_current_pointer(cur, lemma_id)

    selected = None
    blocked = False
    block_reason = ""
    notes: list[str] = []

    if pointer:
        pointer_variant = resolve_variant(cur, lemma_id, pointer["kind"], pointer["id"])
        if pointer_variant.get("publishable"):
            selected = {
                "kind": pointer_variant["kind"],
                "id": pointer_variant["id"],
                "translation_text": pointer_variant["translation_text"],
                "status": pointer_variant.get("status", ""),
                "source_document": pointer_variant.get("source_document", ""),
                "source_text_version_id": pointer_variant.get("source_text_version_id", ""),
            }
        else:
            blocked = True
            block_reason = pointer_variant.get("block_reason", "") or "Canonical pointer is not publishable"
            notes.append("Canonical pointer is not publishable; using fallback selection")

    if selected is None:
        fallback = resolve_fallback_variant(cur, lemma_id)
        if fallback:
            selected = fallback
            blocked = False
            block_reason = ""
        elif not blocked:
            blocked = True
            block_reason = "No publishable translation variant found"

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
        "translation_blocked": bool(blocked or not selected),
        "translation_block_reason": block_reason,
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
            WHEN 'billerbeck' THEN 0
            WHEN 'meineke' THEN 1
            ELSE 2
          END,
          id DESC
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def upsert_pointer(cur, lemma_id: int, variant_kind: str, variant_id: str, updated_by: str):
    cur.execute(
        """
        INSERT INTO lemma_publication_targets (
            lemma_id, surface, variant_kind, variant_id, updated_by, updated_at
        )
        VALUES (%s, 'public_translation', %s, %s, %s, NOW())
        ON CONFLICT (lemma_id, surface) DO UPDATE SET
            variant_kind = EXCLUDED.variant_kind,
            variant_id = EXCLUDED.variant_id,
            updated_by = EXCLUDED.updated_by,
            updated_at = EXCLUDED.updated_at
        """,
        (lemma_id, variant_kind, str(variant_id), updated_by),
    )


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

    upsert_pointer(cur, lemma_id, variant_kind, variant_id, args.updated_by)

    selected_variant = {
        "kind": candidate["kind"],
        "id": candidate["id"],
        "translation_text": candidate["translation_text"],
        "status": candidate.get("status", ""),
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
