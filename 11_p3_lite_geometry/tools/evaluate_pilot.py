#!/usr/bin/env python3
"""Evaluate one frozen P3L-A geometry-only pilot and emit audit artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


EXPECTED_PILOT_MANIFEST_SHA256 = "2f2f8de90026ed5edd7c00b4e64b16d59fa502010078955c7a7d9339e5afcce0"
EXPECTED_PARAMS_SHA256 = "42e6a6e84d9c471ffb951b9fe898ed44af187ce43921dc59bdbdf08085036d72"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def safe_div(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite pilot output: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite pilot output: {path}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def error_category(gt: str, prediction: str, evidence: dict[str, Any]) -> str:
    if gt == "negative" and prediction == "positive":
        return "geometry_rule_failure"
    if gt != "positive" or prediction == "positive":
        return ""
    if evidence["eligible_detection_count"] == 0:
        return "vehicle_detection_failure"
    vehicles = evidence["vehicle_results"]
    candidate_count = sum(len(vehicle["line_candidates"]) for vehicle in vehicles)
    separator_count = max((len(vehicle["separators"]) for vehicle in vehicles), default=0)
    high_slot = any(
        vehicle.get("slot_geometry_confidence") == "high" for vehicle in vehicles
    )
    if candidate_count == 0:
        return "line_detection_failure"
    if separator_count < 2 or not high_slot:
        return "slot_structure_failure"
    if evidence["geometry_state"] in {"normal", "insufficient"}:
        return "geometry_rule_failure"
    return "insufficient_scene_evidence"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if sha256_file(args.manifest) != EXPECTED_PILOT_MANIFEST_SHA256:
        raise SystemExit("pilot manifest SHA-256 mismatch")
    if sha256_file(args.params) != EXPECTED_PARAMS_SHA256:
        raise SystemExit("frozen geometry parameter SHA-256 mismatch")
    manifest = list(csv.DictReader(args.manifest.open(newline="", encoding="utf-8")))
    evidence = read_jsonl(args.evidence)
    if len(manifest) != 60 or len(evidence) != 60:
        raise SystemExit("pilot must contain exactly 60 manifest/evidence rows")
    by_token = {row["sample_token"]: row for row in evidence}
    if len(by_token) != 60 or set(by_token) != {row["sha256"] for row in manifest}:
        raise SystemExit("pilot evidence binding mismatch")

    predictions = []
    for row in manifest:
        item = by_token[row["sha256"]]
        state = item["geometry_state"]
        if state not in {"positive", "normal", "insufficient"}:
            raise SystemExit(f"invalid geometry state: {state}")
        gt = row["v1_2_gt"]
        predictions.append({
            "source_id": row["source_id"],
            "media_id": row["media_id"],
            "relative_path": row["relative_path"],
            "image_sha256": row["sha256"],
            "group_key": row["group_key"],
            "sample_role": row["sample_role"],
            "v1_2_gt": gt,
            "evaluation_scope": row["evaluation_scope"],
            "pilot_stratum": row["pilot_stratum"],
            "geometry_state": state,
            "geometry_confidence": item["geometry_confidence"],
            "reason_code": item["reason_code"],
            "input_detection_count": item["input_detection_count"],
            "eligible_detection_count": item["eligible_detection_count"],
            "detector_latency_seconds": item["detector_latency_seconds"],
            "geometry_latency_seconds": item["geometry_latency_seconds"],
            "total_logical_latency_seconds": item["total_logical_latency_seconds"],
            "is_error": (gt == "positive" and state != "positive") or (gt == "negative" and state == "positive"),
            "error_category": error_category(gt, state, item),
        })

    tp = sum(row["v1_2_gt"] == "positive" and row["geometry_state"] == "positive" for row in predictions)
    fn = sum(row["v1_2_gt"] == "positive" and row["geometry_state"] != "positive" for row in predictions)
    fp = sum(row["v1_2_gt"] == "negative" and row["geometry_state"] == "positive" for row in predictions)
    tn = sum(row["v1_2_gt"] == "negative" and row["geometry_state"] != "positive" for row in predictions)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        by_group[row["group_key"]].append(row)
    p01 = by_group["p01-outside-legal-bay-clear"]
    p05 = by_group["p05-multi-vehicle-at-least-one-violation"]
    gate = by_group["hn01-gate-queue"]
    negatives = [row for row in predictions if row["v1_2_gt"] == "negative"]
    p01_recall = safe_div(sum(row["geometry_state"] == "positive" for row in p01), len(p01))
    p05_recall = safe_div(sum(row["geometry_state"] == "positive" for row in p05), len(p05))
    negative_fpr = safe_div(sum(row["geometry_state"] == "positive" for row in negatives), len(negatives))
    gate_fpr = safe_div(sum(row["geometry_state"] == "positive" for row in gate), len(gate))
    coverage = safe_div(sum(row["geometry_state"] in {"positive", "normal"} for row in predictions), len(predictions))
    detection_rate = safe_div(sum(row["input_detection_count"] > 0 for row in predictions), len(predictions))

    immediate_fail_reasons = []
    if recall < 0.50:
        immediate_fail_reasons.append("positive_recall_below_0.50")
    if p01_recall < 0.50:
        immediate_fail_reasons.append("p01_recall_below_0.50")
    if gate_fpr > 0.10:
        immediate_fail_reasons.append("gate_queue_fpr_above_0.10")
    promising_checks = {
        "positive_recall_gte_0.60": recall >= 0.60,
        "p01_recall_gte_0.60": p01_recall >= 0.60,
        "p05_recall_gte_0.50": p05_recall >= 0.50,
        "negative_fpr_lte_0.10": negative_fpr <= 0.10,
        "gate_queue_fpr_lte_0.05": gate_fpr <= 0.05,
    }
    pilot_gate_passed = all(promising_checks.values())
    final_status = "P3L_A_GEOMETRY_PROMISING" if pilot_gate_passed else "P3_LITE_GEOMETRY_NOT_VIABLE"

    detector_latencies = [float(row["detector_latency_seconds"]) for row in predictions]
    geometry_latencies = [float(row["geometry_latency_seconds"]) for row in predictions]
    total_latencies = [float(row["total_logical_latency_seconds"]) for row in predictions]
    latency = {
        "cache_source": "F2_EXISTING_DETECTOR_RUN",
        "yolo_rerun": False,
        "detector_latency_note": "historical per-sample F2 detector latency; detector was not rerun",
        "detector_p50_seconds": percentile(detector_latencies, 0.50),
        "detector_p95_seconds": percentile(detector_latencies, 0.95),
        "geometry_p50_seconds": percentile(geometry_latencies, 0.50),
        "geometry_p95_seconds": percentile(geometry_latencies, 0.95),
        "total_logical_p50_seconds": percentile(total_latencies, 0.50),
        "total_logical_p95_seconds": percentile(total_latencies, 0.95),
        "vlm_gate_request_count": 0,
        "vlm_gate_request_rate": 0.0,
    }
    metrics = {
        "FINAL_STATUS": final_status,
        "PILOT_COUNT": len(predictions),
        "YOLO_VEHICLE_DETECTION_RATE": detection_rate,
        "GEOMETRY_PILOT_TP": tp,
        "GEOMETRY_PILOT_FP": fp,
        "GEOMETRY_PILOT_TN": tn,
        "GEOMETRY_PILOT_FN": fn,
        "GEOMETRY_PILOT_PRECISION": precision,
        "GEOMETRY_PILOT_RECALL": recall,
        "GEOMETRY_PILOT_F1": f1,
        "GEOMETRY_PILOT_P01_RECALL": p01_recall,
        "GEOMETRY_PILOT_P05_RECALL": p05_recall,
        "GEOMETRY_PILOT_NEGATIVE_FPR": negative_fpr,
        "GEOMETRY_PILOT_GATE_FPR": gate_fpr,
        "GEOMETRY_COVERAGE": coverage,
        "PILOT_IMMEDIATE_FAIL": bool(immediate_fail_reasons),
        "PILOT_IMMEDIATE_FAIL_REASONS": immediate_fail_reasons,
        "PILOT_PROMISING_CHECKS": promising_checks,
        "PILOT_GATE_PASSED": pilot_gate_passed,
        "FULL_DEV_EXECUTED": False,
        "VLM_GATE_REQUEST_COUNT": 0,
        "VLM_GATE_REQUEST_RATE": 0.0,
        "P50_LATENCY": latency["total_logical_p50_seconds"],
        "P95_LATENCY": latency["total_logical_p95_seconds"],
        "READY_FOR_VAL": False,
        "VAL_CONSUMED": False,
        "HOLDOUT_CONSUMED": False,
        "state_counts": dict(sorted(Counter(row["geometry_state"] for row in predictions).items())),
        "error_category_counts": dict(sorted(Counter(row["error_category"] for row in predictions if row["error_category"]).items())),
        "pilot_manifest_sha256": sha256_file(args.manifest),
        "geometry_params_sha256": sha256_file(args.params),
        "geometry_evidence_sha256": sha256_file(args.evidence),
    }

    output = args.output_dir
    write_csv(output / "geometry_predictions.csv", predictions, list(predictions[0]))
    errors = [row for row in predictions if row["is_error"]]
    write_csv(output / "errors.csv", errors, list(predictions[0]))
    subgroup_rows = []
    for group, rows in sorted(by_group.items()):
        positives = sum(row["v1_2_gt"] == "positive" for row in rows)
        negatives_count = len(rows) - positives
        positive_predictions = sum(row["geometry_state"] == "positive" for row in rows)
        subgroup_rows.append({
            "group_key": group,
            "count": len(rows),
            "positive_gt_count": positives,
            "negative_gt_count": negatives_count,
            "geometry_positive_count": positive_predictions,
            "positive_recall": safe_div(
                sum(row["v1_2_gt"] == "positive" and row["geometry_state"] == "positive" for row in rows), positives
            ),
            "negative_fpr": safe_div(
                sum(row["v1_2_gt"] == "negative" and row["geometry_state"] == "positive" for row in rows), negatives_count
            ),
            "geometry_coverage": safe_div(
                sum(row["geometry_state"] in {"positive", "normal"} for row in rows), len(rows)
            ),
        })
    write_csv(output / "subgroup_metrics.csv", subgroup_rows, list(subgroup_rows[0]))
    write_json(output / "pilot_metrics.json", metrics)
    write_json(output / "latency.json", latency)

    report = f"""# P3-lite geometry-only pilot report

