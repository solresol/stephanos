"""Shared helpers for canonical protected scan assets."""

from __future__ import annotations

import html
import json
from pathlib import Path


IMAGES_SUBDIR = "images"
ASSET_MANIFEST = "assets-manifest.json"
IMAGE_EXTENSIONS = {".jpg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}


def render_page_scan_links(image_references: list[dict[str, object]]) -> list[str]:
    """Render links to the canonical ID-named protected image wrappers."""
    links = []
    for reference in image_references:
        try:
            image_id = int(reference.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if image_id <= 0:
            continue
        filename = str(reference.get("filename") or f"image {image_id}")
        links.append(
            f'<a href="protected/image_{image_id}.html" target="_blank">'
            f"{html.escape(filename)}</a>"
        )
    return links


def write_bytes_if_changed(path: Path, content: bytes) -> bool:
    """Write content only when bytes differ, preserving mtimes for stable assets."""
    payload = bytes(content)
    if path.exists() and path.stat().st_size == len(payload):
        if path.read_bytes() == payload:
            return False
    path.write_bytes(payload)
    return True


def write_text_if_changed(path: Path, content: str) -> bool:
    return write_bytes_if_changed(path, content.encode("utf-8"))


def remove_stale_image_assets(images_dir: Path, expected_names: set[str]) -> list[str]:
    """Remove stale files only from the generator-owned protected/images tree."""
    removed = []
    for path in images_dir.iterdir():
        if path.is_file() and path.name not in expected_names:
            path.unlink()
            removed.append(path.name)
    return sorted(removed)


def remove_stale_headword_pages(output_dir: Path, expected_names: set[str]) -> list[str]:
    """Remove only obsolete generator-owned headword_<id>.html pages."""
    removed = []
    for path in output_dir.glob("headword_*.html"):
        if path.is_file() and path.name not in expected_names:
            path.unlink()
            removed.append(path.name)
    return sorted(removed)


def write_asset_manifest(
    output_dir: Path,
    *,
    image_names: set[str],
    wrapper_names: set[str],
    legacy_source_names: set[str],
) -> bool:
    manifest = {
        "schema_version": 1,
        "canonical_image_directory": IMAGES_SUBDIR,
        "image_assets": [f"{IMAGES_SUBDIR}/{name}" for name in sorted(image_names)],
        "wrapper_pages": sorted(wrapper_names),
        "legacy_source_names": sorted(legacy_source_names),
    }
    return write_text_if_changed(
        output_dir / ASSET_MANIFEST,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
