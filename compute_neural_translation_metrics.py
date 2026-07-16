#!/usr/bin/env python3
"""Compute optional neural translation metrics in an isolated environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


DEFAULT_COMET_MODEL = "Unbabel/wmt22-comet-da"
DEFAULT_XCOMET_MODEL = "Unbabel/XCOMET-XL"
DEFAULT_BLEURT_CHECKPOINTS = (
    "/home/stephanos/metric-envs/bleurt/BLEURT-20",
    "bleurt-20",
)


def finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return numeric


def select_bleurt_checkpoint(requested: str | None) -> str:
    candidates = []
    if requested:
        candidates.append(requested)
    candidates.extend(DEFAULT_BLEURT_CHECKPOINTS)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return requested or DEFAULT_BLEURT_CHECKPOINTS[0]


def compute_bertscore(rows: list[dict[str, Any]], request: dict[str, Any]) -> tuple[dict[int, dict[str, float]], str]:
    from bert_score import score as bert_score

    candidates = [str(row.get("candidate") or "") for row in rows]
    references = [str(row.get("reference") or "") for row in rows]
    precision, recall, f1 = bert_score(
        candidates,
        references,
        lang="en",
        verbose=False,
        device="cuda" if request.get("use_gpu") else "cpu",
        batch_size=int(request.get("bertscore_batch_size") or 16),
    )
    scores = {}
    for row, p_value, r_value, f_value in zip(rows, precision, recall, f1, strict=True):
        row_index = int(row["row_index"])
        scores[row_index] = {
            "bertscore": float(f_value),
            "bertscore_precision": float(p_value),
            "bertscore_recall": float(r_value),
        }
    return scores, "sidecar bert-score F1"


def compute_comet_model(
    rows: list[dict[str, Any]],
    request: dict[str, Any],
    *,
    request_key: str,
    default_model: str,
    score_key: str,
) -> tuple[dict[int, dict[str, float]], str]:
    from comet import download_model, load_from_checkpoint

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    model_name = str(request.get(request_key) or default_model)
    if score_key == "xcomet":
        from huggingface_hub import snapshot_download

        model_path = Path(snapshot_download(repo_id=model_name)) / "checkpoints" / "model.ckpt"
    else:
        model_path = download_model(model_name)
    model = load_from_checkpoint(model_path)
    if request.get("use_gpu"):
        model = model.cuda()
    data = [
        {
            "src": str(row.get("source") or ""),
            "mt": str(row.get("candidate") or ""),
            "ref": str(row.get("reference") or ""),
        }
        for row in rows
    ]
    output = model.predict(
        data,
        batch_size=int(request.get("comet_batch_size") or 8),
        gpus=1 if request.get("use_gpu") else 0,
        num_workers=0,
        progress_bar=False,
    )
    raw_scores = output["scores"] if isinstance(output, dict) else output.scores
    scores = {}
    for row, score in zip(rows, raw_scores, strict=True):
        numeric = finite_float(score)
        if numeric is not None:
            scores[int(row["row_index"])] = {score_key: numeric}
    return scores, f"sidecar {model_name}"


def compute_comet(rows: list[dict[str, Any]], request: dict[str, Any]) -> tuple[dict[int, dict[str, float]], str]:
    return compute_comet_model(
        rows,
        request,
        request_key="comet_model",
        default_model=DEFAULT_COMET_MODEL,
        score_key="comet",
    )


def compute_xcomet(rows: list[dict[str, Any]], request: dict[str, Any]) -> tuple[dict[int, dict[str, float]], str]:
    return compute_comet_model(
        rows,
        request,
        request_key="xcomet_model",
        default_model=DEFAULT_XCOMET_MODEL,
        score_key="xcomet",
    )


def compute_bleurt(rows: list[dict[str, Any]], request: dict[str, Any]) -> tuple[dict[int, dict[str, float]], str]:
    from bleurt import score as bleurt_score

    checkpoint = select_bleurt_checkpoint(request.get("bleurt_checkpoint"))
    scorer = bleurt_score.BleurtScorer(checkpoint)
    raw_scores = scorer.score(
        references=[str(row.get("reference") or "") for row in rows],
        candidates=[str(row.get("candidate") or "") for row in rows],
        batch_size=int(request.get("bleurt_batch_size") or 16),
    )
    scores = {}
    for row, score in zip(rows, raw_scores, strict=True):
        numeric = finite_float(score)
        if numeric is not None:
            scores[int(row["row_index"])] = {"bleurt": numeric}
    return scores, f"sidecar BLEURT checkpoint {checkpoint}"


METRIC_FUNCTIONS = {
    "bertscore": compute_bertscore,
    "comet": compute_comet,
    "xcomet": compute_xcomet,
    "bleurt": compute_bleurt,
}


def main() -> int:
    request = json.load(sys.stdin)
    rows = list(request.get("rows") or [])
    metrics = [str(metric) for metric in request.get("metrics") or []]
    combined_scores: dict[int, dict[str, float]] = {int(row["row_index"]): {} for row in rows}
    status: dict[str, str] = {}

    for metric in metrics:
        metric_function = METRIC_FUNCTIONS.get(metric)
        if metric_function is None:
            status[metric] = f"unavailable: unknown metric {metric}"
            continue
        try:
            metric_scores, metric_status = metric_function(rows, request)
        except Exception as exc:
            status[metric] = f"unavailable: sidecar calculation failed ({exc})"
            continue
        status[metric] = metric_status
        for row_index, row_scores in metric_scores.items():
            combined_scores.setdefault(row_index, {}).update(row_scores)

    response = {
        "status": status,
        "scores": [
            {"row_index": row_index, **row_scores}
            for row_index, row_scores in sorted(combined_scores.items())
        ],
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
