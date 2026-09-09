#!/usr/bin/env python3
"""Independent deterministic validation of the completed v2 DEV baseline."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
V2 = ROOT / "12_v2_not_in_bay"
TOOLS = V2 / "02_tools"
DEBUG = V2 / "03_debug"
OUTPUT = V2 / "04_vlm_dev_baseline"

GT = V2 / "01_gt_and_split" / "v2_0_gt.csv"
SPLIT = V2 / "01_gt_and_split" / "v2_split.csv"
BINDING = DEBUG / "v2_step2_binding.json"
MANIFEST = DEBUG / "v2_dev_evaluation_manifest.csv"
INFERENCE = DEBUG / "v2_dev_inference_input.jsonl"
CACHE = DEBUG / "v2_dev_vehicle_detections.jsonl"
FREEZE = DEBUG / "v2_step2_tool_freeze.json"
PREDICTIONS = OUTPUT / "predictions.jsonl"
RUN = OUTPUT / "run_summary.json"
METRICS = OUTPUT / "metrics.json"
SUBGROUPS = OUTPUT / "subgroup_metrics.csv"
RESULT = OUTPUT / "independent_validation.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_sidecar(path: Path, errors: list[str]) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    expected = f"{sha256_file(path)}  {path.name}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
        errors.append(f"SHA-256 sidecar mismatch: {path.name}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    errors: list[str] = []
    required = [
        GT, SPLIT, BINDING, MANIFEST, INFERENCE, CACHE, FREEZE,
        PREDICTIONS, RUN, METRICS, SUBGROUPS,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        errors.append("missing required artifact: " + ", ".join(missing))
        atomic_json(RESULT, {"status": "invalid", "error_count": len(errors), "errors": errors})
        raise SystemExit(1)

    for path in (GT, SPLIT, MANIFEST, INFERENCE, CACHE, FREEZE):
        assert_sidecar(path, errors)

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    if binding.get("gt_sha256") != sha256_file(GT):
        errors.append("GT changed after Step 2 binding")
    if binding.get("split_sha256") != sha256_file(SPLIT):
        errors.append("split changed after Step 2 binding")

    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    manifest_by_token = {row["sample_token"]: row for row in manifest}
    if len(manifest) != 238 or len(manifest_by_token) != 238:
        errors.append("evaluation manifest is not 238 unique rows")
    if any(row.get("split") != "DEV" for row in manifest):
        errors.append("evaluation manifest contains a non-DEV row")

    inference = read_jsonl(INFERENCE)
    cache = read_jsonl(CACHE)
    required_inference_fields = {"sample_token", "image_path", "image_sha256", "detections"}
    forbidden_fields = {
        "media_id", "group_key", "v2_gt", "scope", "split", "target_bbox_hint",
        "source_id", "sample_role", "original_filename",
    }
    if len(inference) != 238 or len({row.get("sample_token") for row in inference}) != 238:
        errors.append("opaque inference input is not 238 unique rows")
    if any(set(row) != required_inference_fields for row in inference):
        errors.append("opaque inference schema differs from the frozen contract")
    if any(set(row).intersection(forbidden_fields) for row in inference):
        errors.append("label-bearing field leaked into opaque inference input")
    inference_tokens = {row.get("sample_token") for row in inference}
    if inference_tokens != set(manifest_by_token):
        errors.append("inference token set does not equal DEV evaluation token set")

    cache_tokens = {row.get("sample_token") for row in cache}
    if len(cache) != 238 or len(cache_tokens) != 238 or cache_tokens != inference_tokens:
        errors.append("detector cache does not exactly cover opaque DEV input")
    for row in cache:
        if row.get("sample_token") != row.get("image_sha256"):
            errors.append("detector cache token/image SHA mismatch")
            break

    predictions = read_jsonl(PREDICTIONS)
    prediction_by_token = {row.get("sample_token"): row for row in predictions}
    if len(predictions) != 238 or len(prediction_by_token) != 238:
        errors.append("predictions are not 238 unique rows")
    if set(prediction_by_token) != set(manifest_by_token):
        errors.append("prediction token set does not equal frozen DEV input")
    if any(row.get("status") not in {"ok", "no_eligible_detection"} for row in predictions):
        errors.append("completed baseline contains a failed inference status")
    if any(row.get("logical_json_success") is not True for row in predictions):
        errors.append("completed baseline contains a logical JSON failure")

    run = json.loads(RUN.read_text(encoding="utf-8"))
    if run.get("status") != "completed" or run.get("completed_image_count") != 238:
        errors.append("run summary is not a complete 238-image execution")
    if run.get("logical_crop_json_success_rate") != 1.0:
        errors.append("logical JSON success is not 100 percent")
    if run.get("physical_json_schema_success_rate") != 1.0:
        errors.append("physical JSON schema success is not 100 percent")
    if run.get("max_ollama_concurrency") != 2:
        errors.append("Ollama concurrency was not frozen at 2")
    if run.get("val_image_reads") != 0 or run.get("holdout_image_reads") != 0:
        errors.append("run summary reports VAL/HOLDOUT image access")

    joined = [{**manifest_by_token[token], **prediction_by_token[token]} for token in manifest_by_token]
    primary = [
        row for row in joined
        if row["scope"] == "primary_binary" and row["v2_gt"] in {"positive", "negative"}
    ]
    tp = sum(row["v2_gt"] == "positive" and row["model_label"] == "positive" for row in primary)
    fn = sum(row["v2_gt"] == "positive" and row["model_label"] != "positive" for row in primary)
    fp = sum(row["v2_gt"] == "negative" and row["model_label"] == "positive" for row in primary)
    tn = sum(row["v2_gt"] == "negative" and row["model_label"] != "positive" for row in primary)
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    primary_metrics = metrics.get("primary_binary", {})
    if (tp, fp, tn, fn) != (
        primary_metrics.get("tp"), primary_metrics.get("fp"),
        primary_metrics.get("tn"), primary_metrics.get("fn"),
    ):
        errors.append("primary confusion matrix does not match independent recomputation")

    with SUBGROUPS.open(encoding="utf-8", newline="") as handle:
        subgroup_rows = list(csv.DictReader(handle))
    if len(subgroup_rows) != 23 or len({row["group_key"] for row in subgroup_rows}) != 23:
        errors.append("subgroup metric table does not contain 23 unique groups")
    if metrics.get("source_type") != "AIGC" or metrics.get("production_claim") != "NOT_AUTHORIZED":
        errors.append("AIGC/non-production reporting boundary is missing")

    result = {
        "status": "valid" if not errors else "invalid",
        "error_count": len(errors),
        "checks": {
            "frozen_gt_and_split_unchanged": binding.get("gt_sha256") == sha256_file(GT)
            and binding.get("split_sha256") == sha256_file(SPLIT),
            "dev_manifest_exactly_238": len(manifest) == 238 and len(manifest_by_token) == 238,
            "no_val_or_holdout_manifest_rows": not any(row.get("split") != "DEV" for row in manifest),
            "opaque_inference_input_no_label_fields": not any(
                set(row).intersection(forbidden_fields) for row in inference
            ),
            "detector_cache_exactly_covers_dev_tokens": len(cache) == 238 and cache_tokens == inference_tokens,
            "prediction_set_exactly_covers_dev_tokens": len(predictions) == 238
            and set(prediction_by_token) == set(manifest_by_token),
            "json_schema_success_100_percent": run.get("logical_crop_json_success_rate") == 1.0
            and run.get("physical_json_schema_success_rate") == 1.0,
            "primary_confusion_recomputed": (tp, fp, tn, fn) == (
                primary_metrics.get("tp"), primary_metrics.get("fp"),
                primary_metrics.get("tn"), primary_metrics.get("fn"),
            ),
            "subgroup_table_23_groups": len(subgroup_rows) == 23
            and len({row["group_key"] for row in subgroup_rows}) == 23,
        },
        "dev_image_count": len(manifest),
        "prediction_status_counts": dict(sorted(Counter(row["status"] for row in predictions).items())),
        "primary_confusion_recomputed": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "errors": errors,
    }
    atomic_json(RESULT, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
