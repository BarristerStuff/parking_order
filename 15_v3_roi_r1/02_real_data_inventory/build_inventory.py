from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


TODAY = "2026-09-09"
ROOT = Path("/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1")
DATASET = Path("/home/yanbo/net_vlm_xunjian_dataset")
PRODUCTION_VLM = Path("/home/yanbo/net_vlm_yanboversion/vlm")
V2_SPLIT = Path("/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/v2_split.csv")

SOURCE_FIELDS = [
    "path",
    "source_type",
    "is_parking_related",
    "is_real_camera",
    "camera_id",
    "route_id",
    "width",
    "height",
    "sha256",
    "provenance",
    "allowed_for_r1",
    "reason",
]

CAMERA_FIELDS = [
    "camera_id",
    "route_id",
    "source_path",
    "source_type",
    "parking_related_count",
    "real_camera_count",
    "image_size_set",
    "homography_available",
    "parking_bay_polygon_available",
    "road_polygon_available",
    "gate_queue_polygon_available",
    "status",
    "evidence",
]


def main() -> None:
    ROOT.joinpath("02_real_data_inventory").mkdir(parents=True, exist_ok=True)
    media_rows = read_csv(DATASET / "01_annotations/media.csv")
    split_by_media = {row["media_id"]: row["split"] for row in read_csv(V2_SPLIT)}
    source_rows = []
    source_rows.extend(raw_source_directory_rows())
    source_rows.extend(parking_annotation_rows(media_rows, split_by_media))
    source_rows.extend(project_test_media_rows())
    write_csv(ROOT / "02_real_data_inventory/source_inventory.csv", SOURCE_FIELDS, source_rows)
    camera_rows = camera_route_rows(source_rows)
    write_csv(ROOT / "02_real_data_inventory/camera_route_inventory.csv", CAMERA_FIELDS, camera_rows)
    status = real_data_status(source_rows, camera_rows)
    (ROOT / "02_real_data_inventory/real_data_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (ROOT / "02_real_data_inventory/README.md").write_text(readme(status, source_rows))
    if not status["REAL_CAMERA_DATA_AVAILABLE"]:
        (ROOT / "03_real_roi_pilot/BLOCKED_MISSING_REAL_CAMERA_DATA.md").write_text(blocked_real_camera_data(status))
        (ROOT / "03_real_roi_pilot/BLOCKED_MISSING_REAL_ROI.md").write_text(blocked_real_roi(status))
        write_empty_pilot_files()


def raw_source_directory_rows() -> list[dict[str, str]]:
    rows = []
    for source_type in ["robot_direct", "phone_camera", "public_dataset", "ai_generated"]:
        source_root = DATASET / "00_raw" / source_type
        file_count = sum(1 for path in source_root.rglob("*") if path.is_file()) if source_root.exists() else 0
        parking_hint_count = sum(1 for path in source_root.rglob("*") if path.is_file() and "parking" in str(path).lower()) if source_root.exists() else 0
        rows.append(
            {
                "path": str(source_root),
                "source_type": source_type,
                "is_parking_related": str(parking_hint_count > 0).lower(),
                "is_real_camera": str(source_type in {"robot_direct", "phone_camera"}).lower(),
                "camera_id": "",
                "route_id": "",
                "width": "",
                "height": "",
                "sha256": "",
                "provenance": f"directory_inventory:file_count={file_count};parking_name_hint_count={parking_hint_count}",
                "allowed_for_r1": "false",
                "reason": "Directory-level inventory only; not a fixed parking camera ROI input.",
            }
        )
    return rows


def parking_annotation_rows(media_rows: list[dict[str, str]], split_by_media: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for row in media_rows:
        is_parking = row.get("capture_batch") == "20260902_ai_generated_parking_order_violation_pov_b1_397" or row.get("scenario_id", "").startswith("POV_PARKING_B1_") or "parking_order_violation" in json.dumps(row, ensure_ascii=False).lower()
        if not is_parking:
            continue
        v2_split = split_by_media.get(row.get("media_id", ""), "NOT_V2_SPLIT")
        allowed = row.get("source_type") in {"robot_direct", "phone_camera"} and bool(row.get("camera_id")) and bool(row.get("route_id"))
        if row.get("source_type") == "ai_generated":
            allowed_for_r1 = "AIGC_FIXTURE_ONLY" if v2_split == "DEV" else "false"
            reason = f"Parking media is AIGC; v2_split={v2_split}; no real fixed camera/route/ROI evidence. VAL/HOLDOUT media not opened."
        elif allowed:
            allowed_for_r1 = "true"
            reason = "Real camera row with route metadata."
        else:
            allowed_for_r1 = "false"
            reason = "Parking-related row lacks confirmed real fixed camera/route metadata."
        rows.append(
            {
                "path": str(DATASET / row.get("relative_path", "")),
                "source_type": row.get("source_type", ""),
                "is_parking_related": "true",
                "is_real_camera": str(row.get("source_type") in {"robot_direct", "phone_camera"}).lower(),
                "camera_id": row.get("camera_id", ""),
                "route_id": row.get("route_id", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "sha256": row.get("sha256", ""),
                "provenance": f"media.csv:media_id={row.get('media_id','')};capture_batch={row.get('capture_batch','')};scenario_id={row.get('scenario_id','')};v2_split={v2_split}",
                "allowed_for_r1": allowed_for_r1,
                "reason": reason,
            }
        )
    return rows


def project_test_media_rows() -> list[dict[str, str]]:
    rows = []
    media_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".avi", ".mov", ".mkv"}
    if not PRODUCTION_VLM.exists():
        return rows
    for path in sorted(PRODUCTION_VLM.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in media_suffixes:
            continue
        if len(rows) >= 100:
            break
        lower_path = str(path).lower()
        is_parking = "parking" in lower_path or "park" in lower_path or "停车" in lower_path
        rows.append(
            {
                "path": str(path),
                "source_type": "project_test_media_unknown",
                "is_parking_related": str(is_parking).lower(),
                "is_real_camera": "false",
                "camera_id": "",
                "route_id": "",
                "width": "",
                "height": "",
                "sha256": sha256_file(path),
                "provenance": "production_vlm_test_media_path_scan; not treated as robot_direct evidence",
                "allowed_for_r1": "false",
                "reason": "Project media file without parking event annotation, camera_id, route_id, or ROI calibration.",
            }
        )
    return rows


def camera_route_rows(source_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        if row["camera_id"] or row["route_id"]:
            grouped[(row["camera_id"], row["route_id"])].append(row)
    if not grouped:
        return [
            {
                "camera_id": "",
                "route_id": "",
                "source_path": "",
                "source_type": "",
                "parking_related_count": "0",
                "real_camera_count": "0",
                "image_size_set": "",
                "homography_available": "false",
                "parking_bay_polygon_available": "false",
                "road_polygon_available": "false",
                "gate_queue_polygon_available": "false",
                "status": "BLOCKED_NO_CAMERA_ROUTE_METADATA",
                "evidence": "No source_inventory row contained camera_id or route_id.",
            }
        ]
    rows = []
    for (camera_id, route_id), items in sorted(grouped.items()):
        rows.append(
            {
                "camera_id": camera_id,
                "route_id": route_id,
                "source_path": items[0]["path"],
                "source_type": ";".join(sorted({item["source_type"] for item in items})),
                "parking_related_count": str(sum(item["is_parking_related"] == "true" for item in items)),
                "real_camera_count": str(sum(item["is_real_camera"] == "true" for item in items)),
                "image_size_set": ";".join(sorted({f"{item['width']}x{item['height']}" for item in items if item["width"] and item["height"]})),
                "homography_available": "false",
                "parking_bay_polygon_available": "false",
                "road_polygon_available": "false",
                "gate_queue_polygon_available": "false",
                "status": "BLOCKED_MISSING_ROI_CALIBRATION",
                "evidence": "Camera/route row exists but no ROI calibration fields were found by this inventory.",
            }
        )
    return rows


def real_data_status(source_rows: list[dict[str, str]], camera_rows: list[dict[str, str]]) -> dict:
    parking_real_rows = [row for row in source_rows if row["is_parking_related"] == "true" and row["is_real_camera"] == "true"]
    fixed_camera_candidates = [row for row in parking_real_rows if row["camera_id"] or row["route_id"]]
    real_roi_ready = [row for row in camera_rows if row["homography_available"] == "true" and row["parking_bay_polygon_available"] == "true" and row["road_polygon_available"] == "true"]
    source_counts = Counter(row["source_type"] for row in source_rows)
    return {
        "execution_date": TODAY,
        "source_inventory_rows": len(source_rows),
        "source_type_counts": dict(source_counts),
        "parking_real_camera_rows": len(parking_real_rows),
        "fixed_camera_route_candidates": len(fixed_camera_candidates),
        "camera_route_inventory_rows": len(camera_rows),
        "REAL_CAMERA_DATA_AVAILABLE": bool(parking_real_rows),
        "REAL_FIXED_CAMERA_ROUTE_AVAILABLE": bool(fixed_camera_candidates),
        "REAL_ROI_CALIBRATION_AVAILABLE": bool(real_roi_ready),
        "R1_REAL_E2E_EVALUATION_BLOCKED": not (parking_real_rows and fixed_camera_candidates and real_roi_ready),
        "old_v2_val_holdout_media_opened": False,
        "model_api_used": False,
        "notes": [
            "Parking annotation rows found in media.csv are AIGC for the current parking batch.",
            "robot_direct and phone_camera directories were inventoried, but no parking-related real camera row was confirmed.",
            "Project test media paths are not accepted as parking robot_direct evidence without annotation, camera_id, route_id, and ROI calibration.",
        ],
    }


def write_empty_pilot_files() -> None:
    write_csv(ROOT / "03_real_roi_pilot/calibration_manifest.csv", ["camera_id", "route_id", "status", "reason"], [])
    (ROOT / "03_real_roi_pilot/calibration_notes.md").write_text("# Calibration Notes\n\nNo real fixed-camera parking data or ROI calibration was available.\n")
    write_csv(ROOT / "03_real_roi_pilot/pilot_labels.csv", ["media_id", "vehicle_id", "label", "review_status", "reason"], [])
    (ROOT / "03_real_roi_pilot/pilot_report.md").write_text("# Pilot Report\n\nR1 real ROI pilot was blocked by missing real camera data and missing real ROI calibration.\n")


def readme(status: dict, source_rows: list[dict[str, str]]) -> str:
    return f"""# Real Data Inventory

Execution date: {TODAY}

## Status

- REAL_CAMERA_DATA_AVAILABLE={str(status['REAL_CAMERA_DATA_AVAILABLE']).lower()}
- REAL_FIXED_CAMERA_ROUTE_AVAILABLE={str(status['REAL_FIXED_CAMERA_ROUTE_AVAILABLE']).lower()}
- REAL_ROI_CALIBRATION_AVAILABLE={str(status['REAL_ROI_CALIBRATION_AVAILABLE']).lower()}
- R1_REAL_E2E_EVALUATION_BLOCKED={str(status['R1_REAL_E2E_EVALUATION_BLOCKED']).lower()}

## Summary

- Inventory rows: {len(source_rows)}
- Parking real-camera rows: {status['parking_real_camera_rows']}
- Fixed camera/route candidates: {status['fixed_camera_route_candidates']}
- Old v2 VAL/HOLDOUT media opened: false

No real parking camera/route ROI pilot is authorized from this inventory.
"""


def blocked_real_camera_data(status: dict) -> str:
    return f"""# BLOCKED_MISSING_REAL_CAMERA_DATA

Execution date: {TODAY}

REAL_CAMERA_DATA_AVAILABLE={str(status['REAL_CAMERA_DATA_AVAILABLE']).lower()}
REAL_FIXED_CAMERA_ROUTE_AVAILABLE={str(status['REAL_FIXED_CAMERA_ROUTE_AVAILABLE']).lower()}
R1_REAL_E2E_EVALUATION_BLOCKED={str(status['R1_REAL_E2E_EVALUATION_BLOCKED']).lower()}

No `parking_order_violation` media row with confirmed `robot_direct` or `phone_camera` source and camera/route metadata was found. AIGC parking rows remain fixture-only and are not real camera evidence.
"""


def blocked_real_roi(status: dict) -> str:
    return f"""# BLOCKED_MISSING_REAL_ROI

Execution date: {TODAY}

REAL_ROI_CALIBRATION_AVAILABLE={str(status['REAL_ROI_CALIBRATION_AVAILABLE']).lower()}

No homography, parking bay polygon, road polygon, gate queue polygon, camera_id, and route_id bundle was found for a real parking camera. No fake production ROI was created.
"""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file_handle:
        return list(csv.DictReader(file_handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
