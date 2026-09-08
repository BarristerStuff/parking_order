#!/usr/bin/env python3
"""Freeze P3-lite debug/pilot inputs and extract the existing F2 YOLO cache.

This preparation tool may read evaluation metadata solely to construct and
evaluate the fixed subsets. Geometry inference is implemented separately and
never receives GT, sample role, group, source_id, or label-bearing filenames.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
P3 = ROOT / "11_p3_lite_geometry"
DATASET = Path("/home/yanbo/net_vlm_xunjian_dataset")
FASTTRACK = ROOT / "10_v1_2_fasttrack"
MANIFEST = FASTTRACK / "02_experiments/F1/manifest.csv"
F2_CONFIG = FASTTRACK / "02_experiments/F2/config.json"
F2_PREDICTIONS = FASTTRACK / "02_experiments/F2/predictions.jsonl"
DEFINITION = FASTTRACK / "00_definition/parking_order_violation_v1.2.md"
PROMPT = FASTTRACK / "00_definition/prompt_v1_2.txt"
YOLO_CHECKPOINT = Path(
    "/home/yanbo/net_vlm_person_smoking_optimization/00_assets/"
    "person_detector/yolo11n.pt"
)

EXPECTED_HASHES = {
    DEFINITION: "64a3f3e73a31e97b1468827be24b1cdfbb713d531e76a60b6b36cfde8623cc67",
    PROMPT: "a6ae853aad36ed5e0ecf3856761b7ae34d0cf6933218ad68f3901dfa7cf1458d",
    MANIFEST: "cab3cb40780888e0016c70bf966597e83a9f0b41da25ae5df6f73112785ee997",
    F2_CONFIG: "c927e6edef16feb836fa3fcb2edee923caf05fa4ad4b09693a03b545ad2b56a2",
    F2_PREDICTIONS: "f1dcf2210d3ad248450f9f792ae01a782f1759f2d8c020e7d88a8a40d035f8c9",
    YOLO_CHECKPOINT: "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
}

DEBUG_MEDIA_IDS = [
    "IMG_007559", "IMG_007567", "IMG_007576", "IMG_007585", "IMG_007593",
    "IMG_007677", "IMG_007684", "IMG_007691", "IMG_007709", "IMG_007714",
]

PILOT_PLAN = [
    ("p01-outside-legal-bay-clear", 20, "positive", "p01_positive"),
    ("p05-multi-vehicle-at-least-one-violation", 20, "positive", "p05_positive"),
    ("hn01-gate-queue", 8, "negative", "gate_queue_negative"),
    ("n01-standard-inside-bay", 6, "negative", "ordinary_negative"),
    ("hn04-large-vehicle-compliant", 3, "negative", "large_vehicle_negative"),
    ("n02-close-to-line-but-inside", 3, "negative", "close_line_negative"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def evenly_spaced(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    """Return deterministic half-up evenly spaced rows, including endpoints."""
    rows = sorted(rows, key=lambda row: int(row["source_id"]))
    if count < 1 or count > len(rows):
        raise ValueError(f"invalid sample count {count} for population {len(rows)}")
    if count == len(rows):
        return rows
    if count == 1:
        return [rows[(len(rows) - 1) // 2]]
    indexes = [
        int(math.floor(i * (len(rows) - 1) / (count - 1) + 0.5))
        for i in range(count)
    ]
    if len(indexes) != len(set(indexes)):
        raise RuntimeError(f"even-spacing generated duplicate indexes: {indexes}")
    return [rows[index] for index in indexes]


def freeze_manifest(
    output: Path,
    rows: list[dict[str, str]],
    extra: dict[str, dict[str, str]] | None = None,
) -> None:
    extra = extra or {}
    fields = list(rows[0]) + sorted({key for values in extra.values() for key in values})
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, **extra.get(row["media_id"], {})})
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{sha256_file(output)}  {output.name}\n", encoding="utf-8"
    )


def geometry_input(row: dict[str, str], detection: dict[str, Any]) -> dict[str, Any]:
    # The token is content-derived and does not expose source_id/group/GT/role.
    return {
        "sample_token": row["sha256"],
        "image_path": str(DATASET / row["relative_path"]),
        "image_sha256": row["sha256"],
        "detections": detection["detections"],
        "detector_latency_seconds": detection.get("detector_latency_seconds", 0.0),
    }


def make_debug_contact_sheet(
    rows: list[dict[str, str]], detections: dict[str, dict[str, Any]], output: Path
) -> None:
    cards: list[np.ndarray] = []
    for row in rows:
        image = cv2.imread(str(DATASET / row["relative_path"]), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"cannot read debug image: {row['media_id']}")
        for detection in detections[row["media_id"]]["detections"]:
            x1, y1, x2, y2 = [int(round(value)) for value in detection["bbox"]]
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 210, 0), 4)
            cv2.putText(
                image,
                f"{detection['class_name']} {detection['confidence']:.2f}",
                (x1, max(24, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 210, 0),
                2,
                cv2.LINE_AA,
            )
        cv2.putText(
            image,
            row["media_id"],
            (20, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.15,
            (0, 0, 255),
            3,
            cv2.LINE_AA,
        )
        scale = min(640 / image.shape[1], 400 / image.shape[0])
        resized = cv2.resize(
            image,
            (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
        card = np.full((440, 660, 3), 245, dtype=np.uint8)
        top = (400 - resized.shape[0]) // 2
        left = (640 - resized.shape[1]) // 2 + 10
        card[top + 10 : top + 10 + resized.shape[0], left : left + resized.shape[1]] = resized
        cv2.putText(
            card,
            f"detections={len(detections[row['media_id']]['detections'])}",
            (14, 430),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )
        cards.append(card)
    sheet = np.vstack([np.hstack(cards[index : index + 2]) for index in range(0, 10, 2)])
    if not cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise RuntimeError(f"failed to write {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace preparation outputs")
    args = parser.parse_args()

    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        if actual != expected:
            raise SystemExit(f"frozen input hash mismatch: {path}: {actual} != {expected}")

    manifest_rows = list(csv.DictReader(MANIFEST.open(newline="", encoding="utf-8")))
    f2_rows = read_jsonl(F2_PREDICTIONS)
    if len(manifest_rows) != 239 or len(f2_rows) != 239:
        raise SystemExit("expected exactly 239 frozen DEV rows and F2 predictions")
    by_media = {row["media_id"]: row for row in manifest_rows}
    detections = {row["media_id"]: row for row in f2_rows}
    if len(by_media) != 239 or set(by_media) != set(detections):
        raise SystemExit("manifest/F2 media binding mismatch")
    for media_id, row in detections.items():
        if row.get("relative_path") != by_media[media_id]["relative_path"]:
            raise SystemExit(f"relative_path mismatch: {media_id}")
        if not row.get("detections"):
            raise SystemExit(f"missing vehicle detection: {media_id}")
        if any(det.get("class_name") not in {"car", "truck", "bus"} for det in row["detections"]):
            raise SystemExit(f"unexpected detector class: {media_id}")

    expected_dirs = [
        P3 / "00_design", P3 / "00_geometry_feasibility", P3 / "01_detector_cache",
        P3 / "02_geometry_debug", P3 / "03_pilot", P3 / "04_full_dev",
        P3 / "05_vlm_gate_verifier", P3 / "06_reports", P3 / "tools",
    ]
    for directory in expected_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    generated = [
        P3 / "01_detector_cache/vehicle_detections.jsonl",
        P3 / "01_detector_cache/cache_summary.json",
        P3 / "02_geometry_debug/debug_manifest.csv",
        P3 / "02_geometry_debug/debug_manifest.csv.sha256",
        P3 / "02_geometry_debug/geometry_input.jsonl",
        P3 / "02_geometry_debug/debug_bbox_contact_sheet.jpg",
        P3 / "03_pilot/pilot_manifest.csv",
        P3 / "03_pilot/pilot_manifest.csv.sha256",
        P3 / "03_pilot/vehicle_detections.jsonl",
        P3 / "03_pilot/geometry_input.jsonl",
        P3 / "00_design/input_freeze.json",
    ]
    existing = [path for path in generated if path.exists()]
    if existing and not args.force:
        raise SystemExit("refusing to replace frozen preparation outputs: " + ", ".join(map(str, existing)))

    cache_rows = []
    for row in manifest_rows:
        f2 = detections[row["media_id"]]
        cache_rows.append({
            "media_id": row["media_id"],
            "relative_path": row["relative_path"],
            "image_sha256": row["sha256"],
            "detections": f2["detections"],
            "detector_latency_seconds": f2.get("detector_latency_seconds", 0.0),
            "cache_source": "F2_EXISTING_DETECTOR_RUN",
        })
    cache_path = P3 / "01_detector_cache/vehicle_detections.jsonl"
    write_jsonl(cache_path, cache_rows)
    all_detection_count = sum(len(row["detections"]) for row in cache_rows)
    write_json(P3 / "01_detector_cache/cache_summary.json", {
        "CACHE_SOURCE": "F2_EXISTING_DETECTOR_RUN",
        "YOLO_RERUN": False,
        "sample_count": len(cache_rows),
        "sample_detection_rate": sum(bool(row["detections"]) for row in cache_rows) / len(cache_rows),
        "detection_count": all_detection_count,
        "classes": sorted({det["class_name"] for row in cache_rows for det in row["detections"]}),
        "source_config_sha256": sha256_file(F2_CONFIG),
        "source_predictions_sha256": sha256_file(F2_PREDICTIONS),
        "output_sha256": sha256_file(cache_path),
    })

    debug_rows = [by_media[media_id] for media_id in DEBUG_MEDIA_IDS]
    if len(debug_rows) != 10 or any(row["evaluation_scope"] == "primary_binary" for row in debug_rows):
        raise SystemExit("debug set must be exactly ten non-primary rows")
    freeze_manifest(P3 / "02_geometry_debug/debug_manifest.csv", debug_rows)
    write_jsonl(
        P3 / "02_geometry_debug/geometry_input.jsonl",
        [geometry_input(row, detections[row["media_id"]]) for row in debug_rows],
    )
    make_debug_contact_sheet(
        debug_rows, detections, P3 / "02_geometry_debug/debug_bbox_contact_sheet.jpg"
    )

    pilot_rows: list[dict[str, str]] = []
    pilot_extra: dict[str, dict[str, str]] = {}
    for group, count, expected_gt, stratum in PILOT_PLAN:
        candidates = [
            row for row in manifest_rows
            if row["group_key"] == group
            and row["evaluation_scope"] == "primary_binary"
            and row["v1_2_gt"] == expected_gt
        ]
        selected = evenly_spaced(candidates, count)
        pilot_rows.extend(selected)
        for row in selected:
            pilot_extra[row["media_id"]] = {
                "pilot_stratum": stratum,
                "selection_rule": "source_id_sorted_evenly_spaced_half_up_endpoints",
            }
    if len(pilot_rows) != 60 or len({row["media_id"] for row in pilot_rows}) != 60:
        raise SystemExit("pilot must contain exactly 60 unique rows")
    if Counter(row["v1_2_gt"] for row in pilot_rows) != Counter({"positive": 40, "negative": 20}):
        raise SystemExit("pilot GT composition mismatch")
    freeze_manifest(P3 / "03_pilot/pilot_manifest.csv", pilot_rows, pilot_extra)
    pilot_cache = [next(item for item in cache_rows if item["media_id"] == row["media_id"]) for row in pilot_rows]
    write_jsonl(P3 / "03_pilot/vehicle_detections.jsonl", pilot_cache)
    write_jsonl(
        P3 / "03_pilot/geometry_input.jsonl",
        [geometry_input(row, detections[row["media_id"]]) for row in pilot_rows],
    )

    write_json(P3 / "00_design/input_freeze.json", {
        "stage": "P3L_A_GEOMETRY_ONLY",
        "allowed_split": "train_DEV_only",
        "debug_count": len(debug_rows),
        "debug_primary_binary_count": sum(row["evaluation_scope"] == "primary_binary" for row in debug_rows),
        "pilot_count": len(pilot_rows),
        "pilot_gt_counts": dict(sorted(Counter(row["v1_2_gt"] for row in pilot_rows).items())),
        "pilot_group_counts": dict(sorted(Counter(row["group_key"] for row in pilot_rows).items())),
        "definition_sha256": sha256_file(DEFINITION),
        "prompt_sha256": sha256_file(PROMPT),
        "dev_manifest_sha256": sha256_file(MANIFEST),
        "f2_config_sha256": sha256_file(F2_CONFIG),
        "f2_predictions_sha256": sha256_file(F2_PREDICTIONS),
        "yolo_checkpoint_sha256": sha256_file(YOLO_CHECKPOINT),
        "cache_source": "F2_EXISTING_DETECTOR_RUN",
        "yolo_rerun": False,
        "debug_manifest_sha256": sha256_file(P3 / "02_geometry_debug/debug_manifest.csv"),
        "pilot_manifest_sha256": sha256_file(P3 / "03_pilot/pilot_manifest.csv"),
        "val_consumed": False,
        "holdout_consumed": False,
    })

    print(json.dumps({
        "status": "prepared",
        "debug_count": len(debug_rows),
        "pilot_count": len(pilot_rows),
        "pilot_groups": dict(sorted(Counter(row["group_key"] for row in pilot_rows).items())),
        "vehicle_cache_count": len(cache_rows),
        "vehicle_detection_count": all_detection_count,
        "YOLO_RERUN": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
