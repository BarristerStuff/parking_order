#!/usr/bin/env python3
"""Atomically append frozen splits, validate, and cryptographically seal HOLDOUT."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SPLIT_HEADER = ["media_id", "split", "group_id", "notes"]
HOLDOUT_HEADER = [
    "source_id", "media_id", "split", "group_key", "group_id", "event_name",
    "event_label", "sample_role", "event_definition_version", "review_status",
    "relative_path", "sha256",
]
CAPTURE_BATCH = "20260902_ai_generated_parking_order_violation_pov_b1_397"
EVENT = "parking_order_violation"
VERSION = "v1.1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            tmp = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        target_mode = (path.stat().st_mode & 0o777) if path.exists() else 0o644
        os.chmod(tmp, target_mode)
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validator(dataset: Path):
    path = dataset / "tools" / "validate_dataset.py"
    spec = importlib.util.spec_from_file_location("parking_dataset_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_inputs(dataset: Path, split_manifest: Path, mapping_path: Path):
    annotation = dataset / "01_annotations"
    planned = read_csv(split_manifest)
    mappings = read_csv(mapping_path)
    media = read_csv(annotation / "media.csv")
    labels = read_csv(annotation / "labels.csv")
    existing_splits = read_csv(annotation / "splits.csv")

    if len(planned) != 397 or list(planned[0]) != SPLIT_HEADER:
        raise SystemExit("split manifest must have exact header and 397 rows")
    if Counter(row["split"] for row in planned) != Counter(
        {"train": 239, "validation": 80, "holdout": 78}
    ):
        raise SystemExit("split manifest must preserve frozen 239/80/78 counts")
    planned_ids = [row["media_id"] for row in planned]
    if len(set(planned_ids)) != 397:
        raise SystemExit("split manifest contains duplicate media_id")

    batch_media = {row["media_id"]: row for row in media if row["capture_batch"] == CAPTURE_BATCH}
    if set(batch_media) != set(planned_ids):
        raise SystemExit("planned media IDs do not exactly match the 397-row formal capture batch")
    mapping_by_id = {row["media_id"]: row for row in mappings}
    if set(mapping_by_id) != set(planned_ids):
        raise SystemExit("formal media mapping does not exactly match split manifest")
    label_by_id = {
        row["media_id"]: row for row in labels
        if row["event_name"] == EVENT and row["media_id"] in batch_media
    }
    if set(label_by_id) != set(planned_ids):
        raise SystemExit("all 397 formal media rows must have parking labels before split append")
    for media_id, label in label_by_id.items():
        mapping = mapping_by_id[media_id]
        if label["event_label"] != mapping["event_label"]:
            raise SystemExit(f"label mismatch for {media_id}")
        if label["sample_role"] != mapping["sample_role"]:
            raise SystemExit(f"role mismatch for {media_id}")
        if label["event_definition_version"] != VERSION or label["review_status"] != "unreviewed":
            raise SystemExit(f"version/review mismatch for {media_id}")

    existing_by_id = {row["media_id"]: row for row in existing_splits}
    overlap = set(existing_by_id) & set(planned_ids)
    if overlap:
        identical = all(existing_by_id[mid] == next(row for row in planned if row["media_id"] == mid) for mid in overlap)
        if len(overlap) == 397 and identical:
            state = "already_exists"
        else:
            raise SystemExit(f"split rows already exist or conflict for {len(overlap)} planned media IDs")
    else:
        state = "new"

    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in existing_splits:
        if row["group_id"]:
            group_splits[row["group_id"]].add(row["split"])
    for row in planned:
        group_splits[row["group_id"]].add(row["split"])
        if row["group_id"] != batch_media[row["media_id"]]["scenario_id"]:
            raise SystemExit(f"group_id/scenario_id mismatch for {row['media_id']}")
    leaking = {group: values for group, values in group_splits.items() if len(values) > 1}
    if leaking:
        raise SystemExit(f"group leakage detected: {leaking}")
    return planned, mappings, batch_media, label_by_id, existing_splits, state


def write_seal(
    dataset: Path,
    seal_dir: Path,
    mappings: list[dict[str, str]],
    batch_media: dict[str, dict[str, str]],
    label_by_id: dict[str, dict[str, str]],
) -> dict[str, object]:
    seal_dir.mkdir(parents=True, exist_ok=True)
    mapping_by_id = {row["media_id"]: row for row in mappings}
    holdout = []
    for mapping in sorted(
        (row for row in mappings if row["split"] == "holdout"),
        key=lambda row: int(row["source_id"]),
    ):
        media = batch_media[mapping["media_id"]]
        label = label_by_id[mapping["media_id"]]
        media_path = dataset / media["relative_path"]
        actual = sha256_file(media_path)
        if actual != media["sha256"] or actual != mapping["sha256"]:
            raise SystemExit(f"HOLDOUT media hash mismatch: {mapping['media_id']}")
        holdout.append({
            "source_id": mapping["source_id"],
            "media_id": mapping["media_id"],
            "split": mapping["split"],
            "group_key": mapping["group_key"],
            "group_id": mapping["group_id"],
            "event_name": EVENT,
            "event_label": label["event_label"],
            "sample_role": label["sample_role"],
            "event_definition_version": label["event_definition_version"],
            "review_status": label["review_status"],
            "relative_path": media["relative_path"],
            "sha256": media["sha256"],
        })
    if len(holdout) != 78 or any(row["split"] != "holdout" for row in holdout):
        raise SystemExit("HOLDOUT seal must contain exactly 78 holdout rows")

    manifest_path = seal_dir / "holdout_manifest.csv"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    atomic_write_csv(manifest_path, HOLDOUT_HEADER, holdout)
    manifest_hash = sha256_file(manifest_path)
    group_counts = Counter(row["group_key"] for row in holdout)
    label_counts = Counter(row["event_label"] for row in holdout)
    role_counts = Counter(row["sample_role"] for row in holdout)
    seal = {
        "seal_id": "parking_order_violation_v1.1_pov_b1_20260903",
        "sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "event_name": EVENT,
        "event_definition_version": VERSION,
        "capture_batch": CAPTURE_BATCH,
        "gt_basis": "generation_intent",
        "gt_review_status": "unreviewed",
        "holdout_count": len(holdout),
        "holdout_manifest": str(manifest_path),
        "holdout_manifest_sha256": manifest_hash,
        "holdout_group_counts": dict(sorted(group_counts.items())),
        "holdout_label_counts": dict(sorted(label_counts.items())),
        "holdout_role_counts": dict(sorted(role_counts.items())),
        "val_consumed": False,
        "holdout_consumed": False,
        "consumption_definition": "model inference or model-driven inspection",
        "administrative_hash_verification_is_not_model_consumption": True,
        "scope_warning": "Synthetic generation-intent HOLDOUT; not human visual gold or production accuracy evidence.",
    }
    seal_path = seal_dir / "holdout_seal.json"
    if seal_path.exists():
        os.chmod(seal_path, 0o644)
    seal_bytes = (json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    seal_path.write_bytes(seal_bytes)
    with seal_path.open("rb") as handle:
        os.fsync(handle.fileno())
    os.chmod(manifest_path, 0o444)
    os.chmod(seal_path, 0o444)
    return seal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--seal-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    planned, mappings, batch_media, labels, existing, state = validate_inputs(
        dataset, args.split_manifest, args.mapping
    )
    summary = {
        "status": "dry_run" if args.dry_run else state,
        "planned_count": len(planned),
        "existing_identical_count": 397 if state == "already_exists" else 0,
        "split_counts": dict(Counter(row["split"] for row in planned)),
        "holdout_would_be_sealed": 78,
        "val_consumed": False,
        "holdout_consumed": False,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return

    annotation = dataset / "01_annotations"
    lock_path = annotation / ".dataset.lock"
    splits_path = annotation / "splits.csv"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        planned, mappings, batch_media, labels, existing, state = validate_inputs(
            dataset, args.split_manifest, args.mapping
        )
        backup_dir = None
        if state == "new":
            stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = annotation / "backups" / f"{stamp}_parking_splits"
            backup_dir.mkdir(parents=True, exist_ok=False)
            shutil.copy2(splits_path, backup_dir / "splits.csv")
            try:
                atomic_write_csv(splits_path, SPLIT_HEADER, existing + planned)
                validator = load_validator(dataset)
                report = validator.validate(dataset, full_hash_check=True)
                if report.errors:
                    raise RuntimeError("; ".join(report.errors))
            except Exception:
                shutil.copy2(backup_dir / "splits.csv", splits_path)
                raise
        else:
            validator = load_validator(dataset)
            report = validator.validate(dataset, full_hash_check=True)
            if report.errors:
                raise SystemExit("dataset is invalid before seal: " + "; ".join(report.errors))

    seal = write_seal(dataset, args.seal_dir, mappings, batch_media, labels)
    summary.update({
        "status": "completed" if state == "new" else "already_exists",
        "backup_dir": str(backup_dir) if backup_dir else None,
        "validation": report.summary(),
        "holdout_manifest_sha256": seal["holdout_manifest_sha256"],
    })
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
