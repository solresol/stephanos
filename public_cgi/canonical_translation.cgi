#!/usr/bin/env python3
"""
Public CGI endpoint for canonical translation read/set operations.

GET:
  /public-cgi/canonical_translation.cgi?lemma_id=123
  /public-cgi/canonical_translation.cgi?headword=Καδμεία

POST (requires REMOTE_USER):
  action=add|remove|set_primary|clear_all|clear_primary
  lemma_id=123 (or headword=...)
  variant_kind=translation_run|human_translation|legacy_assembled (required for add/remove/set_primary)
  variant_id=... (required for add/remove/set_primary)
  notes=... (optional)

Operational note:
  This endpoint MUST be local-only (no SSH proxy). It reads baseline lemma
  data from ../db/review_data.sqlite and records canonical actions in ../db/reviews.db.
  Nightly import applies the action log to PostgreSQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html as html_module
import json
import os
import sqlite3
from urllib.parse import parse_qs


SNAPSHOT_DB = "../db/review_data.sqlite"
SQLITE_DB = "../db/reviews.db"

KIND_PRIORITY = {
    "human_translation": 0,
    "translation_run": 1,
    "legacy_assembled": 2,
}


@dataclass(frozen=True)
class CanonicalAction:
    id: int
    action: str
    variant_kind: str
    variant_id: str
    reviewer_username: str
    reviewed_at: str
    notes: str


def emit_json(status_code: int, payload: dict):
    status_text = {
        200: "200 OK",
        204: "204 No Content",
        400: "400 Bad Request",
        401: "401 Unauthorized",
        403: "403 Forbidden",
        405: "405 Method Not Allowed",
        500: "500 Internal Server Error",
        502: "502 Bad Gateway",
    }.get(status_code, f"{status_code} OK")

    print(f"Status: {status_text}")
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print("Access-Control-Allow-Origin: *")
    print("Access-Control-Allow-Methods: GET, POST, OPTIONS")
    print("Access-Control-Allow-Headers: Content-Type")
    print()
    if status_code != 204:
        print(json.dumps(payload, ensure_ascii=False))


def parse_request_params(method: str) -> dict[str, str]:
    if method == "GET":
        raw_query = os.environ.get("QUERY_STRING", "")
        parsed = parse_qs(raw_query, keep_blank_values=False)
        return {k: v[-1] for k, v in parsed.items() if v}

    if method == "POST":
        length_raw = os.environ.get("CONTENT_LENGTH", "0").strip()
        try:
            length = int(length_raw or "0")
        except ValueError:
            length = 0
        body = os.read(0, max(0, length)).decode("utf-8", errors="replace")
        parsed = parse_qs(body, keep_blank_values=False)
        return {k: v[-1] for k, v in parsed.items() if v}

    return {}


def require_target(params: dict[str, str]) -> tuple[str, str]:
    lemma_id = (params.get("lemma_id") or "").strip()
    headword = (params.get("headword") or "").strip()
    if lemma_id:
        if not lemma_id.isdigit():
            raise RuntimeError("lemma_id must be a positive integer")
        return "lemma_id", lemma_id
    if headword:
        return "headword", headword
    raise RuntimeError("Provide lemma_id or headword")

def open_snapshot() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SNAPSHOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def decode_snapshot_lemma(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    payload = row["payload_json"]
    if not isinstance(payload, str) or not payload.strip():
        return None
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        return None
    return decoded


def resolve_lemma_from_snapshot(target_key: str, target_value: str) -> dict:
    with open_snapshot() as conn:
        if target_key == "lemma_id":
            lemma_id = int(target_value)
            row = conn.execute(
                "SELECT payload_json FROM lemmas WHERE id = ?",
                (lemma_id,),
            ).fetchone()
            lemma = decode_snapshot_lemma(row)
            if lemma is None:
                raise RuntimeError(f"lemma id {lemma_id} not found")
            return lemma

        headword = target_value
        rows = conn.execute(
            """
            SELECT payload_json
            FROM lemmas
            WHERE lemma = ?
            ORDER BY version, sort_order
            """,
            (headword,),
        ).fetchall()
        fallback = None
        for row in rows:
            lemma = decode_snapshot_lemma(row)
            if lemma is None:
                continue
            if (lemma.get("version") or "").lower() == "epitome":
                return lemma
            if fallback is None:
                fallback = lemma
        if fallback is not None:
            return fallback
    raise RuntimeError(f"headword not found: {target_value}")


def resolve_lemma(target_key: str, target_value: str) -> dict:
    return resolve_lemma_from_snapshot(target_key, target_value)


def open_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canonical_variant_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'set_primary', 'clear_all', 'clear_primary')),
            variant_kind TEXT,
            variant_id TEXT,
            reviewer_username TEXT,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            CHECK (
                action IN ('clear_all', 'clear_primary')
                OR (
                    variant_kind IS NOT NULL AND variant_kind <> ''
                    AND variant_id IS NOT NULL AND variant_id <> ''
                )
            )
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_canonical_actions_lemma ON canonical_variant_actions(lemma_id, reviewed_at, id)"
    )


def fetch_actions(conn: sqlite3.Connection, lemma_id: int) -> list[CanonicalAction]:
    rows = conn.execute(
        """
        SELECT
            id,
            COALESCE(action, '') AS action,
            COALESCE(variant_kind, '') AS variant_kind,
            COALESCE(variant_id, '') AS variant_id,
            COALESCE(reviewer_username, '') AS reviewer_username,
            COALESCE(reviewed_at, '') AS reviewed_at,
            COALESCE(notes, '') AS notes
        FROM canonical_variant_actions
        WHERE lemma_id = ?
        ORDER BY reviewed_at ASC, id ASC
        """,
        (lemma_id,),
    ).fetchall()
    actions: list[CanonicalAction] = []
    for row in rows:
        actions.append(
            CanonicalAction(
                id=int(row["id"]),
                action=str(row["action"] or "").strip().lower(),
                variant_kind=str(row["variant_kind"] or "").strip(),
                variant_id=str(row["variant_id"] or "").strip(),
                reviewer_username=str(row["reviewer_username"] or "").strip(),
                reviewed_at=str(row["reviewed_at"] or "").strip(),
                notes=str(row["notes"] or "").strip(),
            )
        )
    return actions


def parse_dt(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def variant_key(kind: str, vid: str) -> str:
    return f"{(kind or '').strip()}|{(vid or '').strip()}"


def baseline_memberships(lemma: dict) -> dict[str, dict]:
    state: dict[str, dict] = {}

    for item in (lemma.get("canonical_variants") or []):
        if not isinstance(item, dict):
            continue
        kind = (item.get("kind") or "").strip()
        vid = str(item.get("id") or "").strip()
        if not kind or not vid:
            continue
        state[variant_key(kind, vid)] = {
            "kind": kind,
            "id": vid,
            "is_primary": bool(item.get("is_primary", False)),
            "updated_at": str(item.get("updated_at") or "").strip(),
        }

    if not state:
        ref = lemma.get("canonical_variant_ref") or {}
        if isinstance(ref, dict):
            kind = (ref.get("kind") or "").strip()
            vid = str(ref.get("id") or "").strip()
            if kind and vid:
                state[variant_key(kind, vid)] = {
                    "kind": kind,
                    "id": vid,
                    "is_primary": True,
                    "updated_at": "",
                }

    if not state:
        state[variant_key("legacy_assembled", "translation")] = {
            "kind": "legacy_assembled",
            "id": "translation",
            "is_primary": True,
            "updated_at": "",
        }

    return state


def apply_actions(state: dict[str, dict], actions: list[CanonicalAction]) -> dict[str, dict]:
    def clear_primary():
        for k in list(state.keys()):
            state[k]["is_primary"] = False

    for a in actions:
        action = (a.action or "").strip().lower()
        kind = (a.variant_kind or "").strip()
        vid = (a.variant_id or "").strip()
        key = variant_key(kind, vid)

        if action == "add":
            if not kind or not vid:
                continue
            if key not in state:
                state[key] = {"kind": kind, "id": vid, "is_primary": False, "updated_at": a.reviewed_at}
            else:
                state[key]["updated_at"] = a.reviewed_at or state[key].get("updated_at", "")
        elif action == "remove":
            if not kind or not vid:
                continue
            state.pop(key, None)
        elif action == "set_primary":
            if not kind or not vid:
                continue
            clear_primary()
            state[key] = {"kind": kind, "id": vid, "is_primary": True, "updated_at": a.reviewed_at}
        elif action == "clear_primary":
            clear_primary()
        elif action == "clear_all":
            state.clear()

    return state


def build_variant_index(lemma: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for v in (lemma.get("translation_variants") or []):
        if not isinstance(v, dict):
            continue
        kind = (v.get("kind") or "").strip()
        vid = str(v.get("id") or "").strip()
        if not kind or not vid:
            continue
        index[variant_key(kind, vid)] = v

    # Ensure legacy variant is addressable.
    legacy_key = variant_key("legacy_assembled", "translation")
    if legacy_key not in index:
        index[legacy_key] = {"kind": "legacy_assembled", "id": "translation"}
    return index


def is_publishable_local(lemma: dict, v: dict) -> bool:
    kind = (v.get("kind") or "").strip()
    status = (v.get("status") or "").strip()

    if kind == "translation_run":
        if status != "approved":
            return False
        guidance_state = (v.get("guidance_freshness_state") or "").strip()
        if guidance_state in {"potentially_outdated", "needs_review", "outdated"}:
            return False
        if v.get("public_eligible") is False:
            return False
        if (v.get("public_block_reason") or "").strip():
            return False
        return bool((v.get("preview") or "").strip())

    if kind == "human_translation":
        if status != "approved":
            return False
        return bool((v.get("preview") or "").strip())

    if kind == "legacy_assembled":
        if lemma.get("translation_blocked"):
            return False
        text = (v.get("text") or lemma.get("english_translation") or "").strip()
        return bool(text)

    return False


def membership_sort_key(m: dict):
    is_primary = bool(m.get("is_primary", False))
    updated_at = parse_dt(str(m.get("updated_at") or ""))
    kind = (m.get("kind") or "").strip()
    vid = str(m.get("id") or "").strip()
    vid_int = None
    if vid.isdigit():
        try:
            vid_int = int(vid)
        except ValueError:
            vid_int = None
    return (
        0 if is_primary else 1,
        -(updated_at.timestamp()) if updated_at else 0,
        KIND_PRIORITY.get(kind, 99),
        -(vid_int or 0),
        vid,
    )


def select_presented_variants_local(lemma: dict, memberships: list[dict]) -> list[dict]:
    index = build_variant_index(lemma)
    candidates: list[dict] = []
    for m in memberships:
        k = variant_key(m.get("kind", ""), m.get("id", ""))
        v = index.get(k)
        if not v or not is_publishable_local(lemma, v):
            continue
        text = (v.get("text") or v.get("preview") or "").strip()
        candidates.append(
            {
                "kind": (m.get("kind") or "").strip(),
                "id": str(m.get("id") or "").strip(),
                "is_primary": bool(m.get("is_primary", False)),
                "updated_at": str(m.get("updated_at") or "").strip(),
                "status": (v.get("status") or "").strip(),
                "source_document": (v.get("source_document") or "").strip(),
                "source_text_version_id": str(v.get("source_text_version_id") or "").strip(),
                "translation_text": text,
            }
        )
    candidates.sort(key=membership_sort_key)
    return candidates


def select_fallback_variant_local(lemma: dict) -> dict | None:
    index = build_variant_index(lemma)

    # human_translation: latest updated_at/id
    human = []
    for k, v in index.items():
        if (v.get("kind") or "").strip() != "human_translation":
            continue
        if not is_publishable_local(lemma, v):
            continue
        human.append(v)
    if human:
        human.sort(
            key=lambda v: (
                parse_dt(str(v.get("updated_at") or "")) or datetime.min,
                int(v.get("id")) if str(v.get("id") or "").isdigit() else -1,
            ),
            reverse=True,
        )
        chosen = human[0]
        return {
            "kind": "human_translation",
            "id": str(chosen.get("id") or ""),
            "is_primary": False,
            "updated_at": str(chosen.get("updated_at") or ""),
            "status": (chosen.get("status") or "").strip(),
            "source_document": (chosen.get("source_document") or "").strip(),
            "source_text_version_id": str(chosen.get("source_text_version_id") or "").strip(),
            "translation_text": (chosen.get("preview") or "").strip(),
        }

    # translation_run: latest created_at/id
    runs = []
    for k, v in index.items():
        if (v.get("kind") or "").strip() != "translation_run":
            continue
        if not is_publishable_local(lemma, v):
            continue
        runs.append(v)
    if runs:
        runs.sort(
            key=lambda v: (
                parse_dt(str(v.get("created_at") or "")) or datetime.min,
                int(v.get("id")) if str(v.get("id") or "").isdigit() else -1,
            ),
            reverse=True,
        )
        chosen = runs[0]
        return {
            "kind": "translation_run",
            "id": str(chosen.get("id") or ""),
            "is_primary": False,
            "updated_at": str(chosen.get("created_at") or ""),
            "status": (chosen.get("status") or "").strip(),
            "source_document": (chosen.get("source_document") or "").strip(),
            "source_text_version_id": str(chosen.get("source_text_version_id") or "").strip(),
            "translation_text": (chosen.get("preview") or "").strip(),
        }

    legacy_key = variant_key("legacy_assembled", "translation")
    legacy = index.get(legacy_key)
    if legacy and is_publishable_local(lemma, legacy):
        text = (legacy.get("text") or lemma.get("english_translation") or "").strip()
        return {
            "kind": "legacy_assembled",
            "id": "translation",
            "is_primary": False,
            "updated_at": "",
            "status": (legacy.get("status") or "approved").strip(),
            "source_document": (legacy.get("source_document") or "billerbeck").strip(),
            "source_text_version_id": str(legacy.get("source_text_version_id") or "").strip(),
            "translation_text": text,
        }

    return None


def compute_state(lemma: dict, actions: list[CanonicalAction]) -> dict:
    baseline_pointer = lemma.get("canonical_variant_ref") if isinstance(lemma.get("canonical_variant_ref"), dict) else {}
    baseline_kind = (baseline_pointer.get("kind") or "legacy_assembled").strip() if isinstance(baseline_pointer, dict) else "legacy_assembled"
    baseline_id = str(baseline_pointer.get("id") or "translation").strip() if isinstance(baseline_pointer, dict) else "translation"

    state = baseline_memberships(lemma)
    state = apply_actions(state, actions)
    memberships = list(state.values())
    memberships.sort(key=membership_sort_key)

    presented = select_presented_variants_local(lemma, memberships)
    selected = None
    if presented:
        primary = next((v for v in presented if v.get("is_primary")), None)
        selected = primary or presented[0]
    else:
        selected = select_fallback_variant_local(lemma)

    blocked = selected is None
    reason = ""
    if blocked:
        reason = "No presentable translation variant found locally"
    elif selected.get("kind") == "legacy_assembled" and lemma.get("translation_blocked"):
        blocked = True
        reason = (lemma.get("translation_block_reason") or "").strip() or "Legacy translation blocked by risk gating"

    return {
        "lemma_id": int(lemma.get("id") or 0),
        "lemma": lemma.get("lemma") or "",
        "canonical_pointer": {"kind": baseline_kind, "id": baseline_id},
        "canonical_memberships": memberships,
        "presented_variants": [
            {
                "kind": v.get("kind", ""),
                "id": v.get("id", ""),
                "is_primary": bool(v.get("is_primary", False)),
                "status": v.get("status", ""),
                "source_document": v.get("source_document", ""),
                "source_text_version_id": v.get("source_text_version_id", ""),
                "preview": ((v.get("translation_text") or "").strip()[:180]),
            }
            for v in presented
        ],
        "selected_variant": {
            "kind": selected.get("kind", "") if selected else "",
            "id": selected.get("id", "") if selected else "",
            "status": selected.get("status", "") if selected else "",
            "source_document": selected.get("source_document", "") if selected else "",
            "source_text_version_id": selected.get("source_text_version_id", "") if selected else "",
        },
        "translation_text": (selected.get("translation_text", "") if selected else ""),
        "translation_blocked": bool(blocked),
        "translation_block_reason": reason,
        "sqlite_actions_applied": len(actions),
        "sqlite_last_action_id": actions[-1].id if actions else 0,
    }


def insert_action(
    conn: sqlite3.Connection,
    *,
    lemma_id: int,
    action: str,
    variant_kind: str,
    variant_id: str,
    reviewer_username: str,
    notes: str,
) -> int:
    action = (action or "").strip().lower()
    if action == "set":
        action = "set_primary"
    if action == "clear":
        action = "clear_all"

    if action not in {"add", "remove", "set_primary", "clear_all", "clear_primary"}:
        raise RuntimeError("Unsupported action")

    if action in {"clear_all", "clear_primary"}:
        variant_kind = ""
        variant_id = ""
    else:
        variant_kind = (variant_kind or "").strip()
        variant_id = (variant_id or "").strip()
        if not variant_kind or not variant_id:
            raise RuntimeError("variant_kind and variant_id are required for this action")

    cur = conn.execute(
        """
        INSERT INTO canonical_variant_actions (
            lemma_id, action, variant_kind, variant_id, reviewer_username, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lemma_id, action, variant_kind, variant_id, reviewer_username, notes or ""),
    )
    return int(cur.lastrowid or 0)


