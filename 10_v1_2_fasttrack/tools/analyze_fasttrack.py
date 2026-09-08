#!/usr/bin/env python3
"""Analyze one v1.2 fast-track candidate using the frozen DEV shadow policy."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def binary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for row in rows:
        gt = row["v1_2_gt"]
        alarm = row.get("model_label") == "positive"
        if gt == "positive" and alarm:
            tp += 1
        elif gt == "positive":
            fn += 1
        elif gt == "negative" and alarm:
            fp += 1
        elif gt == "negative":
            tn += 1
        else:
            raise ValueError(f"non-binary GT in primary rows: {gt!r}")
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    specificity = safe_div(tn, tn + fp)
    return {
        "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "precision": precision, "recall": recall,
        "f1": safe_div(2 * precision * recall, precision + recall) if precision is not None and recall is not None else None,
        "accuracy": safe_div(tp + tn, tp + fp + tn + fn),
        "specificity": specificity, "fpr": safe_div(fp, fp + tn),
        "balanced_accuracy": (recall + specificity) / 2 if recall is not None and specificity is not None else None,
        "count": len(rows),
        "policy": "Positive alarm vs no-positive alarm. Model uncertain is a miss on positive GT and a non-alarm on negative GT; it is also reported separately. Protocol failures make the candidate gate fail.",
    }


def negative_slice(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fp = sum(row.get("model_label") == "positive" for row in rows)
    return {
        "count": len(rows), "FP": fp, "TN": len(rows) - fp,
        "fpr": safe_div(fp, len(rows)),
        "model_uncertain_count": sum(row.get("model_label") == "uncertain" for row in rows),
        "failure_count": sum(row.get("status") != "ok" for row in rows),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    with args.manifest.open("r", encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    predictions = [json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(manifest) != 239 or len(predictions) != 239:
        raise SystemExit(f"analysis requires 239 manifest and prediction rows, got {len(manifest)} and {len(predictions)}")
    manifest_ids = [row["media_id"] for row in manifest]
    prediction_ids = [row["media_id"] for row in predictions]
    if len(set(manifest_ids)) != 239 or len(set(prediction_ids)) != 239 or set(manifest_ids) != set(prediction_ids):
        raise SystemExit("manifest/prediction binding mismatch")
    by_prediction = {row["media_id"]: row for row in predictions}
    rows: list[dict[str, Any]] = []
    for source in manifest:
        prediction = by_prediction[source["media_id"]]
        for field in ("split", "group_key", "v1_2_gt", "evaluation_scope", "relative_path"):
            if prediction[field] != source[field]:
                raise SystemExit(f"prediction binding field mismatch: {source['media_id']} {field}")
        rows.append(prediction)

    primary = [row for row in rows if row["evaluation_scope"] == "primary_binary"]
    gt_uncertain = [row for row in rows if row["evaluation_scope"] == "gt_uncertain"]
    boundary = [row for row in rows if row["evaluation_scope"] == "boundary_challenge"]
    if (len(primary), len(gt_uncertain), len(boundary)) != (179, 25, 35):
        raise SystemExit("analysis scope count mismatch")
    binary = binary_metrics(primary)
    ordinary = [row for row in primary if row["sample_role"] == "negative"]
    hard = [row for row in primary if row["sample_role"] == "hard_negative"]
    gate = [row for row in primary if row["group_key"] == "hn01-gate-queue"]

    logical_latencies = [float(row["latency_seconds"]) for row in rows]
    physical_latencies = [
        float(view["latency_seconds"])
        for row in rows for view in row.get("views", []) if view.get("latency_seconds") is not None
    ]
    physical_views = [view for row in rows for view in row.get("views", [])]
    image_counts = [int(row.get("images_per_logical_request", 0)) for row in rows]
    latency = {
        "count": len(logical_latencies), "mean": statistics.fmean(logical_latencies),
        "p50": percentile(logical_latencies, 0.50), "p90": percentile(logical_latencies, 0.90),
        "p95": percentile(logical_latencies, 0.95), "max": max(logical_latencies),
        "physical_view_latency": {
            "count": len(physical_latencies), "mean": statistics.fmean(physical_latencies) if physical_latencies else None,
            "p50": percentile(physical_latencies, 0.50), "p90": percentile(physical_latencies, 0.90),
            "p95": percentile(physical_latencies, 0.95), "max": max(physical_latencies) if physical_latencies else None,
        },
        "images_per_logical_request": {
            "mean": statistics.fmean(image_counts), "min": min(image_counts), "max": max(image_counts),
        },
        "physical_request_count": sum(int(row.get("physical_request_count", 0)) for row in rows),
        "extra_crop_count": sum(int(row.get("extra_crop_count", 0)) for row in rows),
        "extra_model_request_count": sum(int(row.get("extra_model_request_count", 0)) for row in rows),
        "extra_physical_request_count": sum(int(row.get("extra_physical_request_count", 0)) for row in rows),
        "detector_latency_mean": statistics.fmean(float(row.get("detector_latency_seconds", 0)) for row in rows),
    }

    def positive_group_recall(group: str) -> float | None:
        subset = [row for row in primary if row["group_key"] == group]
        return safe_div(sum(row.get("model_label") == "positive" for row in subset), len(subset))

    logical_protocol_rate = safe_div(sum(bool(row.get("protocol_success")) for row in rows), len(rows))
    physical_http_rate = safe_div(sum(view.get("http_status") == 200 for view in physical_views), len(physical_views))
    physical_schema_rate = safe_div(sum(bool(view.get("schema_success")) for view in physical_views), len(physical_views))
    semantic_rate = safe_div(sum(bool(view.get("semantic_protocol_ok")) for view in physical_views), len(physical_views))
    model_uncertain_count = sum(row.get("model_label") == "uncertain" for row in primary)
    p01_recall = positive_group_recall("p01-outside-legal-bay-clear")
    p05_recall = positive_group_recall("p05-multi-vehicle-at-least-one-violation")
    hard_metrics = negative_slice(hard)
    gate_metrics = negative_slice(gate)
    ordinary_metrics = negative_slice(ordinary)
    gate_passed = all((
        binary["precision"] is not None and binary["precision"] >= 0.90,
        binary["recall"] is not None and binary["recall"] >= 0.85,
        binary["f1"] is not None and binary["f1"] >= 0.87,
        hard_metrics["fpr"] is not None and hard_metrics["fpr"] <= 0.05,
        gate_metrics["fpr"] == 0,
        logical_protocol_rate == 1.0,
        physical_schema_rate == 1.0,
        p01_recall is not None and p01_recall >= 0.85,
        p05_recall is not None and p05_recall >= 0.80,
    ))
    metrics = {
        "task": "parking_order_violation", "stage": "V1.2_FASTTRACK_DEV",
        "candidate": config["candidate"], "event_definition_version": "v1.2",
        "dataset_scope": "DEV/train only", "sample_count": len(rows),
        "primary_binary_count": len(primary), "gt_uncertain_count": len(gt_uncertain),
        "boundary_challenge_count": len(boundary), "binary": binary,
        "ordinary_negative": ordinary_metrics, "hard_negative": hard_metrics, "gate_queue": gate_metrics,
        "model_uncertain_count": model_uncertain_count,
        "model_uncertain_rate": safe_div(model_uncertain_count, len(primary)),
        "p01_recall": p01_recall, "p05_recall": p05_recall,
        "p02": {
            "total": len(boundary),
            "model_positive": sum(row.get("model_label") == "positive" for row in boundary),
            "model_negative": sum(row.get("model_label") == "negative" for row in boundary),
            "model_uncertain": sum(row.get("model_label") == "uncertain" for row in boundary),
            "failure": sum(row.get("status") != "ok" for row in boundary),
        },
        "protocol": {
            "logical_success_rate": logical_protocol_rate, "physical_http_success_rate": physical_http_rate,
            "physical_json_schema_success_rate": physical_schema_rate,
            "physical_semantic_success_rate": semantic_rate,
            "logical_failure_count": sum(not bool(row.get("protocol_success")) for row in rows),
            "physical_view_count": len(physical_views),
        },
        "latency_seconds": latency, "dev_gate_passed": gate_passed,
        "fast_fail_recall_below_0_70": binary["recall"] is not None and binary["recall"] < 0.70,
        "fast_fail_p01_below_0_70": p01_recall is not None and p01_recall < 0.70,
        "gt_basis": "generation_intent_shadow", "gt_review_status": "unreviewed",
        "scope_warning": "Synthetic generation-intent shadow DEV evidence; not per-image Human Gold or production accuracy.",
        "val_consumed": False, "holdout_consumed": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "latency.json").write_text(
        json.dumps(latency, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    subgroup_rows: list[dict[str, Any]] = []
    for group in sorted({row["group_key"] for row in rows}):
        subset = [row for row in rows if row["group_key"] == group]
        gt_values = sorted({row["v1_2_gt"] for row in subset})
        subgroup_rows.append({
            "group_key": group, "count": len(subset), "v1_2_gt": ",".join(gt_values),
            "evaluation_scope": subset[0]["evaluation_scope"],
            "model_positive": sum(row.get("model_label") == "positive" for row in subset),
            "model_negative": sum(row.get("model_label") == "negative" for row in subset),
            "model_uncertain": sum(row.get("model_label") == "uncertain" for row in subset),
            "failure": sum(row.get("status") != "ok" for row in subset),
            "positive_alarm_rate": safe_div(sum(row.get("model_label") == "positive" for row in subset), len(subset)),
        })
    subgroup_fields = [
        "group_key", "count", "v1_2_gt", "evaluation_scope", "model_positive",
        "model_negative", "model_uncertain", "failure", "positive_alarm_rate",
    ]
    write_csv(args.output_dir / "subgroup_metrics.csv", subgroup_rows, subgroup_fields)

    error_rows: list[dict[str, Any]] = []
    for row in rows:
        error_type = ""
        if row["evaluation_scope"] == "primary_binary":
            if row["v1_2_gt"] == "positive" and row.get("model_label") != "positive":
                error_type = "FN"
            elif row["v1_2_gt"] == "negative" and row.get("model_label") == "positive":
                error_type = "FP"
            elif row.get("model_label") == "uncertain":
                error_type = "MODEL_UNCERTAIN"
        if not row.get("protocol_success"):
            error_type = f"{error_type}+PROTOCOL_FAILURE" if error_type else "PROTOCOL_FAILURE"
        if error_type:
            error_rows.append({**row, "error_type": error_type})
    error_fields = [
        "error_type", "source_id", "media_id", "group_key", "sample_role", "v1_2_gt",
        "evaluation_scope", "model_label", "evidence_type", "reason", "status",
        "protocol_success", "latency_seconds", "relative_path", "error",
    ]
    write_csv(args.output_dir / "errors.csv", error_rows, error_fields)

    report = f"""# {config['candidate']} DEV report

