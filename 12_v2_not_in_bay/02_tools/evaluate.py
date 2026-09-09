#!/usr/bin/env python3
"""Join frozen v2 GT only after the complete DEV VLM prediction set is written."""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
V2 = ROOT / "12_v2_not_in_bay"
TOOLS = V2 / "02_tools"
DEBUG = V2 / "03_debug"
OUTPUT = V2 / "04_vlm_dev_baseline"

GT = V2 / "01_gt_and_split" / "v2_0_gt.csv"
SPLIT = V2 / "01_gt_and_split" / "v2_split.csv"
CONFIG = TOOLS / "v2_dev_baseline_config.json"
BINDING = DEBUG / "v2_step2_binding.json"
MANIFEST = DEBUG / "v2_dev_evaluation_manifest.csv"
PREDICTIONS = OUTPUT / "predictions.jsonl"
RUN_SUMMARY = OUTPUT / "run_summary.json"

METRICS = OUTPUT / "metrics.json"
SUBGROUPS = OUTPUT / "subgroup_metrics.csv"
ERRORS = OUTPUT / "errors.csv"
LATENCY = OUTPUT / "latency.json"
DECISION = OUTPUT / "decision.json"
REPORT = OUTPUT / "dev_baseline_report.md"

MANIFEST_FIELDS = [
    "media_id", "sample_token", "group_key", "v2_gt", "scope", "split",
    "source_id", "formal_relative_path", "image_path", "image_sha256", "width", "height",
]


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    expected = f"{sha256_file(path)}  {path.name}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"SHA-256 sidecar mismatch: {path}")


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def wilson_95(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    ) / denominator
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = math.ceil((len(values) - 1) * q)
    return values[max(0, min(len(values) - 1, index))]


def confusion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for row in rows:
        label = row["v2_gt"]
        predicted_positive = row["model_label"] == "positive"
        if label == "positive":
            if predicted_positive:
                tp += 1
            else:
                fn += 1
        elif label == "negative":
            if predicted_positive:
                fp += 1
            else:
                tn += 1
    recall = ratio(tp, tp + fn)
    fpr = ratio(fp, fp + tn)
    precision = ratio(tp, tp + fp)
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "fpr": fpr,
        "recall_wilson_95": wilson_95(tp, tp + fn),
        "fpr_wilson_95": wilson_95(fp, fp + tn),
    }