def main():
    method = (os.environ.get("REQUEST_METHOD") or "GET").upper()
    if method == "OPTIONS":
        emit_json(204, {})
        return
    if method not in {"GET", "POST"}:
        emit_json(405, {"ok": False, "error": "Method not allowed"})
        return

    try:
        params = parse_request_params(method)

        if method == "GET":
            target_key, target_value = require_target(params)
            lemma = resolve_lemma(target_key, target_value)
            lemma_id = int(lemma.get("id") or 0)
            with open_sqlite() as conn:
                ensure_schema(conn)
                actions = fetch_actions(conn, lemma_id)
            result = compute_state(lemma, actions)
            emit_json(200, {"ok": True, "result": result})
            return

        remote_user = (os.environ.get("REMOTE_USER") or "").strip()
        if not remote_user:
            emit_json(403, {"ok": False, "error": "Authenticated user required for canonical updates"})
            return

        action = (params.get("action") or "set_primary").strip().lower()
        target_key, target_value = require_target(params)
        lemma = resolve_lemma(target_key, target_value)
        lemma_id = int(lemma.get("id") or 0)

        variant_kind = (params.get("variant_kind") or "").strip()
        variant_id = (params.get("variant_id") or "").strip()
        notes = (params.get("notes") or "").strip()

        with open_sqlite() as conn:
            ensure_schema(conn)
            action_id = insert_action(
                conn,
                lemma_id=lemma_id,
                action=action,
                variant_kind=variant_kind,
                variant_id=variant_id,
                reviewer_username=remote_user,
                notes=notes,
            )
            conn.commit()
            actions = fetch_actions(conn, lemma_id)

        current_result = compute_state(lemma, actions)

        emit_json(
            200,
            {
                "ok": True,
                "action_id": action_id,
                "reviewer_username": remote_user,
                "current_result": current_result,
            },
        )
    except Exception as exc:
        emit_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
