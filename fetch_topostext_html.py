#!/usr/bin/env python3
"""
Fetch Brady's current ToposText Stephanus HTML into an auditable snapshot.

The production path is Dropbox's shared-link content API with a refresh token
stored outside git under ~/.config/stephanos/. Direct Dropbox shared-link URL
rewrites are kept as an explicit mode for diagnostics only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

DEFAULT_SOURCE_NAME = "topostext_stephanus_html"
DEFAULT_EXPECTED_NAME = "E411StephanusByzGreek.html"
DEFAULT_OUTPUT_DIR = Path("data/topostext_snapshots")
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "stephanos"

DROPBOX_TOKEN_URL = "https://api.dropbox.com/oauth2/token"
DROPBOX_SHARED_LINK_FILE_URL = "https://content.dropboxapi.com/2/sharing/get_shared_link_file"

WORK_241_RE = re.compile(r"<p\s+[^>]*work\s*=\s*['\"]241['\"]", re.IGNORECASE)
PRN_TAG_RE = re.compile(r"<\s*prn\b", re.IGNORECASE)
PLACE_TAG_RE = re.compile(r"<\s*place\b", re.IGNORECASE)


class FetchError(RuntimeError):
    """Raised when the remote source cannot produce a valid ToposText HTML file."""


@dataclass
class FetchResult:
    content: bytes
    source_kind: str
    content_type: str
    original_filename: str
    metadata: dict[str, Any]


@dataclass
class LatestSnapshot:
    id: int
    sha256: str
    local_path: str


def config_path(config_dir: Path, name: str) -> Path:
    return config_dir / name


def read_text_file(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FetchError(f"Missing {label}: {path}") from exc


def read_secret(env_name: str, file_path: Path, *, label: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return read_text_file(file_path, label=label)


def resolve_source_url(args: argparse.Namespace) -> str:
    if args.source_url:
        return args.source_url.strip()

    env_url = os.environ.get("TOPOSTEXT_HTML_SHARED_LINK", "").strip()
    if env_url:
        return env_url

    link_file = args.link_file or os.environ.get("TOPOSTEXT_HTML_LINK_FILE")
    link_path = Path(link_file).expanduser() if link_file else args.config_dir / "topostext-html-link"
    if link_path.exists():
        return read_text_file(link_path, label="ToposText shared-link file")

    raise FetchError(
        "No ToposText source URL configured. Pass --source-url, set "
        "TOPOSTEXT_HTML_SHARED_LINK, or create ~/.config/stephanos/topostext-html-link."
    )


def refresh_dropbox_access_token(config_dir: Path, timeout: int) -> str:
    direct_access_token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    if direct_access_token:
        return direct_access_token

    app_key = read_secret("DROPBOX_APP_KEY", config_path(config_dir, "dropbox-app-key"), label="Dropbox app key")
    app_secret = read_secret(
        "DROPBOX_APP_SECRET",
        config_path(config_dir, "dropbox-app-secret"),
        label="Dropbox app secret",
    )
    refresh_token = read_secret(
        "DROPBOX_REFRESH_TOKEN",
        config_path(config_dir, "dropbox-refresh-token"),
        label="Dropbox refresh token",
    )

    response = requests.post(
        DROPBOX_TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": app_key,
            "client_secret": app_secret,
        },
        timeout=timeout,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise FetchError(f"Dropbox token refresh returned non-JSON HTTP {response.status_code}") from exc
    if not response.ok:
        summary = payload.get("error_summary") or payload.get("error") or response.text[:300]
        raise FetchError(f"Dropbox token refresh failed: {summary}")
    access_token = payload.get("access_token")
    if not access_token:
        raise FetchError("Dropbox token refresh response did not include access_token")
    return str(access_token)


def parse_dropbox_result_header(raw_header: str) -> dict[str, Any]:
    if not raw_header:
        return {}
    try:
        value = json.loads(raw_header)
    except json.JSONDecodeError:
        return {"raw_dropbox_api_result": raw_header}
    return value if isinstance(value, dict) else {"dropbox_api_result": value}


def fetch_dropbox_api(source_url: str, args: argparse.Namespace) -> FetchResult:
    access_token = refresh_dropbox_access_token(args.config_dir, args.timeout)
    api_arg = json.dumps({"url": source_url}, separators=(",", ":"))
    response = requests.post(
        DROPBOX_SHARED_LINK_FILE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Dropbox-API-Arg": api_arg,
        },
        timeout=args.timeout,
    )
    metadata = parse_dropbox_result_header(response.headers.get("dropbox-api-result", ""))
    if not response.ok:
        summary = response.text[:500].replace("\n", " ")
        raise FetchError(f"Dropbox shared-link fetch failed with HTTP {response.status_code}: {summary}")
    original_filename = str(metadata.get("name") or "")
    return FetchResult(
        content=response.content,
        source_kind="dropbox_api",
        content_type=response.headers.get("content-type", ""),
        original_filename=original_filename,
        metadata=metadata,
    )


def fetch_direct_http(source_url: str, args: argparse.Namespace) -> FetchResult:
    response = requests.get(source_url, timeout=args.timeout, allow_redirects=True)
    if not response.ok:
        raise FetchError(f"Direct HTTP fetch failed with HTTP {response.status_code}")
    filename = Path(urlparse(response.url).path).name
    return FetchResult(
        content=response.content,
        source_kind="dropbox_direct_http",
        content_type=response.headers.get("content-type", ""),
        original_filename=filename,
        metadata={"final_url": response.url},
    )


def fetch_local_file(path: Path) -> FetchResult:
    content = path.read_bytes()
    return FetchResult(
        content=content,
        source_kind="local_file",
        content_type="text/html",
        original_filename=path.name,
        metadata={"source_file": str(path)},
    )


def decode_html(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def looks_like_dropbox_viewer(html: str) -> bool:
    prefix = html[:5000].lower()
    return (
        "maestro global-header" in prefix
        or "<title>dropbox</title>" in prefix
        or "window.page_init_data" in prefix
    )


def validate_topostext_html(content: bytes, *, expected_name: str, original_filename: str = "") -> dict[str, bool]:
    html = decode_html(content)
    checks = {
        "not_dropbox_viewer": not looks_like_dropbox_viewer(html),
        "has_work_241": bool(WORK_241_RE.search(html)),
        "has_prn_tags": bool(PRN_TAG_RE.search(html)),
        "has_place_tags": bool(PLACE_TAG_RE.search(html)),
    }
    if expected_name and original_filename and original_filename != expected_name:
        raise FetchError(f"Fetched Dropbox file was {original_filename!r}, expected {expected_name!r}")
    if not checks["not_dropbox_viewer"]:
        raise FetchError("Fetched body is a Dropbox viewer page, not the Stephanus HTML file")
    if not checks["has_work_241"]:
        raise FetchError("Fetched body does not contain expected Stephanus <p work='241'> entries")
    if not checks["has_prn_tags"] or not checks["has_place_tags"]:
        raise FetchError("Fetched body does not contain expected PRN/place entity tags")
    return checks


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_dir_name(moment: datetime) -> str:
    return moment.strftime("%Y%m%d-%H%M%SZ")


def load_latest_snapshot(cur, source_name: str) -> LatestSnapshot | None:
    cur.execute(
        """
        SELECT id, sha256, local_path
        FROM entity_source_snapshots
        WHERE source_name = %s
          AND status = 'fetched'
          AND sha256 IS NOT NULL
        ORDER BY fetched_at DESC, id DESC
        LIMIT 1
        """,
        (source_name,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return LatestSnapshot(id=int(row[0]), sha256=str(row[1]), local_path=str(row[2] or ""))


def snapshot_file_exists(local_path: str, *, base_dir: Path | None = None) -> bool:
    if not local_path:
        return False
    path = Path(local_path).expanduser()
    if not path.is_absolute():
        path = (base_dir or Path.cwd()) / path
    return path.exists()


def insert_snapshot_row(
    cur,
    *,
    source_name: str,
    source_kind: str,
    source_uri: str,
    expected_name: str,
    status: str,
    local_path: str | None,
    original_filename: str,
    content_type: str,
    byte_count: int,
    digest: str,
    unchanged_from_snapshot_id: int | None,
    metadata: dict[str, Any],
    error_message: str | None = None,
) -> int:
    cur.execute(
        """
        INSERT INTO entity_source_snapshots (
            source_name,
            source_kind,
            source_uri,
            expected_name,
            status,
            local_path,
            original_filename,
            content_type,
            byte_count,
            sha256,
            unchanged_from_snapshot_id,
            metadata,
            error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            source_name,
            source_kind,
            source_uri,
            expected_name,
            status,
            local_path,
            original_filename,
            content_type,
            byte_count,
            digest,
            unchanged_from_snapshot_id,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            error_message,
        ),
    )
    return int(cur.fetchone()[0])


