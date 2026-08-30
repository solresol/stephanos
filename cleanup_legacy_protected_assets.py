#!/usr/bin/env python3
"""Remove unreferenced legacy protected scan assets after canonical generation."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import urllib.parse

from protected_assets import ASSET_MANIFEST, IMAGE_EXTENSIONS


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name.lower() in {"href", "src", "poster", "data"} and value:
                self.urls.append(value)


def _resolve_site_path(source: Path, site_root: Path, raw_url: str) -> str | None:
    parsed = urllib.parse.urlsplit(raw_url)
    if parsed.scheme or parsed.netloc or raw_url.startswith("//"):
        return None
    decoded = urllib.parse.unquote(parsed.path)
    if not decoded:
        return None
    if decoded.startswith("/"):
        relative = PurePosixPath(decoded.lstrip("/"))
    else:
        source_parent = PurePosixPath(source.relative_to(site_root).parent.as_posix())
        relative = source_parent / decoded
    parts = []
    for part in relative.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return PurePosixPath(*parts).as_posix()


def referenced_candidate_paths(site_root: Path, candidates: set[str]) -> set[str]:
    directly_referenced = set()
    candidate_edges: dict[str, set[str]] = {}
    for html_path in site_root.rglob("*.html"):
        parser = _LinkParser()
        try:
            parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        source = html_path.relative_to(site_root).as_posix()
        targets = set()
        for raw_url in parser.urls:
            resolved = _resolve_site_path(html_path, site_root, raw_url)
            if resolved in candidates:
                targets.add(resolved)
        if source in candidates:
            candidate_edges[source] = targets
        else:
            directly_referenced.update(targets)

    # A stale wrapper and its image can reference each other. Treat those as
    # reachable only when a current, non-candidate page links into the island.
    referenced = set(directly_referenced)
    queue = list(directly_referenced)
    while queue:
        source = queue.pop()
        for target in candidate_edges.get(source, set()):
            if target not in referenced:
                referenced.add(target)
                queue.append(target)
    return referenced


def cleanup_legacy_assets(site_root: Path, *, apply: bool = False) -> dict[str, object]:
    protected_dir = site_root / "protected"
    manifest_path = protected_dir / ASSET_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    canonical_paths = {
        f"protected/{path}" for path in manifest.get("image_assets", [])
    } | {
        f"protected/{path}" for path in manifest.get("wrapper_pages", [])
    }
    missing_canonical = sorted(
        path for path in canonical_paths if not (site_root / path).is_file()
    )
    if missing_canonical:
        raise RuntimeError(
            f"Refusing legacy cleanup: {len(missing_canonical)} canonical assets are missing"
        )

    root_images = {
        path
        for path in protected_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }
    legacy_names = {
        Path(name).name for name in manifest.get("legacy_source_names", []) if name
    }
    wrapper_candidates = {
        protected_dir / f"{Path(name).stem}.html" for name in legacy_names
    }
    for path in protected_dir.glob("*.html"):
        relative = path.relative_to(site_root).as_posix()
        if relative in canonical_paths:
            continue
        try:
            prefix = path.read_text(encoding="utf-8", errors="replace")[:12000]
        except OSError:
            continue
        if "Stephanos OCR" in prefix and "image-display" in prefix:
            wrapper_candidates.add(path)
    candidates = root_images | {
        path for path in wrapper_candidates if path.is_file()
    }
    candidate_paths = {
        path.relative_to(site_root).as_posix()
        for path in candidates
        if path.relative_to(site_root).as_posix() not in canonical_paths
    }
    referenced = referenced_candidate_paths(site_root, candidate_paths)
    removable = sorted(candidate_paths - referenced)

    removed = []
    if apply:
        for relative in removable:
            path = site_root / relative
            path.unlink()
            removed.append(relative)

    report = {
        "mode": "apply" if apply else "dry-run",
        "candidate_count": len(candidate_paths),
        "referenced_count": len(referenced),
        "removable_count": len(removable),
        "removed_count": len(removed),
        "referenced": sorted(referenced),
        "removable": removable,
    }
    display_report = {
        key: value
        for key, value in report.items()
        if key not in {"referenced", "removable"}
    }
    display_report["referenced_sample"] = report["referenced"][:20]
    display_report["removable_sample"] = report["removable"][:50]
    print(json.dumps(display_report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path("reference_site"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    cleanup_legacy_assets(args.site_root, apply=args.apply)


if __name__ == "__main__":
    main()
