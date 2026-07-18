#!/usr/bin/env python3
"""Score the retained expert revision pairs with XCOMET-XL."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
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

DEFAULT_ENTRIES = ROOT / "paper" / "build" / "benchmark_analysis" / "benchmark_entries.csv"
DEFAULT_CELLS = ROOT / "paper" / "build" / "benchmark_analysis" / "neural_benchmark_cells.csv"
DEFAULT_BENCHMARK_ROWS = (
    ROOT / "paper" / "build" / "benchmark_analysis" / "neural_benchmark_rows.csv"
)
DEFAULT_BUILD_DIR = ROOT / "paper" / "build" / "benchmark_analysis"
DEFAULT_WORK_DIR = ROOT / "paper" / "neural_metrics" / "human_revision"
DEFAULT_SIDECAR = ROOT / "compute_neural_translation_metrics.py"
MODEL_NAME = "Unbabel/XCOMET-XL"
EXPECTED_STATUS = f"sidecar {MODEL_NAME}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_score(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def prepare(entries_path: Path, work_dir: Path) -> None:
    os.environ.setdefault("DB_HOST", "raksasa")
    os.environ.setdefault("DB_USER", "stephanos")
    from db import get_connection

    references = {
        int(row["lemma_id"]): {
            "lemma": row["lemma"],
            "source": row["source_text"],
            "reference": row["human_translation_text"],
        }
        for row in read_csv(entries_path)
    }
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT ON (lemma_id)
            lemma_id,
            translation_text,
            COALESCE(created_by, '') AS created_by
        FROM human_translations
        WHERE lemma_id = ANY(%s)
          AND stage = 'initial'
          AND NULLIF(BTRIM(translation_text), '') IS NOT NULL
        ORDER BY lemma_id,
                 COALESCE(updated_at, reviewed_at, created_at) DESC,
                 id DESC
        """,
        (sorted(references),),
    )
    initial_rows = list(cur.fetchall())
    cur.close()
    conn.close()

    pairs: list[dict[str, object]] = []
    for row in initial_rows:
        lemma_id = int(row["lemma_id"])
        reference = references.get(lemma_id)
        if not reference:
            continue
        pairs.append(
            {
                "row_index": len(pairs),
                "lemma_id": lemma_id,
                "lemma": reference["lemma"],
                "created_by": str(row["created_by"] or "(unknown)"),
                "source": reference["source"],
                "candidate": str(row["translation_text"]),
                "reference": reference["reference"],
            }
        )
    if len(pairs) != 79:
        raise RuntimeError(f"Expected 79 retained expert revision pairs, found {len(pairs)}")
    indexes = [int(row["row_index"]) for row in pairs]
    if indexes != list(range(79)):
        raise RuntimeError("Human revision row indexes are not exactly 0-78")

    work_dir.mkdir(parents=True, exist_ok=True)
    pairs_path = work_dir / "pairs.csv"
    input_path = work_dir / "input.json"
    write_csv(pairs_path, pairs)
    input_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "row_index": row["row_index"],
                        "source": row["source"],
                        "candidate": row["candidate"],
                        "reference": row["reference"],
                    }
                    for row in pairs
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "comparison": "stored initial expert draft against approved reviewed translation",
        "entries_csv": str(entries_path),
        "entries_sha256": file_sha256(entries_path),
        "pairs_sha256": file_sha256(pairs_path),
        "input_sha256": file_sha256(input_path),
        "row_count": len(pairs),
        "model": MODEL_NAME,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"work_dir": str(work_dir), **manifest}, indent=2))


def load_manifest(work_dir: Path) -> dict[str, Any]:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    if int(manifest.get("row_count") or 0) != 79:
        raise RuntimeError(f"Manifest row count is not 79: {manifest.get('row_count')}")
    if manifest.get("model") != MODEL_NAME:
        raise RuntimeError(f"Manifest model is not {MODEL_NAME}")
    input_path = work_dir / "input.json"
    pairs_path = work_dir / "pairs.csv"
    if file_sha256(input_path) != manifest.get("input_sha256"):
        raise RuntimeError("Human revision input hash does not match manifest")
    if file_sha256(pairs_path) != manifest.get("pairs_sha256"):
        raise RuntimeError("Human revision pair hash does not match manifest")
    return manifest