Date: 2026-09-07

## Decision

`FINAL_STATUS={final_status}`

The frozen one-shot pilot {'passed' if pilot_gate_passed else 'did not pass'} the
promising gate. Immediate fail reasons: {', '.join(immediate_fail_reasons) if immediate_fail_reasons else 'none'}.

Because `PILOT_GATE_PASSED={'true' if pilot_gate_passed else 'false'}`, the next
stage is {'P3L-B full-scene gate-queue veto' if pilot_gate_passed else 'stopped; no Ollama and no full DEV'}.

## Metrics

```text
PILOT_COUNT={len(predictions)}
TP={tp}
FP={fp}
TN={tn}
FN={fn}
Precision={precision:.6f}
Recall={recall:.6f}
F1={f1:.6f}
p01_recall={p01_recall:.6f}
p05_recall={p05_recall:.6f}
negative_FPR={negative_fpr:.6f}
gate_queue_FPR={gate_fpr:.6f}
geometry_coverage={coverage:.6f}
YOLO_vehicle_detection_rate={detection_rate:.6f}
```

## Error decomposition

```json
{json.dumps(metrics['error_category_counts'], ensure_ascii=False, indent=2, sort_keys=True)}
```

The categories are assigned after inference by the evaluator. The geometry
engine itself did not receive group, role, GT, source_id, evaluation scope, or
media_id.

## Latency and request discipline

The detector was not rerun. Detector latency is the historical F2 measurement
bound to the cached detection. Geometry was measured locally in this run.

```text
P50_total_logical_seconds={latency['total_logical_p50_seconds']:.6f}
P95_total_logical_seconds={latency['total_logical_p95_seconds']:.6f}
VLM_gate_request_count=0
VLM_gate_request_rate=0
```

## Frozen bindings

```text
pilot_manifest_sha256={sha256_file(args.manifest)}
geometry_params_sha256={sha256_file(args.params)}
geometry_evidence_sha256={sha256_file(args.evidence)}
YOLO_RERUN=false
VAL_CONSUMED=false
HOLDOUT_CONSUMED=false
```
"""
    report_path = output / "pilot_report.md"
    if report_path.exists():
        raise SystemExit(f"refusing to overwrite pilot output: {report_path}")
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
