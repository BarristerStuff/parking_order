#!/usr/bin/env python3
"""Build DEV-only v1.2 shadow manifests from the frozen v1.1 P0 DEV manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

POSITIVE_GROUPS = {"p01-outside-legal-bay-clear", "p05-multi-vehicle-at-least-one-violation"}
BOUNDARY_GROUPS = {"p02-cross-single-boundary-line"}
NEGATIVE_GROUPS = {
    "n01-standard-inside-bay", "n02-close-to-line-but-inside", "n04-parallel-bay-correct",
    "hn01-gate-queue", "hn04-large-vehicle-compliant", "hn06-shadows-cracks-curbs-mimic-lines",
}
UNCERTAIN_GROUPS = {
    "u01-insufficient-parking-visual-evidence", "u04-night-or-blur-boundary-unreadable",
    "u05-gate-queue-or-parking-ambiguous",
}
EXPECTED_COUNTS = {
    "p01-outside-legal-bay-clear": 39, "p02-cross-single-boundary-line": 35,
    "p05-multi-vehicle-at-least-one-violation": 20, "n01-standard-inside-bay": 30,
    "n02-close-to-line-but-inside": 25, "n04-parallel-bay-correct": 15,
    "hn01-gate-queue": 30, "hn04-large-vehicle-compliant": 10,
    "hn06-shadows-cracks-curbs-mimic-lines": 10, "u01-insufficient-parking-visual-evidence": 15,
    "u04-night-or-blur-boundary-unreadable": 5, "u05-gate-queue-or-parking-ambiguous": 5,
}
FIELDNAMES = [
    "source_id", "media_id", "relative_path", "sha256", "group_key", "group_id",
    "sample_role", "original_event_label", "split", "v1_2_gt", "evaluation_scope",
    "mapping_basis", "gt_basis", "gt_review_status",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--definition", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    args = parser.parse_args()

    with args.source_manifest.open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 239 or len({r["media_id"] for r in source_rows}) != 239:
        raise SystemExit("frozen DEV manifest must contain 239 unique media_id rows")
    if any(r.get("split") != "train" for r in source_rows):
        raise SystemExit("DEV-only guard rejected a non-train row")
    actual_counts = Counter(r["group_key"] for r in source_rows)
    if dict(actual_counts) != EXPECTED_COUNTS:
        raise SystemExit(f"unexpected frozen DEV group counts: {dict(actual_counts)}")

    dev_rows: list[dict[str, str]] = []
    boundary_rows: list[dict[str, str]] = []
    for source in source_rows:
        group = source["group_key"]
        if group in POSITIVE_GROUPS:
            gt, scope, basis = "positive", "primary_binary", "v1.2 positive-core subgroup mapping"
        elif group in NEGATIVE_GROUPS:
            gt, scope, basis = "negative", "primary_binary", "v1.2 negative-core subgroup mapping"
        elif group in UNCERTAIN_GROUPS:
            gt, scope, basis = "uncertain", "gt_uncertain", "v1.2 uncertain subgroup retained"
        elif group in BOUNDARY_GROUPS:
            gt, scope, basis = "boundary_unresolved", "boundary_challenge", "p02 requires per-image Human Gold"
        else:
            raise SystemExit(f"unmapped DEV group: {group}")
        row = {
            "source_id": source["source_id"], "media_id": source["media_id"],
            "relative_path": source["relative_path"], "sha256": source["sha256"].lower(),
            "group_key": group, "group_id": source["group_id"], "sample_role": source["sample_role"],
            "original_event_label": source["event_label"], "split": source["split"],
            "v1_2_gt": gt, "evaluation_scope": scope, "mapping_basis": basis,
            "gt_basis": "generation_intent_shadow", "gt_review_status": "unreviewed",
        }
        (boundary_rows if scope == "boundary_challenge" else dev_rows).append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    dev_path = args.output_dir / "v1_2_dev_manifest.csv"
    boundary_path = args.output_dir / "boundary_challenge_manifest.csv"
    write_csv(dev_path, dev_rows)
    write_csv(boundary_path, boundary_rows)

    definition_hash = sha256_file(args.definition)
    prompt_hash = sha256_file(args.prompt)
    args.definition.with_suffix(".sha256").write_text(
        f"{definition_hash}  {args.definition.name}\n", encoding="utf-8"
    )
    args.prompt.with_suffix(".sha256").write_text(f"{prompt_hash}  {args.prompt.name}\n", encoding="utf-8")
    root = args.output_dir.parent
    for candidate in ("F0", "F1", "F2"):
        candidate_dir = root / "02_experiments" / candidate
        candidate_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.prompt, candidate_dir / "prompt.txt")

    dev_counts = Counter(r["evaluation_scope"] for r in dev_rows)
    gt_counts = Counter(r["v1_2_gt"] for r in dev_rows)
    report = f"""# parking_order_violation v1.2 shadow GT mapping

## Confirmed facts

- Source: frozen v1.1 P0 DEV manifest only.
- Split guard: 239/239 rows are `train` (DEV).
- Unique media binding: 239/239.
- V1.2 DEV manifest: {len(dev_rows)} rows.
- Primary binary: {dev_counts['primary_binary']} rows ({gt_counts['positive']} positive, {gt_counts['negative']} negative).
- GT uncertain: {gt_counts['uncertain']} rows, excluded from binary confusion matrix.
- Boundary challenge: {len(boundary_rows)} p02 rows, excluded from primary metrics.
- VAL_CONSUMED=false.
- HOLDOUT_CONSUMED=false.

## Mapping rule

- Positive core: p01 and p05 -> `positive`.
- Negative core: original DEV negative/hard-negative groups -> `negative`.
- Original uncertain groups -> `uncertain`.
- p02 -> `boundary_unresolved`.

## Evidence limitation and risk

This is an auditable generation-intent shadow GT, not per-image Human Gold. Subgroup names and their DEV generation prompts are semantically consistent with v1.2, but individual generated pixels have not been visually adjudicated. Metrics from this manifest are proxy development evidence and must not be presented as production accuracy. In particular, p02 is not mechanically relabeled.

## Frozen references

- Source manifest SHA-256: `{sha256_file(args.source_manifest)}`
- Definition SHA-256: `{definition_hash}`
- Prompt SHA-256: `{prompt_hash}`
- V1.2 DEV manifest SHA-256: `{sha256_file(dev_path)}`
- Boundary manifest SHA-256: `{sha256_file(boundary_path)}`
"""
    (args.output_dir / "v1_2_mapping_report.md").write_text(report, encoding="utf-8")
    summary = {
        "status": "prepared", "source_manifest_count": len(source_rows),
        "dev_manifest_count": len(dev_rows), "boundary_manifest_count": len(boundary_rows),
        "primary_binary_count": dev_counts["primary_binary"], "gt_counts": dict(sorted(gt_counts.items())),
        "group_counts": dict(sorted(actual_counts.items())), "source_manifest_sha256": sha256_file(args.source_manifest),
        "definition_sha256": definition_hash, "prompt_sha256": prompt_hash,
        "dev_manifest_sha256": sha256_file(dev_path), "boundary_manifest_sha256": sha256_file(boundary_path),
        "gt_basis": "generation_intent_shadow", "gt_review_status": "unreviewed",
        "val_consumed": False, "holdout_consumed": False,
    }
    (args.output_dir / "mapping_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