def validate_output(path: Path, manifest: dict[str, Any]) -> dict[int, float]:
    result = json.loads(path.read_text(encoding="utf-8"))
    status = str(dict(result.get("status") or {}).get("xcomet") or "")
    if status != EXPECTED_STATUS:
        raise RuntimeError(f"Expected XCOMET status {EXPECTED_STATUS!r}, found {status!r}")
    provenance = dict(result.get("provenance") or {})
    if provenance.get("input_sha256") != manifest["input_sha256"]:
        raise RuntimeError("XCOMET output input hash does not match manifest")
    if int(provenance.get("row_count") or 0) != int(manifest["row_count"]):
        raise RuntimeError("XCOMET output row count provenance does not match manifest")
    scores: dict[int, float] = {}
    for item in result.get("scores") or []:
        if "xcomet" not in item:
            continue
        row_index = int(item["row_index"])
        if row_index in scores:
            raise RuntimeError(f"Duplicate XCOMET row index {row_index}")
        value = finite_score(item["xcomet"])
        if value is None:
            raise RuntimeError(f"Non-finite XCOMET score at row index {row_index}")
        scores[row_index] = value
    expected_indexes = set(range(int(manifest["row_count"])))
    if set(scores) != expected_indexes:
        missing = sorted(expected_indexes - set(scores))
        extra = sorted(set(scores) - expected_indexes)
        raise RuntimeError(f"XCOMET indexes are incomplete; missing={missing}, extra={extra}")
    return scores


