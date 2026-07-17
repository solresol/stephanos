#!/usr/bin/env python3
"""Prepare, run, validate, and summarize neural benchmark metrics."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_BUILD_DIR = ROOT / "paper" / "build" / "benchmark_analysis"
DEFAULT_ENTRIES = DEFAULT_BUILD_DIR / "benchmark_entries.csv"
DEFAULT_CELLS = DEFAULT_BUILD_DIR / "benchmark_cells.csv"
DEFAULT_WORK_DIR = ROOT / "paper" / "neural_metrics"
METRIC_LABELS = {
    "comet": "COMET-22",
    "xcomet": "XCOMET-XL",
    "bleurt": "BLEURT-20",
}
METRIC_MODELS = {
    "comet": "Unbabel/wmt22-comet-da",
    "xcomet": "Unbabel/XCOMET-XL",
    "bleurt": "/home/stephanos/metric-envs/bleurt/BLEURT-20",
}


def expected_metric_status(metric: str) -> str:
    model = METRIC_MODELS[metric]
    if metric == "bleurt":
        return f"sidecar BLEURT checkpoint {model}"
    return f"sidecar {model}"


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


def load_and_validate_manifest(work_dir: Path) -> dict[str, Any]:
    manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    if int(manifest.get("row_count") or 0) != 4400:
        raise RuntimeError(f"Manifest row count is not 4,400: {manifest.get('row_count')}")
    if int(manifest.get("cell_count") or 0) != 44:
        raise RuntimeError(f"Manifest cell count is not 44: {manifest.get('cell_count')}")
    if dict(manifest.get("metric_models") or {}) != METRIC_MODELS:
        raise RuntimeError("Manifest metric model definitions do not match the current runner")
    total_rows = 0
    for shard in manifest.get("shards") or []:
        input_path = work_dir / "inputs" / str(shard["name"])
        if not input_path.exists():
            raise RuntimeError(f"Missing neural input shard: {input_path}")
        actual_hash = file_sha256(input_path)
        if actual_hash != shard["sha256"]:
            raise RuntimeError(f"Input shard hash mismatch: {input_path}")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if len(payload.get("rows") or []) != int(shard["row_count"]):
            raise RuntimeError(f"Input shard row-count mismatch: {input_path}")
        total_rows += int(shard["row_count"])
    if total_rows != int(manifest["row_count"]):
        raise RuntimeError(f"Manifest shards contain {total_rows} rows, not {manifest['row_count']}")
    return manifest


def prepare(entries_path: Path, work_dir: Path, shard_size: int) -> None:
    rows = read_csv(entries_path)
    if len(rows) != 4400:
        raise RuntimeError(f"Expected 4,400 benchmark rows, found {len(rows)}")
    cells = {(row["profile_name"], row["prompt_version"]) for row in rows}
    if len(cells) != 44:
        raise RuntimeError(f"Expected 44 benchmark cells, found {len(cells)}")

    input_dir = work_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    for stale in input_dir.glob("input-*.json"):
        stale.unlink()
    shards = []
    for shard_index, start in enumerate(range(0, len(rows), shard_size)):
        selected = rows[start : start + shard_size]
        payload_rows = [
            {
                "row_index": start + offset,
                "source": row["source_text"],
                "candidate": row["ai_translation_text"],
                "reference": row["human_translation_text"],
            }
            for offset, row in enumerate(selected)
        ]
        path = input_dir / f"input-{shard_index:03d}.json"
        path.write_text(json.dumps({"rows": payload_rows}, ensure_ascii=False), encoding="utf-8")
        shards.append(
            {
                "name": path.name,
                "row_start": start,
                "row_count": len(selected),
                "sha256": file_sha256(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "entries_csv": str(entries_path),
        "entries_sha256": file_sha256(entries_path),
        "row_count": len(rows),
        "cell_count": len(cells),
        "shard_size": shard_size,
        "shards": shards,
        "metric_models": METRIC_MODELS,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"work_dir": str(work_dir), **manifest}, indent=2))


def valid_output(
    path: Path,
    metric: str,
    expected_rows: int,
    *,
    expected_input_sha256: str,
    expected_row_start: int,
) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        provenance = dict(result.get("provenance") or {})
        status = str(dict(result.get("status") or {}).get(metric) or "")
        scores = [item for item in result.get("scores") or [] if metric in item]
        row_indexes = [int(item["row_index"]) for item in scores]
        values = [finite_score(item[metric]) for item in scores]
        provenance_input_sha256 = str(provenance.get("input_sha256") or "")
        provenance_row_start = int(provenance.get("row_start", -1))
        provenance_row_count = int(provenance.get("row_count", -1))
    except (OSError, json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError):
        return False
    expected_indexes = set(range(expected_row_start, expected_row_start + expected_rows))
    return (
        status == expected_metric_status(metric)
        and len(scores) == expected_rows
        and len(row_indexes) == len(set(row_indexes))
        and set(row_indexes) == expected_indexes
        and all(value is not None for value in values)
        and provenance_input_sha256 == expected_input_sha256
        and provenance_row_start == expected_row_start
        and provenance_row_count == expected_rows
    )


def finite_score(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def run_metric(
    metric: str,
    work_dir: Path,
    python_path: Path,
    sidecar_path: Path,
    *,
    timeout: int,
    reverse: bool,
) -> None:
    manifest = load_and_validate_manifest(work_dir)
    output_dir = work_dir / "outputs" / metric
    log_dir = work_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    shards = list(manifest["shards"])
    if reverse:
        shards.reverse()
    for shard in shards:
        input_path = work_dir / "inputs" / shard["name"]
        output_path = output_dir / shard["name"].replace("input-", "output-")
        if valid_output(
            output_path,
            metric,
            int(shard["row_count"]),
            expected_input_sha256=str(shard["sha256"]),
            expected_row_start=int(shard["row_start"]),
        ):
            completed += int(shard["row_count"])
            print(f"{metric}: retained {output_path.name}; {completed}/{manifest['row_count']}", flush=True)
            continue
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "metrics": [metric],
                "use_gpu": False,
                "comet_batch_size": 16,
                "bleurt_batch_size": 16,
                "comet_model": METRIC_MODELS["comet"],
                "xcomet_model": METRIC_MODELS["xcomet"],
                "bleurt_checkpoint": METRIC_MODELS["bleurt"],
            }
        )
        print(f"{metric}: scoring {input_path.name}", flush=True)
        env = dict(os.environ)
        env["TOKENIZERS_PARALLELISM"] = "false"
        completed_process = subprocess.run(
            [str(python_path), str(sidecar_path)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=env,
            timeout=timeout,
        )
        log_path = log_dir / f"{metric}-{input_path.stem}.stderr.log"
        log_path.write_text(completed_process.stderr, encoding="utf-8")
        if completed_process.returncode != 0:
            raise RuntimeError(
                f"{metric} {input_path.name} exited {completed_process.returncode}; see {log_path}"
            )
        try:
            scored_result = json.loads(completed_process.stdout)
        except json.JSONDecodeError as exc:
            detail = completed_process.stdout[-1000:]
            raise RuntimeError(
                f"{metric} {input_path.name} returned invalid JSON: {detail}"
            ) from exc
        if not isinstance(scored_result, dict):
            raise RuntimeError(f"{metric} {input_path.name} returned a non-object JSON value")
        scored_result["provenance"] = {
            "input_sha256": str(shard["sha256"]),
            "row_start": int(shard["row_start"]),
            "row_count": int(shard["row_count"]),
        }
        temporary_path = output_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(scored_result, ensure_ascii=False),
            encoding="utf-8",
        )
        if not valid_output(
            temporary_path,
            metric,
            int(shard["row_count"]),
            expected_input_sha256=str(shard["sha256"]),
            expected_row_start=int(shard["row_start"]),
        ):
            detail = completed_process.stdout[-1000:]
            raise RuntimeError(f"{metric} {input_path.name} returned incomplete output: {detail}")
        temporary_path.replace(output_path)
        completed += int(shard["row_count"])
        print(f"{metric}: completed {output_path.name}; {completed}/{manifest['row_count']}", flush=True)


def load_metric_scores(work_dir: Path, metric: str, expected_rows: int) -> dict[int, float]:
    output_dir = work_dir / "outputs" / metric
    scores = {}
    for path in sorted(output_dir.glob("output-*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        status = str(dict(result.get("status") or {}).get(metric) or "")
        if status != expected_metric_status(metric):
            raise RuntimeError(
                f"{path}: expected status {expected_metric_status(metric)!r}, found {status!r}"
            )
        for item in result.get("scores") or []:
            if metric in item:
                row_index = int(item["row_index"])
                if row_index in scores:
                    raise RuntimeError(f"Duplicate {metric} row index {row_index}")
                numeric = finite_score(item[metric])
                if numeric is None:
                    raise RuntimeError(f"Non-finite {metric} score at row index {row_index}")
                scores[row_index] = numeric
    if len(scores) != expected_rows or set(scores) != set(range(expected_rows)):
        missing = sorted(set(range(expected_rows)) - set(scores))[:20]
        raise RuntimeError(
            f"{metric}: expected {expected_rows} scores, found {len(scores)}; missing {missing}"
        )
    return scores


def neural_fit(rows: list[dict[str, object]], metric: str) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: row["release_date"])
    x = np.asarray(
        [(row["release_date"] - ordered[0]["release_date"]).days for row in ordered],
        dtype=float,
    )
    y = np.asarray([float(row[metric]) for row in ordered], dtype=float)
    fit = stats.linregress(x, y)
    slope_ci = stats.t.interval(0.95, df=len(x) - 2, loc=fit.slope, scale=fit.stderr)
    return {
        "prompt_version": int(ordered[0]["prompt_version"]),
        "metric_key": metric,
        "metric_label": METRIC_LABELS[metric],
        "model_name": METRIC_MODELS[metric],
        "n_models": len(ordered),
        "slope_per_year": float(fit.slope * 365.25),
        "slope_ci_low_per_year": float(slope_ci[0] * 365.25),
        "slope_ci_high_per_year": float(slope_ci[1] * 365.25),
        "r2": float(fit.rvalue**2),
        "p_value": float(fit.pvalue),
    }


def neural_prompt_delta_rows(
    openai_rows: list[dict[str, object]], metrics: list[str]
) -> list[dict[str, object]]:
    by_profile: dict[str, dict[int, dict[str, object]]] = {}
    for row in openai_rows:
        by_profile.setdefault(str(row["profile_name"]), {})[int(row["prompt_version"])] = row
    output = []
    for metric in metrics:
        for left_version, right_version in ((1, 2), (2, 3), (1, 3)):
            deltas = np.asarray(
                [
                    float(versions[right_version][metric])
                    - float(versions[left_version][metric])
                    for versions in by_profile.values()
                    if left_version in versions and right_version in versions
                ],
                dtype=float,
            )
            if len(deltas) != 12:
                raise RuntimeError(
                    f"Expected 12 paired {metric} prompt deltas, found {len(deltas)}"
                )
            standard_error = float(stats.sem(deltas))
            confidence_interval = stats.t.interval(
                0.95,
                df=len(deltas) - 1,
                loc=float(np.mean(deltas)),
                scale=standard_error,
            )
            test = stats.ttest_1samp(deltas, popmean=0.0)
            output.append(
                {
                    "metric_key": metric,
                    "metric_label": METRIC_LABELS[metric],
                    "comparison": f"v{right_version}-v{left_version}",
                    "n_models": len(deltas),
                    "mean_delta": float(np.mean(deltas)),
                    "ci_low": float(confidence_interval[0]),
                    "ci_high": float(confidence_interval[1]),
                    "t_statistic": float(test.statistic),
                    "p_value": float(test.pvalue),
                }
            )
    return output


def write_latex_tables(
    cells: list[dict[str, object]],
    regressions: list[dict[str, object]],
    prompt_deltas: list[dict[str, object]],
    metrics: list[str],
) -> None:
    from paper.analysis import benchmark_paper_analysis as benchmark

    columns = "lrr" + "r" * len(metrics)
    lines = [
        r"\begin{longtable}{" + columns + "}",
        r"\caption{Neural reference-based metric means by model and prompt. Scores are raw model outputs, not percentages.}\\",
        r"\toprule",
        "Provider/model & Prompt & $n$ & " + " & ".join(METRIC_LABELS[item] for item in metrics) + r" \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        "Provider/model & Prompt & $n$ & " + " & ".join(METRIC_LABELS[item] for item in metrics) + r" \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in sorted(cells, key=lambda item: (item["provider"], item["release_date"], item["prompt_version"])):
        metric_text = " & ".join(f"{float(row[item]):.4f}" for item in metrics)
        lines.append(
            f"{benchmark.latex_escape(str(row['model_display_name']))} & "
            f"v{int(row['prompt_version'])} & {int(row['pair_count'])} & {metric_text} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}"])
    (benchmark.BUILD_DIR / "neural_cells_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begin{longtable}{clrrrrr}",
        r"\caption{OLS regressions of model-level neural metric scores on OpenAI release date. Slopes and confidence limits are raw score units per year.}\\",
        r"\toprule",
        r"Prompt & Metric & Slope & 95\% CI low & 95\% CI high & $R^2$ & $p$ \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Prompt & Metric & Slope & 95\% CI low & 95\% CI high & $R^2$ & $p$ \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in sorted(regressions, key=lambda item: (item["prompt_version"], item["metric_key"])):
        lines.append(
            f"v{int(row['prompt_version'])} & {row['metric_label']} & "
            f"{float(row['slope_per_year']):.4f} & {float(row['slope_ci_low_per_year']):.4f} & "
            f"{float(row['slope_ci_high_per_year']):.4f} & {float(row['r2']):.3f} & "
            f"{benchmark.p_text(float(row['p_value']))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}"])
    (benchmark.BUILD_DIR / "neural_regression_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begin{longtable}{llrrrr}",
        r"\caption{Paired neural-metric prompt-version differences across the 12 OpenAI models. Differences and confidence limits are raw score units.}\\",
        r"\toprule",
        r"Metric & Contrast & Mean difference & 95\% CI low & 95\% CI high & $p$ \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Metric & Contrast & Mean difference & 95\% CI low & 95\% CI high & $p$ \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in prompt_deltas:
        lines.append(
            f"{row['metric_label']} & {row['comparison']} & {float(row['mean_delta']):.4f} & "
            f"{float(row['ci_low']):.4f} & {float(row['ci_high']):.4f} & "
            f"{benchmark.p_text(float(row['p_value']))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}"])
    (benchmark.BUILD_DIR / "neural_prompt_delta_table.tex").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def summarize(entries_path: Path, cells_path: Path, work_dir: Path, metrics: list[str]) -> None:
    from paper.analysis import benchmark_paper_analysis as benchmark

    manifest = load_and_validate_manifest(work_dir)
    if file_sha256(entries_path) != manifest["entries_sha256"]:
        raise RuntimeError("Benchmark entries CSV does not match the neural scoring manifest")
    entries = read_csv(entries_path)
    cell_metadata = {
        (row["profile_name"], int(row["prompt_version"])): row for row in read_csv(cells_path)
    }
    metric_scores = {
        metric: load_metric_scores(work_dir, metric, len(entries)) for metric in metrics
    }
    scored_rows = []
    grouped: dict[tuple[str, int], list[dict[str, object]]] = {}
    for row_index, entry in enumerate(entries):
        row: dict[str, object] = {
            "row_index": row_index,
            "provider": entry["provider"],
            "profile_name": entry["profile_name"],
            "prompt_version": int(entry["prompt_version"]),
            "lemma_id": int(entry["lemma_id"]),
            "entry_number": int(entry["entry_number"]),
            **{metric: metric_scores[metric][row_index] for metric in metrics},
        }
        scored_rows.append(row)
        grouped.setdefault((entry["profile_name"], int(entry["prompt_version"])), []).append(row)

    cell_rows = []
    for key, rows in grouped.items():
        metadata = cell_metadata[key]
        release_date = datetime.fromisoformat(metadata["release_date"])
        cell_rows.append(
            {
                "provider": metadata["provider"],
                "profile_name": metadata["profile_name"],
                "model_display_name": metadata["model_display_name"],
                "release_date": release_date,
                "prompt_version": int(metadata["prompt_version"]),
                "pair_count": len(rows),
                **{metric: float(np.mean([float(row[metric]) for row in rows])) for metric in metrics},
            }
        )
    if any(int(row["pair_count"]) != 100 for row in cell_rows) or len(cell_rows) != 44:
        raise RuntimeError("Neural cell integrity check failed")

    regressions = []
    openai_rows = [row for row in cell_rows if row["provider"] == "OpenAI"]
    for prompt_version in (1, 2, 3):
        prompt_rows = [row for row in openai_rows if row["prompt_version"] == prompt_version]
        for metric in metrics:
            regressions.append(neural_fit(prompt_rows, metric))
    prompt_deltas = neural_prompt_delta_rows(openai_rows, metrics)

    serializable_cells = [
        {**row, "release_date": row["release_date"].date().isoformat()}
        for row in sorted(cell_rows, key=lambda item: (item["provider"], item["release_date"], item["prompt_version"]))
    ]
    write_csv(benchmark.BUILD_DIR / "neural_benchmark_rows.csv", scored_rows)
    write_csv(benchmark.BUILD_DIR / "neural_benchmark_cells.csv", serializable_cells)
    write_csv(benchmark.BUILD_DIR / "neural_benchmark_regressions.csv", regressions)
    write_csv(benchmark.BUILD_DIR / "neural_prompt_deltas.csv", prompt_deltas)
    write_latex_tables(cell_rows, regressions, prompt_deltas, metrics)
    for metric in metrics:
        benchmark.plot_timeline_metric(
            cell_rows,
            metric_key=metric,
            output_stem=f"model-quality-over-time-{metric}",
            title=f"{METRIC_LABELS[metric]} by model release date",
            subtitle=(
                f"Mean {METRIC_LABELS[metric]} on 100 Kappa entries; "
                "Claude points are excluded from all fits"
            ),
            y_label=f"Mean {METRIC_LABELS[metric]} score",
            target_line=False,
            score_scale=1.0,
        )
    result = {
        "row_count": len(scored_rows),
        "cell_count": len(cell_rows),
        "metrics": metrics,
        "metric_models": {metric: METRIC_MODELS[metric] for metric in metrics},
        "regressions": regressions,
        "prompt_deltas": prompt_deltas,
    }
    (benchmark.BUILD_DIR / "neural_results.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    prepare_parser.add_argument("--shard-size", type=int, default=400)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("metric", choices=tuple(METRIC_LABELS))
    run_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run_parser.add_argument("--python", type=Path, required=True)
    run_parser.add_argument("--sidecar", type=Path, default=ROOT / "compute_neural_translation_metrics.py")
    run_parser.add_argument("--timeout", type=int, default=21600)
    run_parser.add_argument("--reverse", action="store_true")

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    summarize_parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    summarize_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    summarize_parser.add_argument("--metrics", nargs="+", choices=tuple(METRIC_LABELS), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.entries, args.work_dir, args.shard_size)
    elif args.command == "run":
        run_metric(
            args.metric,
            args.work_dir,
            args.python,
            args.sidecar,
            timeout=args.timeout,
            reverse=args.reverse,
        )
    elif args.command == "summarize":
        summarize(args.entries, args.cells, args.work_dir, args.metrics)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