def group_metric(group: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [row for row in rows if row["v2_gt"] == "positive"]
    negative = [row for row in rows if row["v2_gt"] == "negative"]
    uncertain = [row for row in rows if row["v2_gt"] == "uncertain"]
    positive_tp = sum(row["model_label"] == "positive" for row in positive)
    negative_fp = sum(row["model_label"] == "positive" for row in negative)
    labels = Counter(row["model_label"] for row in rows)
    statuses = Counter(row["status"] for row in rows)
    no_eligible = sum(row["eligible_detection_count"] == 0 for row in rows)
    return {
        "group_key": group,
        "scope": rows[0]["scope"],
        "row_count": len(rows),
        "positive_count": len(positive),
        "negative_count": len(negative),
        "uncertain_gt_count": len(uncertain),
        "positive_tp": positive_tp,
        "positive_fn": len(positive) - positive_tp,
        "positive_recall": ratio(positive_tp, len(positive)),
        "positive_recall_wilson_95": wilson_95(positive_tp, len(positive)),
        "negative_fp": negative_fp,
        "negative_tn": len(negative) - negative_fp,
        "negative_fpr": ratio(negative_fp, len(negative)),
        "negative_fpr_wilson_95": wilson_95(negative_fp, len(negative)),
        "prediction_positive_count": labels["positive"],
        "prediction_negative_count": labels["negative"],
        "prediction_uncertain_count": labels["uncertain"],
        "prediction_uncertain_rate": ratio(labels["uncertain"], len(rows)),
        "no_eligible_detection_count": no_eligible,
        "no_eligible_detection_rate": ratio(no_eligible, len(rows)),
        "status_ok_count": statuses["ok"],
        "status_non_ok_count": len(rows) - statuses["ok"],
    }


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def main() -> None:
    required = [GT, SPLIT, CONFIG, BINDING, MANIFEST, PREDICTIONS, RUN_SUMMARY]
    if not all(path.is_file() for path in required):
        raise SystemExit("required evaluator input missing")
    for path in (GT, SPLIT, MANIFEST):
        assert_sidecar(path)

    output_paths = [METRICS, SUBGROUPS, ERRORS, LATENCY, DECISION, REPORT]
    existing = [str(path) for path in output_paths if path.exists()]
    if existing:
        raise SystemExit("refusing to overwrite evaluator outputs: " + ", ".join(existing))

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    if binding.get("gt_sha256") != sha256_file(GT) or binding.get("split_sha256") != sha256_file(SPLIT):
        raise SystemExit("frozen GT/split hash changed after Step 2 binding")
    if binding.get("config_sha256") != sha256_file(CONFIG):
        raise SystemExit("baseline config changed after Step 2 binding")
    run_summary = json.loads(RUN_SUMMARY.read_text(encoding="utf-8"))
    if run_summary.get("status") != "completed" or run_summary.get("completed_image_count") != 238:
        raise SystemExit("cannot evaluate a stopped or incomplete VLM run")
    if run_summary.get("logical_crop_json_success_rate", 0.0) < 0.95:
        raise SystemExit("logical JSON success gate failed")
    if run_summary.get("physical_json_schema_success_rate", 0.0) < 0.95:
        raise SystemExit("physical JSON success gate failed")

    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != MANIFEST_FIELDS:
            raise SystemExit("evaluation manifest schema mismatch")
        manifest_rows = list(reader)
    if len(manifest_rows) != 238 or any(row["split"] != "DEV" for row in manifest_rows):
        raise SystemExit("evaluation manifest is not exactly the v2 DEV partition")
    manifest_by_token = {row["sample_token"]: row for row in manifest_rows}
    if len(manifest_by_token) != 238:
        raise SystemExit("duplicate sample token in evaluation manifest")

    predictions = [
        json.loads(line) for line in PREDICTIONS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    prediction_by_token = {row["sample_token"]: row for row in predictions}
    if len(predictions) != 238 or len(prediction_by_token) != 238:
        raise SystemExit("prediction count/token uniqueness failure")
    if set(prediction_by_token) != set(manifest_by_token):
        raise SystemExit("prediction token set does not equal frozen DEV manifest")

    joined: list[dict[str, Any]] = []
    for token, manifest in manifest_by_token.items():
        prediction = prediction_by_token[token]
        if prediction.get("model_label") not in {"positive", "negative", "uncertain"}:
            raise SystemExit(f"invalid model label: {token}")
        joined.append({**manifest, **prediction})

    primary = [
        row for row in joined
        if row["scope"] == "primary_binary" and row["v2_gt"] in {"positive", "negative"}
    ]
    primary_metrics = confusion(primary)
    group_rows = defaultdict(list)
    for row in joined:
        group_rows[row["group_key"]].append(row)
    group_results = {
        group: group_metric(group, sorted(rows, key=lambda row: int(row["source_id"])))
        for group, rows in sorted(group_rows.items())
    }
    hn01 = group_results["hn01-gate-queue"]
    p01 = group_results["p01-outside-legal-bay-clear"]
    p03 = group_results["p03-span-two-bays"]
    p04 = group_results["p04-angled-footprint-outside"]
    p05 = group_results["p05-multi-vehicle-at-least-one-violation"]
    p06 = group_results["p06-nose-or-tail-intrudes-aisle"]
    p02 = group_results["p02-cross-single-boundary-line"]

    p03_good = p03["positive_recall"] is not None and p03["positive_recall"] >= 0.70
    p06_good = p06["negative_fpr"] is not None and p06["negative_fpr"] <= 0.10
    p01_bad = p01["positive_recall"] is not None and p01["positive_recall"] < 0.70
    p04_bad = p04["negative_fpr"] is not None and p04["negative_fpr"] > 0.10
    narrowing_signal = p03_good and p06_good and (p01_bad or p04_bad)
    overall_recall_pass = primary_metrics["recall"] is not None and primary_metrics["recall"] > 0.70
    fpr_gate_pass = (
        primary_metrics["fpr"] is not None
        and primary_metrics["fpr"] <= 0.10
        and p02["negative_fpr"] is not None
        and p02["negative_fpr"] <= 0.20
    )
    if narrowing_signal:
        recommendation = "DEFINITION_NARROWING_SIGNAL__RETURN_TO_USER"
    elif overall_recall_pass and fpr_gate_pass:
        recommendation = "PROMPT_AND_PREPROCESSING_OPTIMIZATION_ELIGIBLE_AFTER_SEPARATE_USER_AUTHORIZATION"
    elif overall_recall_pass:
        recommendation = "RECALL_PASS_BUT_NEGATIVE_FPR_GATE_FAIL__RETURN_TO_USER"
    else:
        recommendation = "CLOSE_SINGLE_RGB_PLAN__RETURN_TO_USER"
    decision = {
        "decision_rule_version": "user_2026-09-08_step2_instruction_interpreted_with_v2_pilot_safety_fpr_gates",
        "primary_positive_recall_strictly_gt_0_70": overall_recall_pass,
        "primary_negative_fpr_lte_0_10": primary_metrics["fpr"] is not None and primary_metrics["fpr"] <= 0.10,
        "p02_fpr_lte_0_20": p02["negative_fpr"] is not None and p02["negative_fpr"] <= 0.20,
        "p03_recall_gte_0_70": p03_good,
        "p06_fpr_lte_0_10": p06_good,
        "p01_recall_lt_0_70": p01_bad,
        "p04_fpr_gt_0_10": p04_bad,
        "definition_narrowing_signal": narrowing_signal,
        "recommendation": recommendation,
        "automatic_next_step_authorized": False,
    }

    physical_attempts = [
        attempt
        for row in joined
        for vehicle in row["vehicle_results"]
        for attempt in vehicle["call"]["attempts"]
    ]
    logical_latencies = [float(row["latency_seconds"]) for row in joined]
    physical_latencies = [float(attempt["latency_seconds"]) for attempt in physical_attempts]
    latency = {
        "logical_image_latency_seconds": {
            "p50": statistics.median(logical_latencies),
            "p95": percentile(logical_latencies, 0.95),
        },
        "physical_vlm_request_latency_seconds": {
            "p50": statistics.median(physical_latencies) if physical_latencies else None,
            "p95": percentile(physical_latencies, 0.95),
        },
        "logical_image_count": len(logical_latencies),
        "physical_request_count": len(physical_latencies),
    }
    errors = [
        {
            "media_id": row["media_id"],
            "sample_token": row["sample_token"],
            "group_key": row["group_key"],
            "v2_gt": row["v2_gt"],
            "scope": row["scope"],
            "status": row["status"],
            "model_label": row["model_label"],
            "eligible_detection_count": row["eligible_detection_count"],
            "error": row["error"],
        }
        for row in joined
        if row["status"] != "ok"
    ]
    metrics = {
        "status": "completed",
        "stage": config["stage"],
        "candidate": config["candidate"],
        "source_type": config["source_type"],
        "gt_basis": config["gt_basis"],
        "production_claim": "NOT_AUTHORIZED",
        "dev_image_count": len(joined),
        "primary_binary": primary_metrics,
        "hn01_secondary": {
            "negative_count": hn01["negative_count"],
            "false_positive_count": hn01["negative_fp"],
            "fpr": hn01["negative_fpr"],
            "fpr_wilson_95": hn01["negative_fpr_wilson_95"],
        },
        "gt_uncertain_excluded_count": sum(row["v2_gt"] == "uncertain" for row in joined),
        "model_prediction_counts": dict(sorted(Counter(row["model_label"] for row in joined).items())),
        "no_eligible_detection_count": sum(row["eligible_detection_count"] == 0 for row in joined),
        "non_ok_result_count": len(errors),
        "ollama_logical_crop_requests": run_summary["logical_crop_request_count"],
        "ollama_physical_requests": run_summary["physical_request_count"],
        "logical_json_success_rate": run_summary["logical_crop_json_success_rate"],
        "physical_json_schema_success_rate": run_summary["physical_json_schema_success_rate"],
        "subgroup_metrics_path": str(SUBGROUPS),
        "decision_path": str(DECISION),
        "binding": {
            "definition_sha256": binding["definition_sha256"],
            "gt_sha256": binding["gt_sha256"],
            "split_sha256": binding["split_sha256"],
            "prompt_sha256": binding["prompt_sha256"],
            "config_sha256": binding["config_sha256"],
        },
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "val_consumed": False,
        "holdout_consumed": False,
    }

    subgroup_fields = [
        "group_key", "scope", "row_count", "positive_count", "negative_count",
        "uncertain_gt_count", "positive_tp", "positive_fn", "positive_recall",
        "positive_recall_wilson_95", "negative_fp", "negative_tn", "negative_fpr",
        "negative_fpr_wilson_95", "prediction_positive_count", "prediction_negative_count",
        "prediction_uncertain_count", "prediction_uncertain_rate",
        "no_eligible_detection_count", "no_eligible_detection_rate",
        "status_ok_count", "status_non_ok_count",
    ]
    subgroup_csv_rows = [
        {field: stringify(metric[field]) for field in subgroup_fields}
        for _, metric in sorted(group_results.items())
    ]
    error_fields = [
        "media_id", "sample_token", "group_key", "v2_gt", "scope", "status",
        "model_label", "eligible_detection_count", "error",
    ]
    report = f"""# parking_order v2.0 Step 2 DEV-only stronger VLM baseline

STAGE=V2_STEP2_STRONGER_VLM_DEV_BASELINE
PILOT_OR_DEV=DEV_BASELINE_DIAGNOSTIC
SOURCE_TYPE=AIGC
GT_BASIS=group_intent_v2.0_with_p05_visual_adjudication
PRODUCTION_CLAIM=NOT_AUTHORIZED
TP={primary_metrics["tp"]}
FP={primary_metrics["fp"]}
TN={primary_metrics["tn"]}
FN={primary_metrics["fn"]}
RECALL={primary_metrics["recall"]}
FPR={primary_metrics["fpr"]}
P01_RECALL={p01["positive_recall"]}
P03_RECALL={p03["positive_recall"]}
P04_FPR={p04["negative_fpr"]}
P05_RECALL={p05["positive_recall"]}
P05_FPR={p05["negative_fpr"]}
P06_FPR={p06["negative_fpr"]}
HN01_FPR={hn01["negative_fpr"]}
P50={latency["logical_image_latency_seconds"]["p50"]}
P95={latency["logical_image_latency_seconds"]["p95"]}
OLLAMA_REQUESTS={run_summary["physical_request_count"]}
GEOMETRY_ONLY_RECALL=N/A
VLM_ONLY_RECALL={primary_metrics["recall"]}
LOGICAL_JSON_SUCCESS_RATE={run_summary["logical_crop_json_success_rate"]}
PHYSICAL_JSON_SCHEMA_SUCCESS_RATE={run_summary["physical_json_schema_success_rate"]}
VAL_IMAGE_READS=0
HOLDOUT_IMAGE_READS=0

## Interpretation boundary

This is one DEV-only AIGC baseline using frozen v2 GT and a single frozen
five-question perception prompt. It is neither Human Gold nor a production,
robot-camera, real-world, VAL, or HOLDOUT accuracy claim. The baseline does not
authorize a subsequent prompt or preprocessing change.

## Main metrics

- Primary binary TP/FP/TN/FN: {primary_metrics["tp"]}/{primary_metrics["fp"]}/{primary_metrics["tn"]}/{primary_metrics["fn"]}
- Primary positive recall: {primary_metrics["recall"]} with Wilson 95% interval {primary_metrics["recall_wilson_95"]}
- Primary negative FPR: {primary_metrics["fpr"]} with Wilson 95% interval {primary_metrics["fpr_wilson_95"]}
- hn01 gate-queue secondary FPR: {hn01["negative_fpr"]} over n={hn01["negative_count"]}
- GT-uncertain excluded from primary confusion matrix: {metrics["gt_uncertain_excluded_count"]}
- No eligible detector box: {metrics["no_eligible_detection_count"]}

## Requested subgroup focus

| Group | Correct metric | Value | Denominator |
|---|---|---:|---:|
| p01 | positive recall | {p01["positive_recall"]} | {p01["positive_count"]} |
| p03 | positive recall | {p03["positive_recall"]} | {p03["positive_count"]} |
| p04 | negative FPR | {p04["negative_fpr"]} | {p04["negative_count"]} |
| p05 positive | positive recall | {p05["positive_recall"]} | {p05["positive_count"]} |
| p05 negative | negative FPR | {p05["negative_fpr"]} | {p05["negative_count"]} |
| p06 | negative FPR | {p06["negative_fpr"]} | {p06["negative_count"]} |
| hn01 | secondary negative FPR | {hn01["negative_fpr"]} | {hn01["negative_count"]} |

## Decision signal

Recommendation: {recommendation}

- Definition-narrowing signal (p03 recall >=0.70 and p06 FPR <=0.10 while p01 recall <0.70 or p04 FPR >0.10): {narrowing_signal}
- Primary recall strictly greater than 0.70: {overall_recall_pass}
- Primary FPR <=0.10 and p02 FPR <=0.20: {fpr_gate_pass}
- No automatic next step is authorized. Return to the user with this report before changing prompt, preprocessing, definition, GT, split, or data access.
"""

    atomic_text(METRICS, json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_csv(SUBGROUPS, subgroup_fields, subgroup_csv_rows)
    atomic_csv(ERRORS, error_fields, errors)
    atomic_text(LATENCY, json.dumps(latency, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_text(DECISION, json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_text(REPORT, report)
    print(json.dumps(
        {
            "status": "evaluated",
            "primary_binary": primary_metrics,
            "recommendation": recommendation,
            "subgroup_count": len(group_results),
        },
        ensure_ascii=False,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