> Generation-intent shadow GT only; not per-image Human Gold or production accuracy.

## Primary operational binary metrics

- TP/FP/TN/FN: {binary['TP']}/{binary['FP']}/{binary['TN']}/{binary['FN']}
- Precision: {binary['precision']}
- Recall: {binary['recall']}
- F1: {binary['f1']}
- Accuracy: {binary['accuracy']}
- Specificity: {binary['specificity']}
- FPR: {binary['fpr']}
- Balanced Accuracy: {binary['balanced_accuracy']}
- ordinary-negative FPR: {ordinary_metrics['fpr']}
- hard-negative FPR: {hard_metrics['fpr']}
- gate-queue FPR: {gate_metrics['fpr']}
- model uncertain rate: {metrics['model_uncertain_rate']}
- p01 recall: {p01_recall}
- p05 recall: {p05_recall}

## Boundary challenge (excluded from primary)

- P02_TOTAL: {metrics['p02']['total']}
- P02_MODEL_POSITIVE: {metrics['p02']['model_positive']}
- P02_MODEL_NEGATIVE: {metrics['p02']['model_negative']}
- P02_MODEL_UNCERTAIN: {metrics['p02']['model_uncertain']}
- P02_FAILURE: {metrics['p02']['failure']}

## Protocol and latency

- Protocol success rate: {logical_protocol_rate}
- HTTP success rate: {physical_http_rate}
- JSON/schema success rate: {physical_schema_rate}
- Semantic protocol success rate: {semantic_rate}
- Logical latency mean/P50/P90/P95/max: {latency['mean']}/{latency['p50']}/{latency['p90']}/{latency['p95']}/{latency['max']}
- Images per logical request mean/min/max: {latency['images_per_logical_request']}
- Physical request count: {latency['physical_request_count']}
- Extra crop count: {latency['extra_crop_count']}
- Extra model request count: {latency['extra_model_request_count']}

## Decision

- DEV_GATE_PASSED: {str(gate_passed).lower()}
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false
"""
    (args.output_dir / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
