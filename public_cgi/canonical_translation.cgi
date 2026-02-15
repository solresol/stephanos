#!/usr/bin/env python3
"""
Public CGI endpoint for canonical translation read/set operations.

GET:
  /public-cgi/canonical_translation.cgi?lemma_id=123
  /public-cgi/canonical_translation.cgi?headword=Καδμεία

POST (requires REMOTE_USER):
  action=set
  lemma_id=123 (or headword=...)
  variant_kind=translation_run|human_translation|legacy_assembled
  variant_id=...
  OR translation_text=...
  publish=1 (default)
"""
from __future__ import annotations

import json
import os
import subprocess
from urllib.parse import parse_qs


RAKSASA_HOST = "stephanos@raksasa.cassia.ifost.org.au"
REMOTE_PYTHON = "/home/stephanos/stephanos/.venv/bin/python"
REMOTE_SERVICE = "/home/stephanos/stephanos/canonical_translation_service.py"
REMOTE_PUBLISH = "/home/stephanos/stephanos/publish_canonical_update.py"


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


def run_remote(script_path: str, extra_args: list[str], timeout: int) -> dict:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        RAKSASA_HOST,
        REMOTE_PYTHON,
        script_path,
        *extra_args,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"remote command failed ({proc.returncode}): {stderr or stdout or 'no output'}")
    try:
        return json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"remote command returned non-JSON output: {stdout[:400]}") from exc


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


def build_lookup_args(target_key: str, target_value: str) -> list[str]:
    if target_key == "lemma_id":
        return ["--lemma-id", target_value]
    return ["--headword", target_value]


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
            get_args = ["get", "--json", *build_lookup_args(target_key, target_value)]
            result = run_remote(REMOTE_SERVICE, get_args, timeout=120)
            emit_json(200, {"ok": True, "result": result})
            return

        remote_user = (os.environ.get("REMOTE_USER") or "").strip()
        if not remote_user:
            emit_json(403, {"ok": False, "error": "Authenticated user required for canonical updates"})
            return

        action = (params.get("action") or "set").strip().lower()
        if action != "set":
            emit_json(400, {"ok": False, "error": "Unsupported action"})
            return

        target_key, target_value = require_target(params)
        set_args = ["set", "--json", *build_lookup_args(target_key, target_value)]

        translation_text = (params.get("translation_text") or "").strip()
        if translation_text:
            set_args.extend(["--translation-text", translation_text])
        else:
            variant_kind = (params.get("variant_kind") or "").strip()
            variant_id = (params.get("variant_id") or "").strip()
            if not variant_kind or not variant_id:
                emit_json(
                    400,
                    {
                        "ok": False,
                        "error": "Provide translation_text or (variant_kind and variant_id)",
                    },
                )
                return
            set_args.extend(["--variant-kind", variant_kind, "--variant-id", variant_id])

        source_text_version_id = (params.get("source_text_version_id") or "").strip()
        if source_text_version_id:
            if not source_text_version_id.isdigit():
                emit_json(400, {"ok": False, "error": "source_text_version_id must be an integer"})
                return
            set_args.extend(["--source-text-version-id", source_text_version_id])

        updated_by = (params.get("updated_by") or remote_user).strip()
        set_args.extend(["--updated-by", updated_by])

        notes = (params.get("notes") or "").strip()
        if notes:
            set_args.extend(["--notes", notes])

        set_result = run_remote(REMOTE_SERVICE, set_args, timeout=180)

        publish_raw = (params.get("publish") or "1").strip().lower()
        should_publish = publish_raw not in {"0", "false", "no", "off"}
        publish_result = None
        if should_publish:
            publish_result = run_remote(
                REMOTE_PUBLISH,
                ["--json", "--triggered-by", updated_by],
                timeout=600,
            )

        get_args = ["get", "--json", *build_lookup_args(target_key, target_value)]
        current_result = run_remote(REMOTE_SERVICE, get_args, timeout=120)

        emit_json(
            200,
            {
                "ok": True,
                "updated_by": updated_by,
                "set_result": set_result,
                "publish_result": publish_result,
                "current_result": current_result,
            },
        )
    except subprocess.TimeoutExpired as exc:
        emit_json(502, {"ok": False, "error": f"remote command timed out: {exc}"})
    except Exception as exc:
        emit_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
