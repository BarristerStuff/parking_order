#!/usr/bin/env python3
"""Combine the DEV shadow and p02 boundary manifests for each frozen candidate."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--shadow-manifest", type=Path, required=True)
    parser.add_argument("--boundary-manifest", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--experiments-dir", type=Path, required=True)
    args = parser.parse_args()

    source = read_csv(args.source_manifest)
    shadow = read_csv(args.shadow_manifest)
    boundary = read_csv(args.boundary_manifest)
    if len(source) != 239 or any(r["split"] != "train" for r in source):
        raise SystemExit("source manifest is not the frozen 239-row DEV split")
    by_media = {r["media_id"]: r for r in shadow + boundary}
    if len(by_media) != 239 or set(by_media) != {r["media_id"] for r in source}:
        raise SystemExit("shadow/boundary binding does not exactly cover frozen DEV")
    combined = [by_media[r["media_id"]] for r in source]
    scopes = Counter(r["evaluation_scope"] for r in combined)
    if scopes != Counter({"primary_binary": 179, "boundary_challenge": 35, "gt_uncertain": 25}):
        raise SystemExit(f"unexpected evaluation scopes: {dict(scopes)}")

    for candidate in ("F0", "F1", "F2"):
        output_dir = args.experiments_dir / candidate
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(combined[0]))
            writer.writeheader()
            writer.writerows(combined)
        shutil.copyfile(args.prompt, output_dir / "prompt.txt")
    print(json.dumps({"status": "ok", "candidate_count": 3, "manifest_count": 239, "scope_counts": dict(scopes)}, sort_keys=True))


if __name__ == "__main__":
    main()
