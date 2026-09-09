#!/usr/bin/env python3
"""Freeze and validate the label-bearing and redacted inputs for the v2 DEV baseline.

This preparation tool is the only Step 2 component allowed to read v2 GT, split,
and group metadata.  It emits a separate opaque inference input later, after the
new DEV-only detector cache has been created.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
V2 = ROOT / "12_v2_not_in_bay"
TOOLS = V2 / "02_tools"
DEBUG = V2 / "03_debug"
DATASET_ROOT = Path("/home/yanbo/net_vlm_xunjian_dataset")

DEFINITION = V2 / "00_definition" / "vehicle_not_in_bay_v2.0.md"
GT = V2 / "01_gt_and_split" / "v2_0_gt.csv"
SPLIT = V2 / "01_gt_and_split" / "v2_split.csv"
P05_REVIEW = V2 / "01_gt_and_split" / "p05_visual_review.csv"
SOURCE = ROOT / "02_ingest" / "manifests" / "formal_media_mapping.csv"
AUTH = TOOLS / "stage2_authorization.md"
CONFIG = TOOLS / "v2_dev_baseline_config.json"
PROMPT = TOOLS / "prompt_v2_perception.txt"

EVAL_MANIFEST = DEBUG / "v2_dev_evaluation_manifest.csv"
DETECTOR_INPUT = DEBUG / "v2_dev_detector_input.jsonl"
BINDING = DEBUG / "v2_step2_binding.json"
PREFLIGHT = DEBUG / "v2_dev_preflight.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def atomic_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def read_csv(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != expected_fields:
            raise SystemExit(f"schema mismatch in {path.name}: {reader.fieldnames}")
        return list(reader)


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    expected = f"{sha256_file(path)}  {path.name}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"frozen SHA-256 sidecar mismatch: {path}")


def verify_image(path: Path, expected_sha256: str) -> tuple[int, int]:
    if not path.is_file():
        raise SystemExit(f"DEV image missing: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise SystemExit(f"DEV image SHA-256 mismatch: {path}")
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        return image.width, image.height


def validate_config(config: dict[str, Any]) -> None:
    expected = {
        "stage": "V2_STEP2_STRONGER_VLM_DEV_BASELINE",
        "model": "qwen3.5:4b",
        "allowed_split": "DEV",
        "val_access_allowed": False,
        "holdout_access_allowed": False,
        "prompt_optimization": False,
        "preprocessing_optimization": False,
        "f2_rerun": False,
        "val_consumed": False,
        "holdout_consumed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise SystemExit(f"baseline config guard failed: {key}")
    if int(config.get("max_workers", 0)) < 1 or int(config["max_workers"]) > 2:
        raise SystemExit("baseline config concurrency guard failed")
    detector = config.get("detector", {})
    if detector.get("method") != "new_v2_dev_only_yolo11n_cache":
        raise SystemExit("baseline detector method guard failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the initial manifest/binding after all DEV-only checks pass",
    )
    args = parser.parse_args()

    required = [DEFINITION, GT, SPLIT, P05_REVIEW, SOURCE, AUTH, CONFIG, PROMPT]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("required input missing: " + ", ".join(missing))
    for path in (DEFINITION, GT, SPLIT):
        verify_sidecar(path)

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    validate_config(config)
    source_rows = read_csv(
        SOURCE,
        [
            "source_id", "media_id", "original_filename", "relative_path", "sha256",
            "group_key", "group_id", "sample_role", "event_label", "split",
        ],
    )
    gt_rows = read_csv(GT, ["media_id", "group_key", "v2_gt", "target_bbox_hint", "scope"])
    split_rows = read_csv(
        SPLIT, ["media_id", "group_key", "split", "split_seed", "allocation_key_sha256"]
    )
    p05_rows = read_csv(
        P05_REVIEW,
        [
            "media_id", "original_filename", "v2_gt", "target_bbox_hint",
            "visual_basis", "reviewer", "review_date",
        ],
    )
    if len(source_rows) != 397 or len(gt_rows) != 397 or len(split_rows) != 397:
        raise SystemExit("Step 1 source/GT/split count is not 397")
    if len(p05_rows) != 20 or Counter(row["v2_gt"] for row in p05_rows) != Counter(
        {"positive": 17, "negative": 3}
    ):
        raise SystemExit("p05 frozen visual adjudication changed")

    source_by_media = {row["media_id"]: row for row in source_rows}
    gt_by_media = {row["media_id"]: row for row in gt_rows}
    split_by_media = {row["media_id"]: row for row in split_rows}
    if min(len(source_by_media), len(gt_by_media), len(split_by_media)) != 397:
        raise SystemExit("duplicate media ID in a Step 1 input")
    if set(source_by_media) != set(gt_by_media) or set(source_by_media) != set(split_by_media):
        raise SystemExit("Step 1 media sets do not match")
    if {row["split_seed"] for row in split_rows} != {"20260908"}:
        raise SystemExit("frozen split seed mismatch")

    dev_rows: list[dict[str, str]] = []
    group_counts = Counter()
    for media_id, source in source_by_media.items():
        gt = gt_by_media[media_id]
        split = split_by_media[media_id]
        if source["group_key"] != gt["group_key"] or source["group_key"] != split["group_key"]:
            raise SystemExit(f"group binding mismatch: {media_id}")
        if split["split"] != "DEV":
            continue
        image_path = (DATASET_ROOT / source["relative_path"]).resolve()
        if DATASET_ROOT not in image_path.parents:
            raise SystemExit(f"unsafe non-dataset path: {image_path}")
        width, height = verify_image(image_path, source["sha256"])
        if (width, height) != (1920, 1080):
            raise SystemExit(f"unexpected DEV image dimensions: {media_id}={width}x{height}")
        token = source["sha256"]
        dev_rows.append(
            {
                "media_id": media_id,
                "sample_token": token,
                "group_key": source["group_key"],
                "v2_gt": gt["v2_gt"],
                "scope": gt["scope"],
                "split": "DEV",
                "source_id": source["source_id"],
                "formal_relative_path": source["relative_path"],
                "image_path": str(image_path),
                "image_sha256": source["sha256"],
                "width": str(width),
                "height": str(height),
            }
        )
        group_counts[source["group_key"]] += 1

    dev_rows.sort(key=lambda row: int(row["source_id"]))
    if len(dev_rows) != 238 or len({row["media_id"] for row in dev_rows}) != 238:
        raise SystemExit("v2 DEV manifest must contain exactly 238 unique rows")
    if len({row["sample_token"] for row in dev_rows}) != 238:
        raise SystemExit("sample tokens must be unique image hashes")

    exempt_groups = {
        "u03-vehicle-cut-by-frame-edge",
        "u04-night-or-blur-boundary-unreadable",
        "u05-gate-queue-or-parking-ambiguous",
    }
    small_nonexempt = [
        group for group, count in group_counts.items()
        if count < 5 and group not in exempt_groups
    ]
    if small_nonexempt:
        raise SystemExit("non-exempt group DEV<5 stop: " + ", ".join(sorted(small_nonexempt)))
    for group in exempt_groups:
        if group_counts.get(group) != 3:
            raise SystemExit(f"unexpected accepted uncertain exemption count: {group}")

    fields = [
        "media_id", "sample_token", "group_key", "v2_gt", "scope", "split",
        "source_id", "formal_relative_path", "image_path", "image_sha256", "width", "height",
    ]
    binding = {
        "stage": "V2_STEP2_STRONGER_VLM_DEV_BASELINE",
        "status": "PREFLIGHT_VALID__NO_OLLAMA_CALL_YET",
        "user_authorization_record_sha256": sha256_file(AUTH),
        "definition_sha256": sha256_file(DEFINITION),
        "gt_sha256": sha256_file(GT),
        "split_sha256": sha256_file(SPLIT),
        "p05_visual_review_sha256": sha256_file(P05_REVIEW),
        "formal_media_mapping_sha256": sha256_file(SOURCE),
        "config_sha256": sha256_file(CONFIG),
        "prompt_sha256": sha256_file(PROMPT),
        "split_seed": "20260908",
        "dev_count": len(dev_rows),
        "dev_group_counts": dict(sorted(group_counts.items())),
        "gt_uncertain_dev_lt5_exemption": sorted(exempt_groups),
        "val_access_allowed": False,
        "holdout_access_allowed": False,
        "model": config["model"],
        "max_ollama_concurrency": config["max_workers"],
        "f2_rerun": False,
        "new_v2_dev_detector_run_required": True,
        "prompt_optimization": False,
        "preprocessing_optimization": False,
    }
    preflight = {
        "status": "valid",
        "error_count": 0,
        "stage": binding["stage"],
        "source_type": "AIGC",
        "gt_basis": config["gt_basis"],
        "dev_image_count": len(dev_rows),
        "dev_group_count": len(group_counts),
        "dev_group_counts": binding["dev_group_counts"],
        "image_sha256_checked": len(dev_rows),
        "image_decode_verified": len(dev_rows),
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "target_bbox_hint_present_in_inference_input": False,
        "nonexempt_dev_lt5_groups": small_nonexempt,
        "exempt_uncertain_dev_lt5_groups": sorted(exempt_groups),
        "frozen_input_hashes": {
            key: binding[key]
            for key in (
                "definition_sha256", "gt_sha256", "split_sha256",
                "p05_visual_review_sha256", "formal_media_mapping_sha256",
                "config_sha256", "prompt_sha256",
            )
        },
    }

    if args.write:
        expected_manifest = "\n".join(
            [",".join(fields)] + [
                ",".join(
                    json.dumps(row[field], ensure_ascii=False)
                    if any(mark in row[field] for mark in (",", "\"", "\n"))
                    else row[field]
                    for field in fields
                )
                for row in dev_rows
            ]
        ) + "\n"
        expected_binding = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        expected_preflight = json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for path, expected in (
            (EVAL_MANIFEST, expected_manifest),
            (BINDING, expected_binding),
            (PREFLIGHT, expected_preflight),
        ):
            if path.exists() and path.read_text(encoding="utf-8") != expected:
                raise SystemExit(f"refusing to replace differing frozen output: {path}")
        if not EVAL_MANIFEST.exists():
            atomic_csv(EVAL_MANIFEST, fields, dev_rows)
        if not BINDING.exists():
            atomic_text(BINDING, expected_binding)
        if not PREFLIGHT.exists():
            atomic_text(PREFLIGHT, expected_preflight)
        detector_rows = [
            {
                "sample_token": row["sample_token"],
                "image_path": row["image_path"],
                "image_sha256": row["image_sha256"],
            }
            for row in dev_rows
        ]
        expected_detector = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in detector_rows
        )
        if DETECTOR_INPUT.exists() and DETECTOR_INPUT.read_text(encoding="utf-8") != expected_detector:
            raise SystemExit(f"refusing to replace differing detector input: {DETECTOR_INPUT}")
        if not DETECTOR_INPUT.exists():
            atomic_jsonl(DETECTOR_INPUT, detector_rows)
        for path in (EVAL_MANIFEST, DETECTOR_INPUT):
            atomic_text(path.with_name(path.name + ".sha256"), f"{sha256_file(path)}  {path.name}\n")
        for path in (CONFIG, PROMPT):
            atomic_text(path.with_name(path.name + ".sha256"), f"{sha256_file(path)}  {path.name}\n")

    print(json.dumps(
        {
            "status": "prepared" if args.write else "check_ok",
            "dev_count": len(dev_rows),
            "group_count": len(group_counts),
            "val_image_reads": 0,
            "holdout_image_reads": 0,
            "nonexempt_dev_lt5_groups": small_nonexempt,
            "exempt_uncertain_dev_lt5_groups": sorted(exempt_groups),
            "prompt_sha256": binding["prompt_sha256"],
            "config_sha256": binding["config_sha256"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
