#!/usr/bin/env python3
"""
Queue translation run requests for the new parallel translation pipeline.
"""
import argparse
import random
import re
import unicodedata

from db import get_connection
from source_documents import (
    PREFERRED_GREEK_SOURCE_DOCUMENTS,
    PREFERRED_SOURCE_DOCUMENT,
    normalize_source_document,
    public_source_document_list_sql,
    source_document_priority_sql,
)
from translation_guidance_coverage import (
    enqueue_missing_guidance,
    guidance_coverage_counts,
)


GREEK_LETTER_BASES = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "omicron": "ο",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
}

LATIN_INITIAL_TO_GREEK = {
    "a": "α",
    "b": "β",
    "g": "γ",
    "d": "δ",
    "e": "ε",
    "z": "ζ",
    "h": "η",
    "i": "ι",
    "k": "κ",
    "l": "λ",
    "m": "μ",
    "n": "ν",
    "x": "ξ",
    "o": "ο",
    "p": "π",
    "r": "ρ",
    "s": "σ",
    "t": "τ",
    "u": "υ",
    "f": "φ",
    "c": "χ",
    "y": "ψ",
    "w": "ω",
}


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalise_headword_key(text: str) -> str:
    return strip_diacritics(text).casefold().replace("ς", "σ").strip()


def normalise_letter_filter(letter: str | None) -> str | None:
    if not letter:
        return None
    raw = letter.strip()
    if not raw:
        return None
    key = raw.casefold().replace("-", "_")
    if key in GREEK_LETTER_BASES:
        return GREEK_LETTER_BASES[key]
    if key in LATIN_INITIAL_TO_GREEK:
        return LATIN_INITIAL_TO_GREEK[key]
    normalised = normalise_headword_key(raw)
    if len(normalised) == 1:
        return normalised
    raise ValueError(f"Unknown Greek letter filter: {letter}")


def normalise_prefix(prefix: str | None) -> str | None:
    if not prefix:
        return None
    raw = prefix.strip()
    if not raw:
        return None
    key = raw.casefold().replace("-", "_")
    if key in GREEK_LETTER_BASES:
        return GREEK_LETTER_BASES[key]
    if key in LATIN_INITIAL_TO_GREEK:
        return LATIN_INITIAL_TO_GREEK[key]
    return normalise_headword_key(raw)


def parse_lemma_ids(value: str | None) -> list[int]:
    if not value:
        return []
    pieces = [piece for piece in re.split(r"[\s,]+", value.strip()) if piece]
    ids: list[int] = []
    for piece in pieces:
        try:
            ids.append(int(piece))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid lemma id: {piece}") from exc
    return ids


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


