"""
Canonical translation variant selection helpers.

These utilities centralize the logic for:
- Determining whether a variant is presentable (approved, non-empty, not risk-blocked)
- Selecting presented variants for public UX (single or multi)
- Selecting a single projection variant for downstream consumers

All functions operate on a DB cursor and are safe to call when optional tables
are missing (they return empty results / fall back deterministically).
"""

from __future__ import annotations

from typing import Any


VARIANT_KINDS = ("translation_run", "human_translation", "legacy_assembled")
VARIANT_KIND_PRIORITY = {
    "human_translation": 0,
    "translation_run": 1,
    "legacy_assembled": 2,
}
PUBLICLY_DEPRECATED_KINDS = {"legacy_assembled"}


def table_exists(cur, table_name: str) -> bool:
    cache_key = None
    try:
        cache_key = (id(getattr(cur, "connection", None) or cur), table_name)
    except Exception:
        cache_key = (id(cur), table_name)

    cache = getattr(table_exists, "_cache", None)
    if cache is None:
        cache = {}
        setattr(table_exists, "_cache", cache)
    if cache_key in cache:
        return bool(cache[cache_key])

    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    exists = bool(cur.fetchone()[0])
    cache[cache_key] = exists
    return exists


def _risk_block_status(cur, *, lemma_id: int, variant_kind: str, variant_id: str) -> tuple[bool, str]:
    if not table_exists(cur, "translation_risk_flags"):
        return False, ""
    cur.execute(
        """
        SELECT
            COALESCE(is_blocked, FALSE),
            COALESCE(details_json->>'summary', ''),
            COALESCE(risk_code, '')
        FROM translation_risk_flags
        WHERE lemma_id = %s
          AND variant_kind = %s
          AND variant_id = %s
          AND is_blocked = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (lemma_id, (variant_kind or "").strip(), str(variant_id or "").strip()),
    )
    row = cur.fetchone()
    if not row:
        return False, ""
    summary = (row[1] or "").strip()
    risk_code = (row[2] or "").strip()
    return True, summary or risk_code or "Blocked by risk gating"


def resolve_variant(cur, *, lemma_id: int, variant_kind: str, variant_id: str) -> dict[str, Any]:
    """
    Resolve a translation variant reference to its publishability + text.

    Returns a dict with at least:
      exists: bool
      publishable: bool
      block_reason: str
      translation_text: str
      status: str
      kind: str
      id: str
    """
    variant_kind = (variant_kind or "").strip()
    variant_id = str(variant_id or "").strip()
    if not variant_kind or not variant_id:
        return {
            "exists": False,
            "publishable": False,
            "block_reason": "Missing variant reference",
        }
    if variant_kind not in VARIANT_KINDS:
        return {
            "exists": False,
            "publishable": False,
            "block_reason": f"Unsupported variant_kind: {variant_kind}",
        }

    blocked, block_reason = _risk_block_status(
        cur, lemma_id=lemma_id, variant_kind=variant_kind, variant_id=variant_id
    )

    if variant_kind == "translation_run":
        if not table_exists(cur, "translation_runs"):
            return {
                "exists": False,
                "publishable": False,
                "block_reason": "translation_runs table missing",
            }
        cur.execute(
            """
            SELECT
                tr.id,
                COALESCE(tr.translation_text, ''),
                COALESCE(tr.status, ''),
                COALESCE(tr.public_eligible, TRUE),
                COALESCE(tr.public_block_reason, ''),
                tr.source_text_version_id,
                COALESCE(tr.model, ''),
                COALESCE(p.name, ''),
                pv.version,
                COALESCE(stv.source_document, '')
            FROM translation_runs tr
            LEFT JOIN translation_prompt_profiles p
              ON p.id = tr.profile_id
            LEFT JOIN translation_prompt_profile_versions pv
              ON pv.id = tr.profile_version_id
            LEFT JOIN lemma_source_text_versions stv
              ON stv.id = tr.source_text_version_id
            WHERE tr.id = %s
              AND tr.lemma_id = %s
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

        translation_text = (row[1] or "").strip()
        status = (row[2] or "").strip()
        public_eligible = bool(row[3])
        public_block_reason = (row[4] or "").strip()

        publishable = (
            status == "approved"
            and public_eligible
            and not public_block_reason
            and bool(translation_text)
            and not blocked
        )
        if not publishable and not block_reason:
            if status != "approved":
                block_reason = f"translation_run status is {status or 'unknown'}"
            elif not public_eligible:
                block_reason = "translation_run is not public_eligible"
            elif public_block_reason:
                block_reason = public_block_reason
            elif not translation_text:
                block_reason = "translation_run has empty translation_text"
            elif blocked:
                block_reason = "translation_run blocked by risk gating"

        return {
            "exists": True,
            "publishable": publishable,
            "block_reason": block_reason,
            "translation_text": translation_text,
            "status": status,
            "kind": variant_kind,
            "id": variant_id,
            "source_document": (row[9] or "").strip(),
            "source_text_version_id": str(row[5] or ""),
            "model": (row[6] or "").strip(),
            "profile_name": (row[7] or "").strip(),
            "profile_version": int(row[8]) if row[8] is not None else None,
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
            SELECT ht.id,
                   COALESCE(translation_text, ''),
                   COALESCE(status, ''),
                   ht.source_text_version_id,
                   COALESCE(stv.source_document, '')
            FROM human_translations ht
            LEFT JOIN lemma_source_text_versions stv
              ON stv.id = ht.source_text_version_id
            WHERE ht.id = %s
              AND ht.lemma_id = %s
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
        translation_text = (row[1] or "").strip()
        status = (row[2] or "").strip()
        publishable = status == "approved" and bool(translation_text) and not blocked
        if not publishable and not block_reason:
            if status != "approved":
                block_reason = f"human_translation status is {status or 'unknown'}"
            elif not translation_text:
                block_reason = "human_translation has empty translation_text"
            elif blocked:
                block_reason = "human_translation blocked by risk gating"
        return {
            "exists": True,
            "publishable": publishable,
            "block_reason": block_reason,
            "translation_text": translation_text,
            "status": status,
            "kind": variant_kind,
            "id": variant_id,
            "source_document": (row[4] or "").strip(),
            "source_text_version_id": str(row[3] or ""),
            "model": "",
            "profile_name": "",
            "profile_version": None,
        }

    # legacy_assembled
    cur.execute(
        """
        SELECT
            COALESCE(reviewed_english_translation, '') AS reviewed,
            COALESCE(corrected_english_translation, '') AS corrected,
            COALESCE(translation, '') AS legacy_translation
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
    reviewed, corrected, legacy_translation = (row[0] or "").strip(), (row[1] or "").strip(), (row[2] or "").strip()
    translation_text = reviewed or corrected or legacy_translation

    publishable = bool(translation_text) and not blocked
    if not publishable and not block_reason:
        if blocked:
            block_reason = "Legacy translation blocked by risk gating"
        else:
            block_reason = "Legacy translation is empty"

    return {
        "exists": True,
        "publishable": publishable,
        "block_reason": block_reason,
        "translation_text": translation_text,
        "status": "approved" if publishable else "blocked",
        "kind": "legacy_assembled",
        "id": "translation",
        "source_document": "billerbeck",
        "source_text_version_id": "",
        "model": "",
        "profile_name": "legacy_scholarly" if translation_text else "",
        "profile_version": None,
    }


def _fetch_active_canonical_memberships(cur, *, lemma_id: int) -> list[dict[str, Any]]:
    if not table_exists(cur, "lemma_canonical_variants"):
        return []
    cur.execute(
        """
        SELECT
            variant_kind,
            variant_id,
            COALESCE(is_primary, FALSE) AS is_primary,
            updated_at,
            COALESCE(updated_by, '') AS updated_by
        FROM lemma_canonical_variants
        WHERE lemma_id = %s
          AND is_active = TRUE
        ORDER BY COALESCE(is_primary, FALSE) DESC, updated_at DESC, variant_kind, variant_id
        """,
        (lemma_id,),
    )
    memberships = []
    for kind, vid, is_primary, updated_at, updated_by in cur.fetchall():
        memberships.append(
            {
                "kind": (kind or "").strip(),
                "id": str(vid or "").strip(),
                "is_primary": bool(is_primary),
                "membership_updated_at": updated_at,
                "membership_updated_by": (updated_by or "").strip(),
            }
        )
    return memberships


def resolve_fallback_variant(cur, *, lemma_id: int) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None

    if table_exists(cur, "human_translations"):
        cur.execute(
            """
            SELECT id::text, updated_at
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
            candidate = resolve_variant(cur, lemma_id=lemma_id, variant_kind="human_translation", variant_id=row[0])
            if candidate.get("publishable"):
                best = {**candidate, "sort_ts": row[1]}

    if table_exists(cur, "translation_runs"):
        cur.execute(
            """
            SELECT
                tr.id::text,
                COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) AS sort_ts
            FROM translation_runs tr
            LEFT JOIN translation_prompt_profiles p
              ON p.id = tr.profile_id
            LEFT JOIN translation_prompt_profile_versions pv
              ON pv.id = tr.profile_version_id
            WHERE tr.lemma_id = %s
              AND status = 'approved'
              AND public_eligible = TRUE
              AND COALESCE(public_block_reason, '') = ''
              AND COALESCE(translation_text, '') != ''
            ORDER BY
              CASE WHEN COALESCE(p.name, '') = 'legacy_scholarly' THEN 0 ELSE 1 END,
              COALESCE(pv.version, 0) DESC,
              COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
              tr.id DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if row:
            candidate = resolve_variant(cur, lemma_id=lemma_id, variant_kind="translation_run", variant_id=row[0])
            if candidate.get("publishable"):
                if best is None:
                    best = {**candidate, "sort_ts": row[1]}
                else:
                    best_ts = best.get("sort_ts")
                    run_ts = row[1]
                    if run_ts is not None and (best_ts is None or run_ts > best_ts):
                        best = {**candidate, "sort_ts": run_ts}

    if not best:
        return None
    best.pop("sort_ts", None)
    return best


def select_presented_variants(
    cur,
    *,
    lemma_id: int,
    ux_mode: str = "multi",
) -> list[dict[str, Any]]:
    """
    Return the list of presented, publishable variants for a lemma.

    ux_mode:
      - 'single': returns exactly 0 or 1 variant
      - 'multi': returns 0..N variants (canonical set if present, else 0/1 fallback)
    """
    ux_mode = (ux_mode or "multi").strip().lower()
    if ux_mode not in {"single", "multi"}:
        ux_mode = "multi"

    has_memberships = table_exists(cur, "lemma_canonical_variants")

    memberships = _fetch_active_canonical_memberships(cur, lemma_id=lemma_id) if has_memberships else []
    canonical_candidates: list[dict[str, Any]] = []
    for membership in memberships:
        candidate = resolve_variant(
            cur,
            lemma_id=lemma_id,
            variant_kind=membership["kind"],
            variant_id=membership["id"],
        )
        if not candidate.get("publishable"):
            continue
        if candidate.get("kind") in PUBLICLY_DEPRECATED_KINDS:
            continue
        canonical_candidates.append(
            {
                **candidate,
                "is_primary": bool(membership.get("is_primary")),
                "membership_updated_at": membership.get("membership_updated_at"),
                "membership_updated_by": membership.get("membership_updated_by", ""),
            }
        )

    def sort_key(v: dict[str, Any]):
        is_primary = bool(v.get("is_primary"))
        updated_at = v.get("membership_updated_at")
        kind = v.get("kind", "")
        vid = v.get("id", "")
        vid_int = None
        if isinstance(vid, str) and vid.isdigit():
            try:
                vid_int = int(vid)
            except ValueError:
                vid_int = None
        return (
            0 if is_primary else 1,
            -(updated_at.timestamp()) if hasattr(updated_at, "timestamp") else 0,
            VARIANT_KIND_PRIORITY.get(kind, 99),
            -(vid_int or 0),
            vid,
        )

    canonical_candidates.sort(key=sort_key)
    if canonical_candidates:
        if ux_mode == "single":
            primary = next((v for v in canonical_candidates if v.get("is_primary")), None)
            return [primary or canonical_candidates[0]]
        return canonical_candidates

    fallback = resolve_fallback_variant(cur, lemma_id=lemma_id)
    if not fallback:
        return []
    return [fallback]


def select_pointer_variant(cur, *, lemma_id: int) -> dict[str, Any] | None:
    """
    Select a single presentable variant for a lemma.

    Uses canonical primary when present; otherwise deterministic canonical fallback; otherwise fallback policy.
    """
    presented = select_presented_variants(cur, lemma_id=lemma_id, ux_mode="single")
    if not presented:
        return None
    choice = presented[0]
    return {
        "kind": choice.get("kind", ""),
        "id": str(choice.get("id", "") or ""),
        "translation_text": choice.get("translation_text", ""),
        "status": choice.get("status", ""),
        "source_document": choice.get("source_document", ""),
        "source_text_version_id": choice.get("source_text_version_id", ""),
        "model": choice.get("model", ""),
        "profile_name": choice.get("profile_name", ""),
        "profile_version": choice.get("profile_version"),
    }
