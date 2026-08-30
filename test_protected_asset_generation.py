import os
from pathlib import Path

from cleanup_legacy_protected_assets import cleanup_legacy_assets
from protected_assets import (
    remove_stale_image_assets,
    render_page_scan_links,
    write_asset_manifest,
    write_bytes_if_changed,
)


def test_write_bytes_if_changed_preserves_mtime_for_identical_content(tmp_path):
    target = tmp_path / "image.jpg"
    target.write_bytes(b"same")
    fixed_ns = 1_700_000_000_000_000_000
    os.utime(target, ns=(fixed_ns, fixed_ns))

    assert write_bytes_if_changed(target, b"same") is False
    assert target.stat().st_mtime_ns == fixed_ns

    assert write_bytes_if_changed(target, b"changed") is True
    assert target.read_bytes() == b"changed"


def test_manifest_and_owned_image_cleanup_are_scoped(tmp_path):
    protected = tmp_path / "protected"
    images = protected / "images"
    images.mkdir(parents=True)
    (images / "image_1.jpg").write_bytes(b"keep")
    (images / "stale.jpg").write_bytes(b"remove")
    (protected / "report.png").write_bytes(b"not-owned-by-images-dir")

    removed = remove_stale_image_assets(images, {"image_1.jpg"})
    assert removed == ["stale.jpg"]
    assert (images / "image_1.jpg").exists()
    assert (protected / "report.png").exists()

    assert write_asset_manifest(
        protected,
        image_names={"image_1.jpg"},
        wrapper_names={"image_1.html"},
        legacy_source_names={"old.jpg"},
    ) is True
    assert write_asset_manifest(
        protected,
        image_names={"image_1.jpg"},
        wrapper_names={"image_1.html"},
        legacy_source_names={"old.jpg"},
    ) is False


def _build_cleanup_site(tmp_path: Path, *, reference_legacy: bool) -> Path:
    site = tmp_path / "reference_site"
    protected = site / "protected"
    images = protected / "images"
    images.mkdir(parents=True)
    (images / "image_1.jpg").write_bytes(b"canonical")
    (protected / "image_1.html").write_text(
        '<img src="images/image_1.jpg">', encoding="utf-8"
    )
    (protected / "old.jpg").write_bytes(b"legacy")
    (protected / "old.html").write_text("legacy wrapper", encoding="utf-8")
    write_asset_manifest(
        protected,
        image_names={"image_1.jpg"},
        wrapper_names={"image_1.html"},
        legacy_source_names={"old.jpg"},
    )
    legacy_links = (
        '<a href="protected/old.html">old</a><img src="protected/old.jpg">'
        if reference_legacy
        else ""
    )
    (site / "index.html").write_text(
        f'<a href="protected/image_1.html">canonical</a>{legacy_links}',
        encoding="utf-8",
    )
    return site


def test_legacy_cleanup_removes_only_unreferenced_assets(tmp_path):
    site = _build_cleanup_site(tmp_path, reference_legacy=False)

    dry_run = cleanup_legacy_assets(site)
    assert dry_run["removable"] == ["protected/old.html", "protected/old.jpg"]
    assert (site / "protected/old.jpg").exists()

    applied = cleanup_legacy_assets(site, apply=True)
    assert applied["removed_count"] == 2
    assert not (site / "protected/old.jpg").exists()
    assert not (site / "protected/old.html").exists()
    assert (site / "protected/images/image_1.jpg").exists()


def test_legacy_cleanup_retains_referenced_assets(tmp_path):
    site = _build_cleanup_site(tmp_path, reference_legacy=True)
    report = cleanup_legacy_assets(site, apply=True)

    assert report["removed_count"] == 0
    assert set(report["referenced"]) == {
        "protected/old.html",
        "protected/old.jpg",
    }


def test_reference_site_links_use_canonical_image_id_wrappers():
    links = render_page_scan_links(
        [{"id": 42, "filename": "../graphic/vol1_001.jpg"}]
    )
    assert links == [
        '<a href="protected/image_42.html" target="_blank">'
        "../graphic/vol1_001.jpg</a>"
    ]
