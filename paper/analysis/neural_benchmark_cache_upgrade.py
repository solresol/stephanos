#!/usr/bin/env python3
"""Upgrade the learned-metric benchmark cache by reusing unchanged rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from paper.analysis import neural_benchmark_analysis as neural


DEFAULT_ENTRIES = ROOT / "paper" / "build" / "benchmark_analysis" / "benchmark_entries.csv"
DEFAULT_CELLS = ROOT / "paper" / "build" / "benchmark_analysis" / "benchmark_cells.csv"
DEFAULT_LEGACY_WORK_DIR = ROOT / "paper" / "neural_metrics"
DEFAULT_WORK_DIR = ROOT / "paper" / "neural_metrics_4500"
DEFAULT_SIDECAR = ROOT / "compute_neural_translation_metrics.py"
METRICS = ("comet", "xcomet", "bleurt")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("source") or row.get("source_text") or ""),
        str(row.get("candidate") or row.get("ai_translation_text") or ""),
        str(row.get("reference") or row.get("human_translation_text") or ""),
    )


def load_manifest_inputs(work_dir: Path) -> tuple[dict[str, Any], list[dict[str, object]]]:
    manifest_path = work_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows_by_index: dict[int, dict[str, object]] = {}
    total_rows = 0
    for shard in manifest.get("shards") or []:
        input_path = work_dir / "inputs" / str(shard["name"])
        if file_sha256(input_path) != str(shard["sha256"]):
            raise RuntimeError(f"Input shard hash mismatch: {input_path}")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        rows = list(payload.get("rows") or [])
        if len(rows) != int(shard["row_count"]):
            raise RuntimeError(f"Input shard row-count mismatch: {input_path}")
        total_rows += len(rows)
        for row in rows:
            row_index = int(row["row_index"])
            if row_index in rows_by_index:
                raise RuntimeError(f"Duplicate input row index {row_index}")
            rows_by_index[row_index] = row
    expected_rows = int(manifest.get("row_count") or 0)
    if total_rows != expected_rows or set(rows_by_index) != set(range(expected_rows)):
        raise RuntimeError(
            f"Manifest inputs contain {total_rows} rows but expected a complete 0..{expected_rows - 1} index"
        )
    return manifest, [rows_by_index[index] for index in range(expected_rows)]


def legacy_output_files(work_dir: Path, metric: str) -> list[Path]:
    return sorted((work_dir / "outputs" / metric).glob("output-*.json"))


def load_metric_scores(work_dir: Path, metric: str, expected_rows: int) -> dict[int, float]:
    scores: dict[int, float] = {}
    expected_status = neural.expected_metric_status(metric)
    for path in legacy_output_files(work_dir, metric):
        result = json.loads(path.read_text(encoding="utf-8"))
        status = str(dict(result.get("status") or {}).get(metric) or "")
        if status != expected_status:
            raise RuntimeError(f"{path}: expected status {expected_status!r}, found {status!r}")
        for item in result.get("scores") or []:
            if metric not in item:
                continue
            row_index = int(item["row_index"])
            if row_index in scores:
                raise RuntimeError(f"Duplicate {metric} row index {row_index}")
            value = float(item[metric])
            if not math.isfinite(value):
                raise RuntimeError(f"Non-finite {metric} score at row index {row_index}")
            scores[row_index] = value
    if len(scores) != expected_rows or set(scores) != set(range(expected_rows)):
        missing = sorted(set(range(expected_rows)) - set(scores))[:20]
        raise RuntimeError(
            f"{metric}: expected {expected_rows} legacy scores, found {len(scores)}; missing {missing}"
        )
    return scores


def metric_score_by_content(
    input_rows: list[dict[str, object]],
    scores_by_index: dict[int, float],
    *,
    metric: str,
) -> dict[tuple[str, str, str], float]:
    values_by_content: dict[tuple[str, str, str], list[float]] = {}
    for row in input_rows:
        row_index = int(row["row_index"])
        key = row_key(row)
        score = scores_by_index[row_index]
        values_by_content.setdefault(key, []).append(score)

    scores = {}
    for key, values in values_by_content.items():
        # GPU batches can move the final float32 result by a few ULPs. Identical
        # metric inputs should still agree to within one millionth; average those
        # harmless duplicates, but reject any discrepancy large enough to matter.
        if max(values) - min(values) > 1e-6:
            raise RuntimeError(f"Duplicate content has inconsistent {metric} scores")
        scores[key] = sum(values) / len(values)
    return scores


def output_hashes(work_dir: Path) -> dict[str, dict[str, str]]:
    return {
        metric: {
            str(path.relative_to(work_dir)): file_sha256(path)
            for path in legacy_output_files(work_dir, metric)
        }
        for metric in METRICS
    }


def verify_output_hashes(work_dir: Path, expected: dict[str, object]) -> None:
    actual = output_hashes(work_dir)
    if actual != expected:
        raise RuntimeError("Legacy learned-metric output files changed after upgrade preparation")


def prepare_upgrade(
    *,
    entries_path: Path,
    legacy_work_dir: Path,
    work_dir: Path,
    shard_size: int,
) -> dict[str, object]:
    if (work_dir / "manifest.json").exists():
        raise RuntimeError(f"Upgrade work directory already contains a manifest: {work_dir}")
    legacy_manifest, legacy_inputs = load_manifest_inputs(legacy_work_dir)
    legacy_row_count = int(legacy_manifest["row_count"])
    content_scores = {
        metric: metric_score_by_content(
            legacy_inputs,
            load_metric_scores(legacy_work_dir, metric, legacy_row_count),
            metric=metric,
        )
        for metric in METRICS
    }

    current_entries = read_csv(entries_path)
    neural.prepare(entries_path, work_dir, shard_size)
    refresh_rows = []
    reused_rows = 0
    for row_index, row in enumerate(current_entries):
        key = row_key(row)
        if all(key in content_scores[metric] for metric in METRICS):
            reused_rows += 1
            continue
        refresh_rows.append(
            {
                "row_index": row_index,
                "source": key[0],
                "candidate": key[1],
                "reference": key[2],
            }
        )

    refresh_input = work_dir / "refresh-input.json"
    refresh_input.write_text(
        json.dumps({"rows": refresh_rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "entries_path": str(entries_path),
        "entries_sha256": file_sha256(entries_path),
        "legacy_work_dir": str(legacy_work_dir),
        "legacy_manifest_sha256": file_sha256(legacy_work_dir / "manifest.json"),
        "legacy_row_count": legacy_row_count,
        "legacy_output_hashes": output_hashes(legacy_work_dir),
        "current_row_count": len(current_entries),
        "reused_row_count": reused_rows,
        "refresh_row_count": len(refresh_rows),
        "refresh_row_indexes": [int(row["row_index"]) for row in refresh_rows],
        "refresh_input_sha256": file_sha256(refresh_input),
        "metrics": list(METRICS),
    }
    (work_dir / "upgrade-receipt.json").write_text(
        json.dumps(receipt, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return receipt


def validate_refresh_result(
    result: dict[str, object],
    *,
    metric: str,
    expected_indexes: set[int],
) -> dict[int, float]:
    expected_status = neural.expected_metric_status(metric)
    status = str(dict(result.get("status") or {}).get(metric) or "")
    if status != expected_status:
        raise RuntimeError(f"Expected status {expected_status!r}, found {status!r}")
    scores = {}
    for item in result.get("scores") or []:
        if metric not in item:
            continue
        row_index = int(item["row_index"])
        if row_index in scores:
            raise RuntimeError(f"Duplicate refresh {metric} row index {row_index}")
        score = float(item[metric])
        if not math.isfinite(score):
            raise RuntimeError(f"Non-finite refresh {metric} score at row index {row_index}")
        scores[row_index] = score
    if set(scores) != expected_indexes:
        missing = sorted(expected_indexes - set(scores))[:20]
        extra = sorted(set(scores) - expected_indexes)[:20]
        raise RuntimeError(f"Refresh {metric} index mismatch; missing={missing}, extra={extra}")
    return scores


def score_refresh(
    *,
    work_dir: Path,
    metric: str,
    python_path: Path,
    sidecar_path: Path,
    timeout: int,
) -> None:
    input_path = work_dir / "refresh-input.json"
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    expected_indexes = {int(row["row_index"]) for row in payload.get("rows") or []}
    payload.update(
        {
            "metrics": [metric],
            "use_gpu": False,
            "comet_batch_size": 16,
            "bleurt_batch_size": 16,
            "comet_model": neural.METRIC_MODELS["comet"],
            "xcomet_model": neural.METRIC_MODELS["xcomet"],
            "bleurt_checkpoint": neural.METRIC_MODELS["bleurt"],
        }
    )
    output_dir = work_dir / "refresh_outputs"
    log_dir = work_dir / "refresh_logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(python_path), str(sidecar_path)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        check=False,
        encoding="utf-8",
        env={**os.environ, "TOKENIZERS_PARALLELISM": "false"},
        timeout=timeout,
    )
    (log_dir / f"{metric}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"{metric} sidecar exited {completed.returncode}")
    result = json.loads(completed.stdout)
    validate_refresh_result(result, metric=metric, expected_indexes=expected_indexes)
    result["provenance"] = {
        "refresh_input_sha256": file_sha256(input_path),
        "refresh_row_count": len(expected_indexes),
    }
    destination = output_dir / f"{metric}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    print(json.dumps({"metric": metric, "rows": len(expected_indexes), "output": str(destination)}))


def finalize_upgrade(
    *,
    entries_path: Path,
    cells_path: Path,
    legacy_work_dir: Path,
    work_dir: Path,
) -> None:
    receipt_path = work_dir / "upgrade-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if file_sha256(entries_path) != str(receipt["entries_sha256"]):
        raise RuntimeError("Benchmark entries changed after upgrade preparation")
    if file_sha256(legacy_work_dir / "manifest.json") != str(receipt["legacy_manifest_sha256"]):
        raise RuntimeError("Legacy manifest changed after upgrade preparation")
    verify_output_hashes(legacy_work_dir, dict(receipt["legacy_output_hashes"]))

    current_manifest, current_inputs = load_manifest_inputs(work_dir)
    current_entries = read_csv(entries_path)
    if len(current_inputs) != len(current_entries):
        raise RuntimeError("Current manifest and benchmark entry counts differ")
    for row_index, (input_row, entry_row) in enumerate(zip(current_inputs, current_entries, strict=True)):
        if int(input_row["row_index"]) != row_index or row_key(input_row) != row_key(entry_row):
            raise RuntimeError(f"Current manifest content differs at row {row_index}")

    legacy_manifest, legacy_inputs = load_manifest_inputs(legacy_work_dir)
    legacy_row_count = int(legacy_manifest["row_count"])
    expected_refresh_indexes = {int(value) for value in receipt["refresh_row_indexes"]}
    refresh_input_path = work_dir / "refresh-input.json"
    if file_sha256(refresh_input_path) != str(receipt["refresh_input_sha256"]):
        raise RuntimeError("Refresh input changed after upgrade preparation")

    combined_by_metric: dict[str, dict[int, float]] = {}
    for metric in METRICS:
        legacy_content_scores = metric_score_by_content(
            legacy_inputs,
            load_metric_scores(legacy_work_dir, metric, legacy_row_count),
            metric=metric,
        )
        refresh_path = work_dir / "refresh_outputs" / f"{metric}.json"
        refresh_result = json.loads(refresh_path.read_text(encoding="utf-8"))
        provenance = dict(refresh_result.get("provenance") or {})
        if provenance.get("refresh_input_sha256") != receipt["refresh_input_sha256"]:
            raise RuntimeError(f"{metric} refresh provenance does not match the prepared input")
        refresh_scores = validate_refresh_result(
            refresh_result,
            metric=metric,
            expected_indexes=expected_refresh_indexes,
        )
        combined = {}
        for row_index, row in enumerate(current_entries):
            key = row_key(row)
            if key in legacy_content_scores:
                combined[row_index] = legacy_content_scores[key]
            elif row_index in refresh_scores:
                combined[row_index] = refresh_scores[row_index]
            else:
                raise RuntimeError(f"No {metric} score for current row {row_index}")
        combined_by_metric[metric] = combined

    for metric, combined in combined_by_metric.items():
        output_dir = work_dir / "outputs" / metric
        output_dir.mkdir(parents=True, exist_ok=True)
        for stale in output_dir.glob("output-*.json"):
            stale.unlink()
        for shard in current_manifest["shards"]:
            row_start = int(shard["row_start"])
            row_count = int(shard["row_count"])
            result = {
                "status": {metric: neural.expected_metric_status(metric)},
                "scores": [
                    {"row_index": row_index, metric: combined[row_index]}
                    for row_index in range(row_start, row_start + row_count)
                ],
                "provenance": {
                    "input_sha256": str(shard["sha256"]),
                    "row_start": row_start,
                    "row_count": row_count,
                },
            }
            output_path = output_dir / str(shard["name"]).replace("input-", "output-")
            temporary = output_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            if not neural.valid_output(
                temporary,
                metric,
                row_count,
                expected_input_sha256=str(shard["sha256"]),
                expected_row_start=row_start,
            ):
                raise RuntimeError(f"Generated invalid cache shard: {temporary}")
            temporary.replace(output_path)

    neural.summarize(entries_path, cells_path, work_dir, list(METRICS))
    final_receipt = {
        **receipt,
        "status": "complete",
        "final_manifest_sha256": file_sha256(work_dir / "manifest.json"),
        "final_output_hashes": output_hashes(work_dir),
    }
    (work_dir / "upgrade-receipt.json").write_text(
        json.dumps(final_receipt, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": "complete", "row_count": len(current_entries), "work_dir": str(work_dir)}))


def activate_upgrade(*, legacy_work_dir: Path, work_dir: Path, archive_dir: Path) -> None:
    receipt = json.loads((work_dir / "upgrade-receipt.json").read_text(encoding="utf-8"))
    if receipt.get("status") != "complete":
        raise RuntimeError("Upgrade cache is not complete")
    neural.load_and_validate_manifest(work_dir)
    for metric in METRICS:
        neural.load_metric_scores(work_dir, metric, neural.EXPECTED_ROW_COUNT)
    if archive_dir.exists():
        raise RuntimeError(f"Archive directory already exists: {archive_dir}")
    legacy_work_dir.replace(archive_dir)
    try:
        work_dir.replace(legacy_work_dir)
    except Exception:
        archive_dir.replace(legacy_work_dir)
        raise
    print(json.dumps({"active": str(legacy_work_dir), "archived": str(archive_dir)}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    prepare_parser.add_argument("--legacy-work-dir", type=Path, default=DEFAULT_LEGACY_WORK_DIR)
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    prepare_parser.add_argument("--shard-size", type=int, default=400)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("metric", choices=METRICS)
    score_parser.add_argument("--work-dir", type=Path, required=True)
    score_parser.add_argument("--python", type=Path, required=True)
    score_parser.add_argument("--sidecar", type=Path, required=True)
    score_parser.add_argument("--timeout", type=int, default=43200)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    finalize_parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    finalize_parser.add_argument("--legacy-work-dir", type=Path, default=DEFAULT_LEGACY_WORK_DIR)
    finalize_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)

    activate_parser = subparsers.add_parser("activate")
    activate_parser.add_argument("--legacy-work-dir", type=Path, default=DEFAULT_LEGACY_WORK_DIR)
    activate_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    activate_parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ROOT / "paper" / "build" / "neural_metrics_4400",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare_upgrade(
            entries_path=args.entries,
            legacy_work_dir=args.legacy_work_dir,
            work_dir=args.work_dir,
            shard_size=args.shard_size,
        )
    elif args.command == "score":
        score_refresh(
            work_dir=args.work_dir,
            metric=args.metric,
            python_path=args.python,
            sidecar_path=args.sidecar,
            timeout=args.timeout,
        )
    elif args.command == "finalize":
        finalize_upgrade(
            entries_path=args.entries,
            cells_path=args.cells,
            legacy_work_dir=args.legacy_work_dir,
            work_dir=args.work_dir,
        )
    elif args.command == "activate":
        activate_upgrade(
            legacy_work_dir=args.legacy_work_dir,
            work_dir=args.work_dir,
            archive_dir=args.archive_dir,
        )


if __name__ == "__main__":
    main()