def run(work_dir: Path, sidecar_path: Path, timeout: int) -> None:
    manifest = load_manifest(work_dir)
    output_path = work_dir / "output.json"
    if output_path.exists():
        validate_output(output_path, manifest)
        print(f"Retained validated {output_path} with {manifest['row_count']} scores")
        return
    payload = json.loads((work_dir / "input.json").read_text(encoding="utf-8"))
    payload.update(
        {
            "metrics": ["xcomet"],
            "use_gpu": False,
            "comet_batch_size": 16,
            "xcomet_model": MODEL_NAME,
        }
    )
    completed = subprocess.run(
        [sys.executable, str(sidecar_path)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        check=False,
        encoding="utf-8",
        env={**os.environ, "TOKENIZERS_PARALLELISM": "false"},
        timeout=timeout,
    )
    (work_dir / "xcomet.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"XCOMET exited {completed.returncode}; see xcomet.stderr.log")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"XCOMET returned invalid JSON: {completed.stdout[-1000:]}") from exc
    result["provenance"] = {
        "input_sha256": manifest["input_sha256"],
        "row_count": manifest["row_count"],
        "model": MODEL_NAME,
    }
    temporary_path = output_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    validate_output(temporary_path, manifest)
    temporary_path.replace(output_path)
    print(f"Completed validated {output_path} with {manifest['row_count']} scores")


def matched_openai_analysis(
    human_rows: list[dict[str, object]],
    benchmark_rows_path: Path,
    cells_path: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    import numpy as np
    from scipy import stats

    human_by_lemma = {int(row["lemma_id"]): float(row["xcomet"]) for row in human_rows}
    benchmark_rows = read_csv(benchmark_rows_path)
    cell_metadata = {
        (row["profile_name"], int(row["prompt_version"])): row
        for row in read_csv(cells_path)
        if row["provider"] == "OpenAI"
    }
    grouped: dict[tuple[str, int], list[float]] = {}
    latest_by_prompt: dict[int, dict[int, float]] = {2: {}, 3: {}}
    for row in benchmark_rows:
        prompt_version = int(row["prompt_version"])
        lemma_id = int(row["lemma_id"])
        if (
            row["provider"] != "OpenAI"
            or prompt_version not in (2, 3)
            or lemma_id not in human_by_lemma
        ):
            continue
        key = (row["profile_name"], prompt_version)
        grouped.setdefault(key, []).append(float(row["xcomet"]))
        if row["profile_name"] == "gpt-5.6-sol":
            latest_by_prompt[prompt_version][lemma_id] = float(row["xcomet"])

    subset_cells = []
    for key, values in grouped.items():
        metadata = cell_metadata[key]
        if len(values) != len(human_by_lemma):
            raise RuntimeError(
                f"Expected {len(human_by_lemma)} matched entries for {key}, found {len(values)}"
            )
        subset_cells.append(
            {
                "profile_name": key[0],
                "prompt_version": key[1],
                "release_date": metadata["release_date"],
                "pair_count": len(values),
                "mean_xcomet": float(np.mean(values)),
            }
        )
    if len(subset_cells) != 24:
        raise RuntimeError(f"Expected 24 matched OpenAI v2/v3 cells, found {len(subset_cells)}")

    latest_comparisons: dict[str, object] = {}
    trends: dict[str, object] = {}
    human_order = sorted(human_by_lemma)
    for prompt_version in (2, 3):
        model_by_lemma = latest_by_prompt[prompt_version]
        if set(model_by_lemma) != set(human_by_lemma):
            raise RuntimeError(f"GPT-5.6 v{prompt_version} matched-entry set is incomplete")
        differences = np.asarray(
            [model_by_lemma[lemma_id] - human_by_lemma[lemma_id] for lemma_id in human_order],
            dtype=float,
        )
        difference_ci = stats.t.interval(
            0.95,
            df=len(differences) - 1,
            loc=float(differences.mean()),
            scale=float(stats.sem(differences)),
        )
        correlation = stats.pearsonr(
            [human_by_lemma[lemma_id] for lemma_id in human_order],
            [model_by_lemma[lemma_id] for lemma_id in human_order],
        )
        latest_comparisons[f"v{prompt_version}"] = {
            "profile_name": "gpt-5.6-sol",
            "pair_count": len(differences),
            "human_revision_mean_xcomet": float(
                np.mean([human_by_lemma[lemma_id] for lemma_id in human_order])
            ),
            "model_mean_xcomet": float(
                np.mean([model_by_lemma[lemma_id] for lemma_id in human_order])
            ),
            "paired_model_minus_human_mean": float(differences.mean()),
            "paired_difference_ci_low": float(difference_ci[0]),
            "paired_difference_ci_high": float(difference_ci[1]),
            "paired_t_p_value": float(stats.ttest_1samp(differences, popmean=0.0).pvalue),
            "entry_score_pearson_r": float(correlation.statistic),
            "entry_score_pearson_p_value": float(correlation.pvalue),
        }

        prompt_cells = sorted(
            [row for row in subset_cells if row["prompt_version"] == prompt_version],
            key=lambda row: row["release_date"],
        )
        first_date = date.fromisoformat(str(prompt_cells[0]["release_date"]))
        x = np.asarray(
            [
                (date.fromisoformat(str(row["release_date"])) - first_date).days
                for row in prompt_cells
            ],
            dtype=float,
        )
        y = np.asarray([float(row["mean_xcomet"]) for row in prompt_cells], dtype=float)
        fit = stats.linregress(x, y)
        if fit.slope <= 0:
            raise RuntimeError(f"Prompt v{prompt_version} matched XCOMET slope is not positive")
        target = float(np.mean([human_by_lemma[lemma_id] for lemma_id in human_order]))
        crossing = first_date + timedelta(days=float((target - fit.intercept) / fit.slope))
        trends[f"v{prompt_version}"] = {
            "model_count": len(prompt_cells),
            "slope_per_year": float(fit.slope * 365.25),
            "r2": float(fit.rvalue**2),
            "p_value": float(fit.pvalue),
            "human_revision_mean_crossing_date": crossing.isoformat(),
        }
    return subset_cells, {"latest_gpt_5_6": latest_comparisons, "release_trends": trends}


def summarize(
    work_dir: Path,
    build_dir: Path,
    cells_path: Path,
    benchmark_rows_path: Path,
) -> None:
    import numpy as np
    from scipy import stats

    manifest = load_manifest(work_dir)
    scores = validate_output(work_dir / "output.json", manifest)
    pairs = read_csv(work_dir / "pairs.csv")
    rows = [
        {
            "row_index": int(row["row_index"]),
            "lemma_id": int(row["lemma_id"]),
            "lemma": row["lemma"],
            "created_by": row["created_by"],
            "xcomet": scores[int(row["row_index"])],
        }
        for row in pairs
    ]
    values = np.asarray([float(row["xcomet"]) for row in rows], dtype=float)
    confidence_interval = stats.t.interval(
        0.95,
        df=len(values) - 1,
        loc=float(values.mean()),
        scale=float(stats.sem(values)),
    )
    mean_score = float(values.mean())
    subset_cells, matched_openai = matched_openai_analysis(rows, benchmark_rows_path, cells_path)
    result = {
        "comparison": manifest["comparison"],
        "pair_count": len(rows),
        "model": MODEL_NAME,
        "status": EXPECTED_STATUS,
        "finite_score_count": int(np.isfinite(values).sum()),
        "unique_row_index_count": len({int(row["row_index"]) for row in rows}),
        "mean_xcomet": mean_score,
        "mean_xcomet_ci_low": float(confidence_interval[0]),
        "mean_xcomet_ci_high": float(confidence_interval[1]),
        "median_xcomet": float(np.median(values)),
        "standard_deviation": float(values.std(ddof=1)),
        "minimum_xcomet": float(values.min()),
        "maximum_xcomet": float(values.max()),
        "matched_entry_openai": matched_openai,
        "interpretation": (
            "Within-workflow expert revision stability benchmark; not independent "
            "inter-translator agreement or a human-performance ceiling."
        ),
    }
    write_csv(build_dir / "human_revision_neural_rows.csv", rows)
    write_csv(build_dir / "human_revision_openai_subset_cells.csv", subset_cells)
    (build_dir / "human_revision_neural_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run_parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    run_parser.add_argument("--timeout", type=int, default=21600)

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    summarize_parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    summarize_parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    summarize_parser.add_argument(
        "--benchmark-rows", type=Path, default=DEFAULT_BENCHMARK_ROWS
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.entries, args.work_dir)
    elif args.command == "run":
        run(args.work_dir, args.sidecar, args.timeout)
    elif args.command == "summarize":
        summarize(args.work_dir, args.build_dir, args.cells, args.benchmark_rows)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