def write_snapshot_files(
    *,
    output_dir: Path,
    expected_name: str,
    content: bytes,
    metadata: dict[str, Any],
    moment: datetime,
) -> Path:
    base_snapshot_dir = output_dir / timestamp_dir_name(moment)
    snapshot_dir = base_snapshot_dir
    for counter in range(100):
        if counter:
            snapshot_dir = output_dir / f"{base_snapshot_dir.name}-{counter}"
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise FetchError(f"Could not allocate unique snapshot directory under {output_dir}")
    html_path = snapshot_dir / expected_name
    html_path.write_bytes(content)
    (snapshot_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return html_path


def build_file_metadata(
    *,
    args: argparse.Namespace,
    source_url: str,
    fetch_result: FetchResult,
    digest: str,
    validation: dict[str, bool],
    fetched_at: datetime,
) -> dict[str, Any]:
    uri_parts = urlparse(source_url)
    return {
        "byte_count": len(fetch_result.content),
        "content_type": fetch_result.content_type,
        "expected_name": args.expected_name,
        "fetched_at": fetched_at.isoformat(),
        "original_filename": fetch_result.original_filename,
        "sha256": digest,
        "source_host": uri_parts.netloc,
        "source_kind": fetch_result.source_kind,
        "source_name": args.source_name,
        "source_uri_sha256": sha256_bytes(source_url.encode("utf-8")),
        "validation": validation,
        "remote_metadata": fetch_result.metadata,
    }


def print_summary(*, status: str, snapshot_id: int | None, digest: str, byte_count: int, path: str | None = None):
    print(f"status={status}")
    if snapshot_id is not None:
        print(f"snapshot_id={snapshot_id}")
    if path:
        print(f"path={path}")
    print(f"bytes={byte_count}")
    print(f"sha256={digest}")


def fetch_content(args: argparse.Namespace) -> tuple[str, FetchResult]:
    if args.fetch_mode == "local_file":
        if not args.source_file:
            raise FetchError("--source-file is required with --fetch-mode local_file")
        source_path = Path(args.source_file).expanduser()
        return str(source_path), fetch_local_file(source_path)

    source_url = resolve_source_url(args)
    if args.fetch_mode in {"dropbox_api", "dropbox_shared_link"}:
        return source_url, fetch_dropbox_api(source_url, args)
    if args.fetch_mode == "dropbox_direct_http":
        return source_url, fetch_direct_http(source_url, args)
    raise FetchError(f"Unsupported fetch mode: {args.fetch_mode}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Brady's ToposText Stephanus HTML snapshot.")
    parser.add_argument("--source-url", help="Dropbox shared link or direct HTTP source URL")
    parser.add_argument("--source-file", help="Local HTML file path when --fetch-mode local_file is used")
    parser.add_argument("--link-file", help="File containing the Dropbox shared link")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-name", default=DEFAULT_EXPECTED_NAME)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument(
        "--fetch-mode",
        choices=["dropbox_api", "dropbox_shared_link", "dropbox_direct_http", "local_file"],
        default=os.environ.get("TOPOSTEXT_HTML_FETCH_MODE", "dropbox_api"),
    )
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing files or DB rows")
    parser.add_argument("--skip-db", action="store_true", help="Write snapshot files without recording DB metadata")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.config_dir = args.config_dir.expanduser()
    args.output_dir = args.output_dir.expanduser()

    try:
        source_uri, fetch_result = fetch_content(args)
        digest = sha256_bytes(fetch_result.content)
        validation = validate_topostext_html(
            fetch_result.content,
            expected_name=args.expected_name,
            original_filename=fetch_result.original_filename,
        )
        fetched_at = now_utc()
        metadata = build_file_metadata(
            args=args,
            source_url=source_uri,
            fetch_result=fetch_result,
            digest=digest,
            validation=validation,
            fetched_at=fetched_at,
        )

        if args.dry_run:
            print_summary(status="dry_run", snapshot_id=None, digest=digest, byte_count=len(fetch_result.content))
            return 0

        conn = None
        latest = None
        if not args.skip_db:
            from db import get_connection

            conn = get_connection()
            cur = conn.cursor()
            latest = load_latest_snapshot(cur, args.source_name)

        if latest is not None and latest.sha256 == digest and snapshot_file_exists(latest.local_path):
            snapshot_id = None
            if conn is not None:
                snapshot_id = insert_snapshot_row(
                    cur,
                    source_name=args.source_name,
                    source_kind=fetch_result.source_kind,
                    source_uri=source_uri,
                    expected_name=args.expected_name,
                    status="unchanged",
                    local_path=latest.local_path,
                    original_filename=fetch_result.original_filename,
                    content_type=fetch_result.content_type,
                    byte_count=len(fetch_result.content),
                    digest=digest,
                    unchanged_from_snapshot_id=latest.id,
                    metadata=metadata,
                )
                conn.commit()
                conn.close()
            print_summary(
                status="unchanged",
                snapshot_id=snapshot_id,
                digest=digest,
                byte_count=len(fetch_result.content),
                path=latest.local_path,
            )
            return 0

        materialized_from_snapshot_id = latest.id if latest is not None and latest.sha256 == digest else None
        html_path = write_snapshot_files(
            output_dir=args.output_dir,
            expected_name=args.expected_name,
            content=fetch_result.content,
            metadata=metadata,
            moment=fetched_at,
        )

        snapshot_id = None
        if conn is not None:
            snapshot_id = insert_snapshot_row(
                cur,
                source_name=args.source_name,
                source_kind=fetch_result.source_kind,
                source_uri=source_uri,
                expected_name=args.expected_name,
                status="fetched",
                local_path=str(html_path),
                original_filename=fetch_result.original_filename,
                content_type=fetch_result.content_type,
                byte_count=len(fetch_result.content),
                digest=digest,
                unchanged_from_snapshot_id=materialized_from_snapshot_id,
                metadata=metadata,
            )
            conn.commit()
            conn.close()

        print_summary(
            status="fetched",
            snapshot_id=snapshot_id,
            digest=digest,
            byte_count=len(fetch_result.content),
            path=str(html_path),
        )
        return 0
    except FetchError as exc:
        print(f"fetch_topostext_html: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