def resolve_profile(cur, profile_name: str):
    cur.execute(
        "SELECT id FROM translation_prompt_profiles WHERE name = %s AND active = TRUE LIMIT 1",
        (profile_name,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Unknown active prompt profile: {profile_name}")
    return row[0]


def resolve_profile_version(cur, profile_id: int, explicit_version: int | None):
    if explicit_version is not None:
        cur.execute(
            """
            SELECT id
            FROM translation_prompt_profile_versions
            WHERE profile_id = %s AND version = %s
            LIMIT 1
            """,
            (profile_id, explicit_version),
        )
    else:
        cur.execute(
            """
            SELECT id
            FROM translation_prompt_profile_versions
            WHERE profile_id = %s AND active = TRUE
            ORDER BY version DESC
            LIMIT 1
            """,
            (profile_id,),
        )
    row = cur.fetchone()
    if not row:
        if explicit_version is None:
            raise RuntimeError("No active profile version found")
        raise RuntimeError(f"Profile version not found: {explicit_version}")
    return row[0]


def find_candidates(
    cur,
    source_document: str,
    lemma_id: int | None,
    limit: int | None,
    *,
    target_profile_id: int,
    target_profile_version_id: int,
    include_quarantined: bool,
    include_translated: bool,
    has_human_translations: bool,
    letter: str | None = None,
    headword_prefix: str | None = None,
    headword_start: str | None = None,
    headword_end: str | None = None,
    explicit_lemma_ids: list[int] | None = None,
    order: str = "canonical",
):
    explicit_lemma_ids = explicit_lemma_ids or []
    source_document = normalize_source_document(source_document)
    letter_filter = normalise_letter_filter(letter)
    prefix_filter = normalise_prefix(headword_prefix)
    start_key = normalise_headword_key(headword_start) if headword_start else None
    end_key = normalise_headword_key(headword_end) if headword_end else None

    if source_document == PREFERRED_SOURCE_DOCUMENT:
        source_join = f"""
        JOIN LATERAL (
            SELECT stv.id, stv.text_body, stv.source_document
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = a.id
              AND stv.source_document IN ({public_source_document_list_sql()})
              AND stv.is_current = TRUE
            ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
            LIMIT 1
        ) stv ON TRUE
        """
        params = [int(target_profile_id)]
    else:
        source_join = """
        JOIN lemma_source_text_versions stv
          ON stv.lemma_id = a.id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        """
        params = [int(target_profile_id), source_document]

    query = f"""
        SELECT
            a.id,
            stv.id,
            COALESCE(a.lemma, '') AS lemma,
            a.entry_number,
            EXISTS (
                SELECT 1
                FROM translation_runs tr
                WHERE tr.lemma_id = a.id
                  AND tr.profile_id = %s
                  AND tr.status IN ('approved', 'completed', 'blocked', 'hidden')
                  AND COALESCE(tr.translation_text, '') != ''
            ) AS has_older_profile_run
        FROM assembled_lemmas a
        {source_join}
        WHERE 1=1
    """

    if lemma_id is not None and explicit_lemma_ids:
        raise ValueError("Use either --lemma-id or --lemma-ids, not both")

    if explicit_lemma_ids:
        query += " AND a.id = ANY(%s)"
        params.append([int(value) for value in explicit_lemma_ids])
    elif lemma_id is not None:
        query += " AND a.id = %s"
        params.append(int(lemma_id))
    elif not include_quarantined:
        query += " AND COALESCE(a.quarantined, FALSE) = FALSE"

    # Skip lemmas that already have human translations in the legacy fields.
    query += """
        AND COALESCE(a.reviewed_english_translation, '') = ''
        AND COALESCE(a.corrected_english_translation, '') = ''
    """

    if has_human_translations:
        query += """
            AND NOT EXISTS (
                SELECT 1
                FROM human_translations ht
                WHERE ht.lemma_id = a.id
                  AND ht.status IN ('draft', 'approved')
                  AND COALESCE(ht.translation_text, '') != ''
            )
        """

    # Avoid piling up duplicate pending/running requests for the same lemma.
    query += """
        AND NOT EXISTS (
            SELECT 1
            FROM translation_run_requests trr
            WHERE trr.lemma_id = a.id
              AND trr.status IN ('pending', 'running')
        )
    """

    # Queue only when the authoritative translation_run layer does not already
    # have a successful run for the target profile/version + current source text.
    if not include_translated:
        query += """
            AND NOT EXISTS (
                SELECT 1
                FROM translation_runs tr
                WHERE tr.lemma_id = a.id
                  AND tr.profile_id = %s
                  AND tr.profile_version_id = %s
                  AND tr.source_text_version_id = stv.id
                  AND tr.status IN ('approved', 'completed', 'blocked', 'hidden')
                  AND COALESCE(tr.translation_text, '') != ''
            )
        """
        params.extend([int(target_profile_id), int(target_profile_version_id)])

    # Avoid empty source text.
    query += " AND COALESCE(stv.text_body, '') != ''"

    cur.execute(query, params)
    rows = [
        {
            "lemma_id": int(row[0]),
            "source_text_version_id": int(row[1]),
            "lemma": row[2] or "",
            "entry_number": int(row[3]) if row[3] is not None else None,
            "has_older_profile_run": bool(row[4]),
        }
        for row in cur.fetchall()
    ]

    def matches(row: dict) -> bool:
        key = normalise_headword_key(row.get("lemma", ""))
        if letter_filter and (not key or key[0] != letter_filter):
            return False
        if prefix_filter and not key.startswith(prefix_filter):
            return False
        if start_key and key < start_key:
            return False
        if end_key and key > end_key:
            return False
        return True

    rows = [row for row in rows if matches(row)]

    def canonical_key(row: dict) -> tuple[int, int]:
        entry_number = row.get("entry_number")
        return (
            int(entry_number) if entry_number is not None else 10_000_000,
            int(row["lemma_id"]),
        )

    if order == "random":
        random.shuffle(rows)
    elif order == "reverse":
        rows.sort(key=canonical_key, reverse=True)
    else:
        rows.sort(key=canonical_key)

    if limit is not None:
        rows = rows[: int(limit)]
    return rows


def print_candidate_preview(rows, max_rows: int = 50):
    print("Candidate preview:")
    for row in rows[:max_rows]:
        entry = row.get("entry_number")
        entry_text = f"entry={entry}" if entry is not None else "entry=?"
        print(f"  {row['lemma_id']}\t{entry_text}\t{row.get('lemma', '')}")
    if len(rows) > max_rows:
        print(f"  ... {len(rows) - max_rows} more")


def enqueue(
    cur,
    rows,
    profile_id,
    profile_version_id,
    repeat,
    model,
    temperature,
    top_p,
    created_by,
    priority,
    has_priority_column,
):
    inserted = 0
    for row in rows:
        lemma_id = int(row["lemma_id"])
        source_text_version_id = int(row["source_text_version_id"])
        if has_priority_column:
            cur.execute(
                """
                INSERT INTO translation_run_requests (
                    lemma_id, profile_id, profile_version_id, source_text_version_id,
                    requested_runs, model, temperature, top_p, status, created_by, priority
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                """,
                (
                    lemma_id,
                    profile_id,
                    profile_version_id,
                    source_text_version_id,
                    repeat,
                    model,
                    temperature,
                    top_p,
                    created_by,
                    int(priority),
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO translation_run_requests (
                    lemma_id, profile_id, profile_version_id, source_text_version_id,
                    requested_runs, model, temperature, top_p, status, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                """,
                (
                    lemma_id,
                    profile_id,
                    profile_version_id,
                    source_text_version_id,
                    repeat,
                    model,
                    temperature,
                    top_p,
                    created_by,
                ),
            )
        inserted += 1
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Enqueue translation run requests.")
    parser.add_argument("--profile", required=True, help="Prompt profile name")
    parser.add_argument("--profile-version", type=int, help="Prompt profile version (default: latest active)")
    parser.add_argument(
        "--source-document",
        default=PREFERRED_SOURCE_DOCUMENT,
        choices=(PREFERRED_SOURCE_DOCUMENT, *PREFERRED_GREEK_SOURCE_DOCUMENTS),
    )
    parser.add_argument("--lemma-id", type=int, help="Queue only a single lemma id")
    parser.add_argument("--lemma-ids", type=parse_lemma_ids, help="Comma/space-separated explicit lemma id list")
    parser.add_argument("--letter", help="Greek letter filter, e.g. kappa")
    parser.add_argument("--headword-prefix", help="Headword prefix filter; Greek text or a single Latin initial")
    parser.add_argument("--headword-start", "--range-start", dest="headword_start", help="Inclusive headword range start")
    parser.add_argument("--headword-end", "--range-end", dest="headword_end", help="Inclusive headword range end")
    parser.add_argument("--limit", type=int, help="Max lemmas to queue")
    parser.add_argument(
        "--order",
        default="canonical",
        choices=["canonical", "reverse", "random"],
        help="Candidate ordering before limit is applied",
    )
    parser.add_argument("--priority", type=int, default=100, help="Lower values are processed first")
    parser.add_argument(
        "--missing-final",
        action="store_true",
        help="Queue only entries without final/reviewed human translation; this is the default safety filter",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Runs requested per lemma")
    parser.add_argument("--include-quarantined", action="store_true", help="Include quarantined lemmas in selection")
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Also queue lemmas that already have an AI translation (default: queue untranslated/outdated only)",
    )
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--created-by", default="enqueue_translation_runs.py")
    parser.add_argument(
        "--prepare-guidance-first",
        action="store_true",
        help="Queue missing prompt-eligible guidance checks for selected candidates before enqueueing translations",
    )
    parser.add_argument(
        "--require-guidance-complete",
        action="store_true",
        help="Only enqueue translation requests whose prompt-eligible guidance coverage is complete",
    )
    parser.add_argument(
        "--guidance-queue-priority",
        type=int,
        default=20,
        help="Priority for guidance rows queued by --prepare-guidance-first",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print candidate/coverage summary without writing")
    args = parser.parse_args()

    if args.lemma_id is not None and args.lemma_ids:
        parser.error("Use either --lemma-id or --lemma-ids, not both")
    if args.priority < 0:
        parser.error("--priority must be non-negative")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")

    required_tables = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "translation_run_requests",
        "translation_runs",
        "lemma_source_text_versions",
    ]
    missing = []
    for table in required_tables:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        print("Missing required tables:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        conn.close()
        return

    profile_id = resolve_profile(cur, args.profile)
    profile_version_id = resolve_profile_version(cur, profile_id, args.profile_version)
    cur.execute("SELECT to_regclass('public.human_translations') IS NOT NULL")
    has_human_translations = bool(cur.fetchone()[0])
    has_priority_column = column_exists(cur, "translation_run_requests", "priority")
    if not has_priority_column and args.priority != 100:
        print("Warning: translation_run_requests.priority is missing; priority will not be stored. Run migrations.")
    candidates = find_candidates(
        cur,
        args.source_document,
        args.lemma_id,
        args.limit,
        target_profile_id=profile_id,
        target_profile_version_id=profile_version_id,
        include_quarantined=bool(args.include_quarantined),
        include_translated=bool(args.include_translated),
        has_human_translations=has_human_translations,
        letter=args.letter,
        headword_prefix=args.headword_prefix,
        headword_start=args.headword_start,
        headword_end=args.headword_end,
        explicit_lemma_ids=args.lemma_ids or [],
        order=args.order,
    )

    if not candidates:
        print("No candidate lemmas found for enqueue.")
        conn.close()
        return

    if args.prepare_guidance_first or args.require_guidance_complete:
        ready = []
        incomplete = []
        guidance_rows_inserted = 0
        for row in candidates:
            lemma_id = int(row["lemma_id"])
            source_text_version_id = int(row["source_text_version_id"])
            coverage = guidance_coverage_counts(
                cur,
                source_text_version_id=int(source_text_version_id),
            )
            if args.prepare_guidance_first and int(coverage.get("missing", 0)) > 0:
                queued = enqueue_missing_guidance(
                    cur,
                    lemma_id=int(lemma_id),
                    source_text_version_id=int(source_text_version_id),
                    requested_by=args.created_by,
                    priority=args.guidance_queue_priority,
                    notes="queued before translation request because guidance-first mode is enabled",
                )
                guidance_rows_inserted += queued["inserted"]
                coverage = guidance_coverage_counts(
                    cur,
                    source_text_version_id=int(source_text_version_id),
                )

            if (
                coverage.get("available")
                and int(coverage.get("required", 0)) > 0
                and int(coverage.get("missing", 0)) == 0
            ):
                ready.append(row)
            else:
                incomplete.append((row, coverage))

        print(f"Translation candidates selected: {len(candidates)}")
        print(f"Guidance-complete candidates: {len(ready)}")
        print(f"Guidance-incomplete candidates: {len(incomplete)}")
        if args.prepare_guidance_first:
            print(f"Missing guidance queue rows inserted: {guidance_rows_inserted}")

        if args.require_guidance_complete:
            candidates = ready
            if not candidates:
                print("No guidance-complete translation candidates to enqueue.")
                if args.dry_run:
                    conn.rollback()
                else:
                    conn.commit()
                conn.close()
                return

    if args.dry_run:
        print(f"Would queue translation requests: {len(candidates)}")
        if candidates:
            print_candidate_preview(candidates, max_rows=max(50, min(len(candidates), 100)))
        conn.rollback()
        conn.close()
        return

    inserted = enqueue(
        cur,
        candidates,
        profile_id=profile_id,
        profile_version_id=profile_version_id,
        repeat=max(1, args.repeat),
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        created_by=args.created_by,
        priority=args.priority,
        has_priority_column=has_priority_column,
    )
    conn.commit()
    conn.close()

    print(f"Queued translation requests: {inserted}")


if __name__ == "__main__":
    main()
