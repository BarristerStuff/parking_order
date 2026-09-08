#!/usr/bin/env python3
"""Run one frozen parking_order_violation v1.2 candidate on the 239-row DEV manifest."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image

from fasttrack_common import Detector, direct_resize, fuse_views, letterbox, run_view, sha256_file, expand_box


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 239 or len({row["media_id"] for row in rows}) != 239:
        raise SystemExit("candidate manifest must contain 239 unique DEV rows")
    if any(row.get("split") != "train" for row in rows):
        raise SystemExit("DEV-only split guard rejected a non-train row")
    scopes: dict[str, int] = {}
    for row in rows:
        scopes[row["evaluation_scope"]] = scopes.get(row["evaluation_scope"], 0) + 1
    expected = {"primary_binary": 179, "gt_uncertain": 25, "boundary_challenge": 35}
    if scopes != expected:
        raise SystemExit(f"unexpected evaluation scopes: {scopes}")
    return rows


def infer_one(
    row: dict[str, str], config: dict[str, Any], prompt: str, detector: Detector | None
) -> dict[str, Any]:
    started = time.perf_counter()
    image_path = Path(config["dataset_root"]) / row["relative_path"]
    base = {key: row[key] for key in (
        "source_id", "media_id", "split", "group_key", "group_id", "sample_role",
        "v1_2_gt", "evaluation_scope", "relative_path",
    )}
    try:
        if not image_path.is_file() or sha256_file(image_path) != row["sha256"]:
            raise ValueError(f"DEV media binding failed: {row['media_id']}")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        prep = config["preprocess"]
        views: list[tuple[str, str, dict[str, Any]]] = []
        detections: list[dict[str, Any]] = []
        detector_latency = 0.0
        if prep["mode"] == "direct_resize":
            encoded, metadata = direct_resize(image, prep)
            views.append(("full", encoded, metadata))
        else:
            encoded, metadata = letterbox(image, prep)
            views.append(("full", encoded, metadata))
            if prep["mode"] == "detector_guided_context":
                if detector is None:
                    raise RuntimeError("F2 detector was not initialized")
                detections, detector_latency = detector.detect(image)
                for index, detection in enumerate(detections[: int(prep["max_context_crops"])], start=1):
                    crop_box = expand_box(
                        detection["bbox"], float(prep["context_expansion_factor"]), image.width, image.height
                    )
                    crop = image.crop(tuple(crop_box))
                    crop_encoded, crop_metadata = letterbox(crop, prep)
                    crop_metadata.update({"crop_box": crop_box, "detection": detection})
                    views.append((f"context_{index}", crop_encoded, crop_metadata))

        view_results: list[dict[str, Any]] = []
        for view_name, image_b64, metadata in views:
            view_result = run_view(image_b64, view_name, prompt, config)
            view_result["preprocess"] = metadata
            view_results.append(view_result)
        status, final_label, final_evidence, final_reason = fuse_views(view_results)
        all_http = all(view["http_status"] == 200 for view in view_results)
        all_schema = all(view["schema_success"] for view in view_results)
        all_semantic = all(view["semantic_protocol_ok"] for view in view_results)
        protocol_success = status == "ok" and all_http and all_schema and all_semantic
        crop_views = view_results[1:]
        return {
            **base, "status": status, "model_label": final_label, "evidence_type": final_evidence,
            "reason": final_reason, "http_success": all_http, "schema_success": all_schema,
            "semantic_protocol_success": all_semantic, "protocol_success": protocol_success,
            "views": view_results, "images_per_logical_request": len(view_results),
            "physical_request_count": sum(int(view["http_attempt_count"]) for view in view_results),
            "extra_crop_count": len(crop_views), "extra_model_request_count": len(crop_views),
            "extra_physical_request_count": sum(int(view["http_attempt_count"]) for view in crop_views),
            "detector_method": config.get("detector", {}).get("method", "none"),
            "detector_latency_seconds": detector_latency, "detections": detections,
            "latency_seconds": round(time.perf_counter() - started, 6), "error": "",
        }
    except Exception as exc:
        return {
            **base, "status": "inference_failure", "model_label": "", "evidence_type": "", "reason": "",
            "http_success": False, "schema_success": False, "semantic_protocol_success": False,
            "protocol_success": False, "views": [], "images_per_logical_request": 0,
            "physical_request_count": 0, "extra_crop_count": 0, "extra_model_request_count": 0,
            "extra_physical_request_count": 0,
            "detector_method": config.get("detector", {}).get("method", "none"),
            "detector_latency_seconds": 0.0, "detections": [],
            "latency_seconds": round(time.perf_counter() - started, 6),
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mapping-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping_summary.read_text(encoding="utf-8"))
    if config.get("stage") != "V1.2_FASTTRACK_DEV" or config.get("allowed_split") != "train":
        raise SystemExit("candidate stage/split guard failed")
    if config.get("val_consumed") is not False or config.get("holdout_consumed") is not False:
        raise SystemExit("candidate consumption guard failed")
    if sha256_file(args.prompt) != mapping["prompt_sha256"]:
        raise SystemExit("frozen prompt SHA-256 mismatch")
    rows = read_manifest(args.manifest)
    dataset_root = Path(config["dataset_root"])
    for row in rows:
        image_path = dataset_root / row["relative_path"]
        if not image_path.is_file() or sha256_file(image_path) != row["sha256"]:
            raise SystemExit(f"DEV preflight failed: {row['media_id']}")
    if args.check_only:
        print(json.dumps({
            "status": "check_ok", "candidate": config["candidate"], "manifest_count": len(rows),
            "allowed_split": "train", "val_consumed": False, "holdout_consumed": False,
        }, sort_keys=True))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if config["preprocess"]["mode"] == "detector_guided_context":
        configured_python = Path(config["detector"]["python"]).resolve()
        if Path(sys.executable).resolve() != configured_python:
            raise SystemExit(f"F2 must run with configured detector Python: {configured_python}")
        detector: Detector | None = Detector(config, args.output_dir)
    else:
        detector = None
    prompt = args.prompt.read_text(encoding="utf-8")
    results_path = args.output_dir / "predictions.jsonl"
    completed: set[str] = set()
    if results_path.exists():
        prior = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        prior_ids = [row["media_id"] for row in prior]
        if len(prior_ids) != len(set(prior_ids)):
            raise SystemExit("existing predictions contain duplicate media_id")
        manifest_ids = {row["media_id"] for row in rows}
        if not set(prior_ids).issubset(manifest_ids):
            raise SystemExit("existing predictions contain non-manifest media_id")
        completed.update(prior_ids)
    pending = [row for row in rows if row["media_id"] not in completed]
    if args.limit is not None:
        pending = pending[: args.limit]
    lock = threading.Lock()
    new_status_counts: dict[str, int] = {}
    with results_path.open("a", encoding="utf-8") as output:
        with ThreadPoolExecutor(max_workers=int(config["max_workers"])) as pool:
            futures = {pool.submit(infer_one, row, config, prompt, detector): row for row in pending}
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                with lock:
                    output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                    output.flush()
                    os.fsync(output.fileno())
                new_status_counts[result["status"]] = new_status_counts.get(result["status"], 0) + 1
                print(
                    f"FASTTRACK_PROGRESS candidate={config['candidate']} completed={index}/{len(pending)} "
                    f"media_id={result['media_id']} status={result['status']} label={result['model_label']} "
                    f"views={result['images_per_logical_request']}", flush=True,
                )
    all_rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_summary = {
        "status": "completed" if len(all_rows) == len(rows) else "partial",
        "candidate": config["candidate"], "manifest_count": len(rows), "result_count": len(all_rows),
        "new_result_count": len(pending), "new_status_counts": new_status_counts,
        "physical_request_count": sum(int(row.get("physical_request_count", 0)) for row in all_rows),
        "extra_crop_count": sum(int(row.get("extra_crop_count", 0)) for row in all_rows),
        "extra_model_request_count": sum(int(row.get("extra_model_request_count", 0)) for row in all_rows),
        "extra_physical_request_count": sum(int(row.get("extra_physical_request_count", 0)) for row in all_rows),
        "allowed_split": "train", "val_consumed": False, "holdout_consumed": False,
    }
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
