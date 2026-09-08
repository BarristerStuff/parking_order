#!/usr/bin/env python3
"""Calculate abstention-aware parking P0 metrics and error-analysis queues."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def safe_div(num: int | float, den: int | float) -> float | None:
    return None if den == 0 else num / den


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - index) + ordered[hi] * (index - lo)


def confusion(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    out = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    for row in rows:
        gt, pred = row["gt_label"], row["model_label"]
        if gt not in {"0", "1"} or pred not in {"0", "1"} or row["status"] != "ok":
            continue
        if gt == "1" and pred == "1": out["TP"] += 1
        elif gt == "0" and pred == "1": out["FP"] += 1
        elif gt == "0" and pred == "0": out["TN"] += 1
        elif gt == "1" and pred == "0": out["FN"] += 1
    return out


def binary_metrics(c: dict[str, int]) -> dict[str, float | int | None]:
    tp, fp, tn, fn = c["TP"], c["FP"], c["TN"], c["FN"]
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    specificity = safe_div(tn, tn + fp)
    return {
        **c,
        "decisive_binary_count": tp + fp + tn + fn,
        "precision": precision,
        "recall": recall,
        "f1": None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall),
        "accuracy": safe_div(tp + tn, tp + fp + tn + fn),
        "specificity": specificity,
        "fpr": safe_div(fp, fp + tn),
        "balanced_accuracy": None if recall is None or specificity is None else (recall + specificity) / 2,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["media_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 239 or len({row["media_id"] for row in rows}) != 239:
        raise SystemExit(f"analysis requires 239 unique DEV predictions, found {len(rows)}")
    if any(row["split"] != "train" for row in rows):
        raise SystemExit("analysis split guard rejected non-train result")
    rows.sort(key=lambda row: int(row["source_id"]))

    overall = binary_metrics(confusion(rows))
    status_counts = Counter(row["status"] for row in rows)
    parsed = [row for row in rows if row["status"] == "ok"]
    model_uncertain = [row for row in parsed if row["model_label"] == "uncertain"]
    binary_gt = [row for row in rows if row["gt_label"] in {"0", "1"}]
    binary_gt_abstentions = [row for row in binary_gt if row["status"] == "ok" and row["model_label"] == "uncertain"]
    ordinary = [row for row in rows if row["sample_role"] == "negative"]
    hard = [row for row in rows if row["sample_role"] == "hard_negative"]
    gate = [row for row in rows if row["group_key"] == "hn01-gate-queue"]

    def negative_slice_metrics(slice_rows: list[dict[str, Any]]) -> dict[str, Any]:
        c = confusion(slice_rows)
        abst = sum(row["status"] == "ok" and row["model_label"] == "uncertain" for row in slice_rows)
        failures = sum(row["status"] != "ok" for row in slice_rows)
        return {
            "count": len(slice_rows), "FP": c["FP"], "TN": c["TN"],
            "fpr": safe_div(c["FP"], c["FP"] + c["TN"]),
            "model_uncertain_count": abst, "failure_count": failures,
            "decisive_coverage": safe_div(c["FP"] + c["TN"], len(slice_rows)),
        }

    latencies = [float(row["latency_seconds"]) for row in rows]
    metrics = {
        "task": "parking_order_violation",
        "stage": "P0",
        "event_definition_version": "v1.1",
        "dataset_scope": "DEV/train only",
        "gt_basis": "generation_intent",
        "gt_review_status": "unreviewed",
        "sample_count": len(rows),
        "gt_counts": dict(Counter(row["gt_label"] for row in rows)),
        "role_counts": dict(Counter(row["sample_role"] for row in rows)),
        "prediction_status_counts": dict(status_counts),
        "model_label_counts_on_parsed": dict(Counter(row["model_label"] for row in parsed)),
        "binary": overall,
        "binary_gt_count": len(binary_gt),
        "binary_gt_model_uncertain_count": len(binary_gt_abstentions),
        "binary_gt_model_uncertain_rate": safe_div(len(binary_gt_abstentions), len(binary_gt)),
        "uncertain_rate": safe_div(len(model_uncertain), len(parsed)),
        "gt_uncertain_count": sum(row["gt_label"] == "uncertain" for row in rows),
        "ordinary_negative": negative_slice_metrics(ordinary),
        "hard_negative": negative_slice_metrics(hard),
        "gate_queue": negative_slice_metrics(gate),
        "inference_failure_count": status_counts.get("inference_failure", 0),
        "parse_failure_count": status_counts.get("parse_failure", 0),
        "latency_seconds": {
            "count": len(latencies),
            "mean": statistics.fmean(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "p95": percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "metric_policy": "TP/FP/TN/FN use only GT 0/1 rows with parsed decisive model 0/1 outputs. GT uncertain, model uncertain, parse failures, and inference failures are separately reported.",
        "val_consumed": False,
        "holdout_consumed": False,
        "scope_warning": "Synthetic generation-intent DEV evidence; not human visual gold or production accuracy.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    false_positives = [row for row in rows if row["status"] == "ok" and row["gt_label"] == "0" and row["model_label"] == "1"]
    false_negatives = [row for row in rows if row["status"] == "ok" and row["gt_label"] == "1" and row["model_label"] == "0"]
    queues = {
        "false_positives.csv": false_positives,
        "false_negatives.csv": false_negatives,
        "hard_negative_false_positives.csv": [row for row in false_positives if row["sample_role"] == "hard_negative"],
        "gate_queue_false_positives.csv": [row for row in false_positives if row["group_key"] == "hn01-gate-queue"],
        "model_uncertain.csv": model_uncertain,
        "parse_failures.csv": [row for row in rows if row["status"] == "parse_failure"],
        "inference_failures.csv": [row for row in rows if row["status"] == "inference_failure"],
    }
    for name, queue in queues.items():
        write_csv(args.output_dir / name, queue)

    group_rows = []
    for group in sorted({row["group_key"] for row in rows}):
        subset = [row for row in rows if row["group_key"] == group]
        c = binary_metrics(confusion(subset))
        group_rows.append({
            "group_key": group, "count": len(subset),
            "gt_1": sum(row["gt_label"] == "1" for row in subset),
            "gt_0": sum(row["gt_label"] == "0" for row in subset),
            "gt_uncertain": sum(row["gt_label"] == "uncertain" for row in subset),
            "pred_1": sum(row["status"] == "ok" and row["model_label"] == "1" for row in subset),
            "pred_0": sum(row["status"] == "ok" and row["model_label"] == "0" for row in subset),
            "pred_uncertain": sum(row["status"] == "ok" and row["model_label"] == "uncertain" for row in subset),
            "failures": sum(row["status"] != "ok" for row in subset),
            **c,
        })
    write_csv(args.output_dir / "group_metrics.csv", group_rows)

    md = [
        "# parking_order_violation P0 results", "",
        "> Synthetic generation-intent DEV evidence only; not human visual gold or production accuracy.", "",
        f"- Scope: DEV/`train` only ({len(rows)} images)",
        "- VAL_CONSUMED=false", "- HOLDOUT_CONSUMED=false", "",
        "## Binary decisive metrics", "",
    ]
    for key in ["TP", "FP", "TN", "FN", "precision", "recall", "f1", "accuracy", "specificity", "fpr", "balanced_accuracy", "decisive_binary_count"]:
        md.append(f"- {key}: {overall[key]}")
    md += ["", "## Negative-slice FPR", ""]
    for name in ["ordinary_negative", "hard_negative", "gate_queue"]:
        md.append(f"- {name}: {metrics[name]}")
    md += ["", "## Abstention, failures, latency", "",
           f"- uncertain_rate: {metrics['uncertain_rate']}",
           f"- binary_gt_model_uncertain_rate: {metrics['binary_gt_model_uncertain_rate']}",
           f"- inference_failure_count: {metrics['inference_failure_count']}",
           f"- parse_failure_count: {metrics['parse_failure_count']}",
           f"- latency_seconds: {metrics['latency_seconds']}", "",
           "## Error queues", ""]
    for name, queue in queues.items(): md.append(f"- {name}: {len(queue)}")
    (args.output_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
