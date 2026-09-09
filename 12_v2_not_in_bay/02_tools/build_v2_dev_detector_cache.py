#!/usr/bin/env python3
"""Build one new, isolated YOLO11n cache for exactly the v2 DEV image set.

The detector receives only an opaque-token manifest.  It never reads group, GT,
split, source ID, target hint, or any VAL/HOLDOUT path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
V2 = ROOT / "12_v2_not_in_bay"
TOOLS = V2 / "02_tools"
DEBUG = V2 / "03_debug"
DATASET_ROOT = Path("/home/yanbo/net_vlm_xunjian_dataset").resolve()
CONFIG = TOOLS / "v2_dev_baseline_config.json"
BINDING = DEBUG / "v2_step2_binding.json"
INPUT = DEBUG / "v2_dev_detector_input.jsonl"

CACHE = DEBUG / "v2_dev_vehicle_detections.jsonl"
INFERENCE_INPUT = DEBUG / "v2_dev_inference_input.jsonl"
SUMMARY = DEBUG / "v2_dev_detector_cache_summary.json"
VALIDATION = DEBUG / "v2_dev_detector_cache_validation.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path, fields: set[str]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or set(value) != fields:
                raise SystemExit(f"invalid inference input schema at line {line_number}")
            values.append(value)
    return values


def atomic_text(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def ensure_sha_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    expected = f"{sha256_file(path)}  {path.name}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"input SHA-256 sidecar mismatch: {path}")


def validate_inputs(config: dict[str, Any], binding: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if config.get("stage") != "V2_STEP2_STRONGER_VLM_DEV_BASELINE":
        raise SystemExit("invalid baseline stage")
    if config.get("allowed_split") != "DEV" or config.get("model") != "qwen3.5:4b":
        raise SystemExit("baseline model/split guard failed")
    if config.get("val_access_allowed") is not False or config.get("holdout_access_allowed") is not False:
        raise SystemExit("VAL/HOLDOUT access guard failed")
    if binding.get("dev_count") != 238 or binding.get("new_v2_dev_detector_run_required") is not True:
        raise SystemExit("binding does not authorize a new full v2 DEV detector cache")
    if binding.get("config_sha256") != sha256_file(CONFIG):
        raise SystemExit("frozen baseline config hash mismatch")
    if len(rows) != 238 or len({row["sample_token"] for row in rows}) != 238:
        raise SystemExit("detector input must contain 238 unique v2 DEV tokens")
    for row in rows:
        token = row["sample_token"]
        image_path = Path(row["image_path"]).resolve()
        if token != row["image_sha256"] or len(token) != 64:
            raise SystemExit("opaque token/image SHA binding mismatch")
        if DATASET_ROOT not in image_path.parents or not image_path.is_file():
            raise SystemExit(f"unsafe or missing detector image path: {image_path}")
        if sha256_file(image_path) != row["image_sha256"]:
            raise SystemExit(f"detector image SHA mismatch: {image_path}")


def load_detector(config: dict[str, Any]) -> Any:
    detector = config["detector"]
    checkpoint = Path(detector["checkpoint"])
    if not checkpoint.is_file() or sha256_file(checkpoint) != detector["checkpoint_sha256"]:
        raise SystemExit("YOLO checkpoint SHA-256 mismatch")
    # Keep Ultralytics settings under the authorized new revision, never under user-global config.
    os.environ["YOLO_CONFIG_DIR"] = str((DEBUG / ".ultralytics").resolve())
    from ultralytics import YOLO

    model = YOLO(str(checkpoint))
    expected = {int(class_id): class_name for class_id, class_name in detector["classes"].items()}
    for class_id, class_name in expected.items():
        if model.names[class_id] != class_name:
            raise SystemExit(
                f"YOLO class mapping mismatch: {class_id}={model.names[class_id]!r}, expected {class_name!r}"
            )
    return model


def detect_one(model: Any, row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    detector = config["detector"]
    started = time.perf_counter()
    result = model.predict(
        source=row["image_path"],
        classes=[int(value) for value in detector["classes"]],
        conf=float(detector["confidence_threshold"]),
        imgsz=int(detector["inference_size"]),
        device=detector["device"],
        verbose=False,
        save=False,
    )[0]
    detections: list[dict[str, Any]] = []
    if result.boxes is not None:
        for xyxy, confidence, class_id in zip(
            result.boxes.xyxy.cpu().tolist(),
            result.boxes.conf.cpu().tolist(),
            result.boxes.cls.cpu().tolist(),
        ):
            class_index = int(class_id)
            class_name = detector["classes"].get(str(class_index))
            if class_name is None:
                raise RuntimeError(f"unexpected detector class ID: {class_index}")
            detections.append(
                {
                    "bbox": [round(float(value), 3) for value in xyxy],
                    "class_id": class_index,
                    "class_name": class_name,
                    "confidence": round(float(confidence), 6),
                }
            )
    detections.sort(
        key=lambda item: (
            -item["confidence"],
            item["class_id"],
            item["bbox"][0],
            item["bbox"][1],
            item["bbox"][2],
            item["bbox"][3],
        )
    )
    return {
        "sample_token": row["sample_token"],
        "image_path": row["image_path"],
        "image_sha256": row["image_sha256"],
        "detections": detections,
        "detector_latency_seconds": round(time.perf_counter() - started, 6),
        "cache_source": "V2_DEV_NEW_LOCAL_YOLO11N",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    if not all(path.is_file() for path in (CONFIG, BINDING, INPUT)):
        raise SystemExit("required detector-cache input missing")
    ensure_sha_sidecar(INPUT)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    rows = read_jsonl(INPUT, {"sample_token", "image_path", "image_sha256"})
    validate_inputs(config, binding, rows)
    model = load_detector(config)
    if args.check_only:
        print(json.dumps(
            {
                "status": "check_ok",
                "dev_token_count": len(rows),
                "detector_checkpoint_sha256": config["detector"]["checkpoint_sha256"],
                "cache_output_exists": CACHE.exists(),
                "val_image_reads": 0,
                "holdout_image_reads": 0,
            },
            sort_keys=True,
        ))
        return

    outputs = [CACHE, INFERENCE_INPUT, SUMMARY, VALIDATION]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise SystemExit("refusing to overwrite existing detector outputs: " + ", ".join(existing))

    cache_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        # Recheck immediately before detector reads the DEV image.
        image_path = Path(row["image_path"])
        if sha256_file(image_path) != row["image_sha256"]:
            raise SystemExit(f"detector image changed after preflight: {image_path}")
        cache = detect_one(model, row, config)
        cache_rows.append(cache)
        print(
            f"V2_DETECTOR_PROGRESS completed={index}/{len(rows)} "
            f"token={row['sample_token'][:12]} detections={len(cache['detections'])}",
            flush=True,
        )

    if len({row["sample_token"] for row in cache_rows}) != len(rows):
        raise SystemExit("duplicate token in new detector cache")
    inference_rows = [
        {
            "sample_token": row["sample_token"],
            "image_path": row["image_path"],
            "image_sha256": row["image_sha256"],
            "detections": row["detections"],
        }
        for row in cache_rows
    ]
    if any(set(row) != {"sample_token", "image_path", "image_sha256", "detections"} for row in inference_rows):
        raise SystemExit("label-bearing field leaked into inference input")

    detection_count = sum(len(row["detections"]) for row in cache_rows)
    summary = {
        "stage": "V2_STEP2_STRONGER_VLM_DEV_BASELINE",
        "cache_source": "V2_DEV_NEW_LOCAL_YOLO11N",
        "f2_rerun": False,
        "v2_dev_detector_run": True,
        "dev_token_count": len(cache_rows),
        "detection_count": detection_count,
        "sample_detection_rate": sum(bool(row["detections"]) for row in cache_rows) / len(cache_rows),
        "class_counts": dict(sorted(Counter(
            detection["class_name"] for row in cache_rows for detection in row["detections"]
        ).items())),
        "detector_checkpoint_sha256": config["detector"]["checkpoint_sha256"],
        "detector_config": config["detector"],
        "detector_input_sha256": sha256_file(INPUT),
        "config_sha256": sha256_file(CONFIG),
        "val_image_reads": 0,
        "holdout_image_reads": 0,
    }
    validation = {
        "status": "valid",
        "error_count": 0,
        "cache_token_count": len(cache_rows),
        "expected_dev_token_count": len(rows),
        "duplicate_token_count": 0,
        "cache_source": summary["cache_source"],
        "f2_rerun": False,
        "v2_dev_detector_run": True,
        "cache_paths_under_dataset_root": True,
        "cache_image_hashes_rechecked": len(cache_rows),
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "inference_input_has_forbidden_fields": False,
    }
    atomic_jsonl(CACHE, cache_rows)
    atomic_jsonl(INFERENCE_INPUT, inference_rows)
    summary["cache_sha256"] = sha256_file(CACHE)
    summary["inference_input_sha256"] = sha256_file(INFERENCE_INPUT)
    atomic_text(SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_text(VALIDATION, json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    for path in (CACHE, INFERENCE_INPUT):
        atomic_text(path.with_name(path.name + ".sha256"), f"{sha256_file(path)}  {path.name}\n")
    print(json.dumps(
        {
            "status": "completed",
            "dev_token_count": len(cache_rows),
            "detection_count": detection_count,
            "cache_sha256": summary["cache_sha256"],
            "inference_input_sha256": summary["inference_input_sha256"],
            "val_image_reads": 0,
            "holdout_image_reads": 0,
        },
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
