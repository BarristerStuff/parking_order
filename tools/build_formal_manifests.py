#!/usr/bin/env python3
"""Build strict media mapping, label, split, and DEV-only P0 manifests."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

LABEL_HEADER = [
    "media_id", "event_name", "event_label", "sample_role",
    "evidence_description", "reviewer", "review_status",
    "event_definition_version",
]
SPLIT_HEADER = ["media_id", "split", "group_id", "notes"]
MAPPING_HEADER = [
    "source_id", "media_id", "original_filename", "relative_path", "sha256",
    "group_key", "group_id", "sample_role", "event_label", "split",
]
DEV_HEADER = [
    "source_id", "media_id", "relative_path", "sha256", "group_key",
    "group_id", "sample_role", "event_label", "split",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--capture-batch", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    inventory = read_csv(args.inventory)
    if len(inventory) != 397:
        raise SystemExit(f"inventory must contain 397 rows, found {len(inventory)}")
    if Counter(row["split"] for row in inventory) != Counter(
        {"train": 239, "validation": 80, "holdout": 78}
    ):
        raise SystemExit("inventory split counts differ from frozen 239/80/78")

    media_rows = read_csv(dataset / "01_annotations" / "media.csv")
    selected = [row for row in media_rows if row["capture_batch"] == args.capture_batch]
    if len(selected) != 397:
        raise SystemExit(f"capture batch must contain 397 media rows, found {len(selected)}")
    by_filename = {row["original_filename"]: row for row in selected}
    if len(by_filename) != 397:
        raise SystemExit("capture batch original_filename values are not unique")

    mappings: list[dict[str, str]] = []
    labels: list[dict[str, str]] = []
    splits: list[dict[str, str]] = []
    dev_rows: list[dict[str, str]] = []
    for source in sorted(inventory, key=lambda row: int(row["source_id"])):
        original_filename = Path(source["image_path"]).name
        media = by_filename.get(original_filename)
        if media is None:
            raise SystemExit(f"no formal media row for {original_filename}")
        if media["sha256"] != source["sha256"]:
            raise SystemExit(f"SHA-256 mismatch for {original_filename}")
        expected_group_id = "POV_PARKING_B1_" + source["group_key"].upper().replace("-", "_")
        if media["scenario_id"] != expected_group_id:
            raise SystemExit(
                f"scenario mismatch for {original_filename}: "
                f"{media['scenario_id']} != {expected_group_id}"
            )
        mapping = {
            "source_id": source["source_id"],
            "media_id": media["media_id"],
            "original_filename": original_filename,
            "relative_path": media["relative_path"],
            "sha256": media["sha256"],
            "group_key": source["group_key"],
            "group_id": expected_group_id,
            "sample_role": source["role"],
            "event_label": source["event_label"],
            "split": source["split"],
        }
        mappings.append(mapping)
        provenance = (
            "GT_BASIS=generation_intent; GT_REVIEW_STATUS=unreviewed; "
            f"source_slot={source['source_id']}; intended_group={source['group_key']}; "
            "synthetic prompt-derived intent label, not human visual gold and not a model prediction."
        )
        labels.append({
            "media_id": media["media_id"],
            "event_name": "parking_order_violation",
            "event_label": source["event_label"],
            "sample_role": source["role"],
            "evidence_description": provenance,
            "reviewer": "",
            "review_status": "unreviewed",
            "event_definition_version": "v1.1",
        })
        splits.append({
            "media_id": media["media_id"],
            "split": source["split"],
            "group_id": expected_group_id,
            "notes": (
                "parking_order_violation v1.1 group-level frozen split; "
                "train=DEV, validation=VAL, holdout=HOLDOUT; GT_BASIS=generation_intent"
            ),
        })
        if source["split"] == "train":
            dev_rows.append({key: mapping[key] for key in DEV_HEADER})

    if len({row["media_id"] for row in mappings}) != 397:
        raise SystemExit("media mapping is not one-to-one")
    if len(dev_rows) != 239 or any(row["split"] != "train" for row in dev_rows):
        raise SystemExit("DEV manifest must contain exactly 239 train rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "formal_media_mapping.csv", MAPPING_HEADER, mappings)
    write_csv(args.output_dir / "parking_labels_manifest.csv", LABEL_HEADER, labels)
    write_csv(args.output_dir / "parking_splits_manifest.csv", SPLIT_HEADER, splits)
    write_csv(args.output_dir / "p0_dev_manifest.csv", DEV_HEADER, dev_rows)
    summary = {
        "capture_batch": args.capture_batch,
        "mapping_count": len(mappings),
        "label_count": len(labels),
        "split_count": len(splits),
        "dev_count": len(dev_rows),
        "split_counts": dict(Counter(row["split"] for row in mappings)),
        "role_counts": dict(Counter(row["sample_role"] for row in mappings)),
        "gt_basis": "generation_intent",
        "gt_review_status": "unreviewed",
        "val_consumed": False,
        "holdout_consumed": False,
    }
    summary_bytes = (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    (args.output_dir / "manifest_build_summary.json").write_bytes(summary_bytes)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
