from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


TODAY = "2026-09-09"
REVISION_ROOT = Path("/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road")
OPT_ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
DATASET_ROOT = Path("/home/yanbo/net_vlm_xunjian_dataset")
YANBO_ROOT = Path("/home/yanbo/net_vlm_yanboversion")
PRODUCTION_VLM = YANBO_ROOT / "vlm"

INPUT_FILES = [
    YANBO_ROOT / "docs/parking_order/codex-handoff.md",
    OPT_ROOT / "README.md",
    OPT_ROOT / "12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md",
    OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/STEP1_REPORT.md",
    OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv",
    OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv",
    OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/dev_baseline_report.md",
    OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json",
    OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/single_rgb_route_closure.md",
    OPT_ROOT / "13_spatiolm_successor_gate/final_report.md",
    OPT_ROOT / "08_final_audit/final_report.md",
    OPT_ROOT / "09_v1_1_error_review/v1_1_error_review_report.md",
    OPT_ROOT / "10_v1_2_fasttrack/final_fasttrack_report.md",
    OPT_ROOT / "11_p3_lite_geometry/final_report.md",
    PRODUCTION_VLM / "script/prompts.py",
    PRODUCTION_VLM / "script/alerts.py",
    PRODUCTION_VLM / "script/tts_publisher.py",
    PRODUCTION_VLM / "w_v/realtime_worker.py",
    PRODUCTION_VLM / "w_v/yolo_gate.py",
    OPT_ROOT / "02_ingest/manifests/formal_media_mapping.csv",
    OPT_ROOT / "12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl",
]

VEHICLE_FIELDNAMES = [
    "media_id",
    "vehicle_id",
    "bbox_xyxy",
    "source_group",
    "candidate_old_v2_gt",
    "v3_label",
    "parking_context",
    "visibility",
    "evidence",
    "review_status",
    "reviewer",
    "review_date",
]

IMAGE_FIELDNAMES = [
    "media_id",
    "image_label",
    "positive_vehicle_ids",
    "negative_vehicle_ids",
    "uncertain_vehicle_ids",
    "source_type",
    "split",
    "review_status",
    "label_basis",
]

POSITIVE_LABELS = {"positive_road", "positive_two_bays"}
NEGATIVE_LABELS = {
    "negative_in_bay",
    "negative_line_touch_or_minor_overrun",
    "negative_nose_tail_overhang",
    "negative_gate_queue",
}

MANUAL_PILOT_LABELS = {
    ("IMG_007520", "v01"): ("positive_road", "driving aisle", "clear", "Pilot contact sheet: vehicle body appears in driving aisle, not in a marked bay."),
    ("IMG_007559", "v04"): (
        "negative_line_touch_or_minor_overrun",
        "single-bay boundary challenge",
        "limited",
        "Pilot contact sheet: main vehicle appears to touch/cross one bay line; no clear two-bay occupancy used for alert.",
    ),
    ("IMG_007594", "v02"): (
        "positive_two_bays",
        "two adjacent bays",
        "clear",
        "Pilot contact sheet: main vehicle footprint visibly straddles two adjacent bay spaces.",
    ),
    ("IMG_007625", "v02"): (
        "uncertain",
        "angled/road-bay ambiguous",
        "limited",
        "Pilot contact sheet: vehicle is angled near bay line, but v3 road/two-bay evidence is not reliable enough.",
    ),
    ("IMG_007667", "v01"): (
        "negative_nose_tail_overhang",
        "nose/tail overhang",
        "limited",
        "Pilot contact sheet: vehicle mostly remains in one bay with front/rear overhang context.",
    ),
    ("IMG_007400", "v02"): ("negative_in_bay", "marked parking bay", "clear", "Pilot contact sheet: central vehicle is inside a marked bay."),
    ("IMG_007433", "v01"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: main red car remains in a bay; no v3 positive evidence."),
    ("IMG_007455", "v01"): ("negative_in_bay", "diagonal parking bay", "limited", "Pilot contact sheet: vehicle is in a diagonal bay."),
    ("IMG_007470", "v01"): ("negative_in_bay", "parallel bay", "limited", "Pilot contact sheet: vehicle appears in a marked parallel bay."),
    ("IMG_007485", "v01"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: visible vehicle appears within a bay."),
    ("IMG_007485", "v02"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: visible vehicle appears within a bay."),
    ("IMG_007485", "v03"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: visible vehicle appears within a bay."),
    ("IMG_007500", "v01"): ("negative_in_bay", "special marked bay", "clear", "Pilot contact sheet: vehicle is in the marked EV charging bay."),
    ("IMG_007321", "v01"): ("negative_gate_queue", "gate queue", "clear", "Pilot contact sheet: vehicle is in a gate queue lane."),
    ("IMG_007321", "v02"): ("negative_gate_queue", "gate queue", "partial", "Pilot contact sheet: partial vehicle is in the same gate queue context."),
    ("IMG_007321", "v03"): ("negative_gate_queue", "gate queue", "partial", "Pilot contact sheet: partial vehicle is in the same gate queue context."),
    ("IMG_007350", "v01"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: visible vehicle appears in a bay despite faded lines."),
    ("IMG_007350", "v02"): ("negative_in_bay", "marked parking bay", "partial", "Pilot contact sheet: partial vehicle appears in a bay context."),
    ("IMG_007350", "v03"): ("negative_in_bay", "marked parking bay", "limited", "Pilot contact sheet: visible vehicle appears in a bay despite faded lines."),
    ("IMG_007360", "v01"): (
        "negative_line_touch_or_minor_overrun",
        "perspective line challenge",
        "limited",
        "Pilot contact sheet: perspective suggests possible line crossing, but no clear v3 two-bay occupancy.",
    ),
    ("IMG_007370", "v01"): ("negative_in_bay", "large marked bay", "clear", "Pilot contact sheet: large vehicle is in a marked compliant area."),
    ("IMG_007392", "v01"): ("negative_in_bay", "shadow/curb line challenge", "limited", "Pilot contact sheet: shadow/curb marks do not create v3 positive evidence."),
    ("IMG_007677", "v01"): ("uncertain", "insufficient parking evidence", "limited", "Pilot contact sheet: road/bay relationship is not reliable."),
    ("IMG_007692", "v01"): ("uncertain", "missing/occluded markings", "limited", "Pilot contact sheet: markings are insufficient for reliable v3 decision."),
    ("IMG_007702", "v01"): ("uncertain", "frame-edge cut vehicle", "partial", "Pilot contact sheet: target vehicle is cut by frame edge."),
    ("IMG_007707", "v08"): ("uncertain", "night/blur unreadable", "limited", "Pilot contact sheet: night/blur prevents reliable road/bay decision."),
    ("IMG_007712", "v01"): ("uncertain", "gate-or-parking ambiguous", "limited", "Pilot contact sheet: gate queue vs parking context remains ambiguous."),
}


def main() -> None:
    ensure_dirs()
    mapping_rows = read_csv(OPT_ROOT / "02_ingest/manifests/formal_media_mapping.csv")
    split_rows = read_csv(OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv")
    gt_rows = read_csv(OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv")
    mapping_by_media = {row["media_id"]: row for row in mapping_rows}
    split_by_media = {row["media_id"]: row for row in split_rows}
    gt_by_media = {row["media_id"]: row for row in gt_rows}
    dev_media_ids = {row["media_id"] for row in split_rows if row["split"] == "DEV"}
    detection_records = read_detection_records(dev_media_ids)
    pilot_media_ids = read_pilot_media_ids()

    vehicle_rows = build_vehicle_rows(detection_records, mapping_by_media, gt_by_media, pilot_media_ids)
    write_csv(REVISION_ROOT / "01_v3_gt_overlay/v3_dev_vehicle_labels.csv", VEHICLE_FIELDNAMES, vehicle_rows)
    image_rows = build_image_rows(dev_media_ids, vehicle_rows, mapping_by_media, split_by_media)
    write_csv(REVISION_ROOT / "01_v3_gt_overlay/v3_dev_image_labels.csv", IMAGE_FIELDNAMES, image_rows)

    split_counts = Counter(row["split"] for row in split_rows)
    dev_group_counts = Counter(mapping_by_media[media_id]["group_key"] for media_id in dev_media_ids)
    pilot_vehicle_count = sum(1 for row in vehicle_rows if row["review_status"] == "PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET")
    reviewed_image_count = sum(1 for row in image_rows if row["review_status"] == "PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET")
    metrics = build_metrics(image_rows, vehicle_rows, split_counts, dev_group_counts, reviewed_image_count, pilot_vehicle_count)
    write_json(REVISION_ROOT / "05_dev_eval/metrics.json", metrics)

    frozen_hashes = build_frozen_hashes()
    write_json(REVISION_ROOT / "06_audit/frozen_hashes.json", frozen_hashes)
    input_manifest = build_input_manifest(split_counts, dev_group_counts, detection_records, vehicle_rows, image_rows)
    write_json(REVISION_ROOT / "06_audit/input_manifest.json", input_manifest)
    validation_report = build_validation_report(input_manifest, frozen_hashes)
    write_json(REVISION_ROOT / "06_audit/validation_report.json", validation_report)
    write_text_reports(input_manifest, metrics, validation_report)


def ensure_dirs() -> None:
    for relative_dir in [
        "00_definition",
        "01_v3_gt_overlay",
        "02_roi_config",
        "03_detector_adapter",
        "04_roi_rule",
        "05_dev_eval",
        "06_audit",
    ]:
        (REVISION_ROOT / relative_dir).mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file_handle:
        return list(csv.DictReader(file_handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_detection_records(dev_media_ids: set[str]) -> list[dict]:
    records = []
    path = OPT_ROOT / "12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl"
    with path.open() as file_handle:
        for line in file_handle:
            if not line.strip():
                continue
            record = json.loads(line)
            media_id = Path(record["image_path"]).stem
            if media_id not in dev_media_ids:
                raise RuntimeError(f"Non-DEV detection record found: {media_id}")
            record["media_id"] = media_id
            records.append(record)
    return sorted(records, key=lambda item: item["media_id"])


def read_pilot_media_ids() -> set[str]:
    path = REVISION_ROOT / "01_v3_gt_overlay/pilot_dev_selection.csv"
    if not path.exists():
        return set()
    return {row["media_id"] for row in read_csv(path)}


def build_vehicle_rows(
    detection_records: list[dict], mapping_by_media: dict[str, dict[str, str]], gt_by_media: dict[str, dict[str, str]], pilot_media_ids: set[str]
) -> list[dict[str, str]]:
    rows = []
    for record in detection_records:
        media_id = record["media_id"]
        source_group = mapping_by_media[media_id]["group_key"]
        old_v2_gt = gt_by_media.get(media_id, {}).get("v2_gt", "")
        for detection_index, detection in enumerate(record.get("detections", []), start=1):
            vehicle_id = f"v{detection_index:02d}"
            override = MANUAL_PILOT_LABELS.get((media_id, vehicle_id))
            if override:
                v3_label, parking_context, visibility, evidence = override
                review_status = "PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET"
                reviewer = "codex_contact_sheet"
            elif media_id in pilot_media_ids:
                v3_label = "uncertain"
                parking_context = "not reliably resolved in contact sheet"
                visibility = "limited"
                evidence = "Pilot contact sheet review did not provide reliable per-vehicle v3 evidence; kept uncertain rather than inferred from group intent."
                review_status = "PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET"
                reviewer = "codex_contact_sheet"
            else:
                v3_label = "uncertain"
                parking_context = "not_reviewed"
                visibility = "not_reviewed"
                evidence = "Full per-vehicle visual review was not completed; row is intentionally uncertain and is not human gold."
                review_status = "BLOCKED_VISUAL_REVIEW"
                reviewer = "codex_overlay_builder"
            rows.append(
                {
                    "media_id": media_id,
                    "vehicle_id": vehicle_id,
                    "bbox_xyxy": json.dumps(detection.get("bbox", []), separators=(",", ":")),
                    "source_group": source_group,
                    "candidate_old_v2_gt": old_v2_gt,
                    "v3_label": v3_label,
                    "parking_context": parking_context,
                    "visibility": visibility,
                    "evidence": evidence,
                    "review_status": review_status,
                    "reviewer": reviewer,
                    "review_date": TODAY,
                }
            )
    return rows


def build_image_rows(
    dev_media_ids: set[str], vehicle_rows: list[dict[str, str]], mapping_by_media: dict[str, dict[str, str]], split_by_media: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    vehicles_by_media = defaultdict(list)
    for row in vehicle_rows:
        vehicles_by_media[row["media_id"]].append(row)

    rows = []
    for media_id in sorted(dev_media_ids):
        media_vehicle_rows = vehicles_by_media.get(media_id, [])
        positive_vehicle_ids = [row["vehicle_id"] for row in media_vehicle_rows if row["v3_label"] in POSITIVE_LABELS]
        negative_vehicle_ids = [row["vehicle_id"] for row in media_vehicle_rows if row["v3_label"] in NEGATIVE_LABELS]
        uncertain_vehicle_ids = [row["vehicle_id"] for row in media_vehicle_rows if row["v3_label"] == "uncertain"]
        review_statuses = {row["review_status"] for row in media_vehicle_rows}
        if positive_vehicle_ids:
            image_label = "positive"
        elif uncertain_vehicle_ids:
            image_label = "uncertain"
        elif negative_vehicle_ids:
            image_label = "negative"
        else:
            image_label = "ignore"
        if review_statuses == {"PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET"}:
            review_status = "PILOT_VISUAL_REVIEWED_FROM_CONTACT_SHEET"
            label_basis = "limited contact-sheet visual review; not full human gold"
        else:
            review_status = "BLOCKED_VISUAL_REVIEW"
            label_basis = "full per-vehicle visual review not completed; uncertain is a safety placeholder"
        rows.append(
            {
                "media_id": media_id,
                "image_label": image_label,
                "positive_vehicle_ids": ";".join(positive_vehicle_ids),
                "negative_vehicle_ids": ";".join(negative_vehicle_ids),
                "uncertain_vehicle_ids": ";".join(uncertain_vehicle_ids),
                "source_type": "AIGC_AI_GENERATED",
                "split": split_by_media[media_id]["split"],
                "review_status": review_status,
                "label_basis": label_basis,
            }
        )
    return rows


def build_metrics(
    image_rows: list[dict[str, str]],
    vehicle_rows: list[dict[str, str]],
    split_counts: Counter,
    dev_group_counts: Counter,
    reviewed_image_count: int,
    pilot_vehicle_count: int,
) -> dict:
    vehicle_label_counts = Counter(row["v3_label"] for row in vehicle_rows)
    image_label_counts = Counter(row["image_label"] for row in image_rows)
    group_image_counts = defaultdict(Counter)
    group_vehicle_counts = defaultdict(Counter)
    media_to_group = {}
    for row in vehicle_rows:
        media_to_group[row["media_id"]] = row["source_group"]
        group_vehicle_counts[row["source_group"]][row["v3_label"]] += 1
    for row in image_rows:
        group_image_counts[media_to_group.get(row["media_id"], "UNKNOWN")][row["image_label"]] += 1
    return {
        "execution_date": TODAY,
        "source_split_counts": dict(split_counts),
        "dev_image_count": len(image_rows),
        "dev_vehicle_detection_count": len(vehicle_rows),
        "reviewed_pilot_image_count": reviewed_image_count,
        "reviewed_pilot_vehicle_row_count": pilot_vehicle_count,
        "v3_label_coverage": "partial",
        "image_review_coverage_ratio": round(reviewed_image_count / len(image_rows), 6) if image_rows else 0,
        "vehicle_review_coverage_ratio": round(pilot_vehicle_count / len(vehicle_rows), 6) if vehicle_rows else 0,
        "vehicle_label_counts": dict(vehicle_label_counts),
        "image_label_counts": dict(image_label_counts),
        "dev_group_counts": dict(sorted(dev_group_counts.items())),
        "group_vehicle_label_counts": {key: dict(value) for key, value in sorted(group_vehicle_counts.items())},
        "group_image_label_counts": {key: dict(value) for key, value in sorted(group_image_counts.items())},
        "metrics_authorized": False,
        "metric_blockers": ["FAIL_LABEL_COVERAGE", "FAIL_MISSING_REAL_ROI", "FAIL_DATA_DOMAIN_GAP"],
        "vehicle_level_metrics": {
            "positive_road_recall": None,
            "positive_two_bays_recall": None,
            "negative_in_bay_fpr": None,
            "negative_line_overrun_fpr": None,
            "negative_nose_tail_overhang_fpr": None,
            "gate_queue_fpr": None,
            "uncertain_rate": None,
            "coverage": round(pilot_vehicle_count / len(vehicle_rows), 6) if vehicle_rows else 0,
        },
        "image_level_metrics": {
            "image_positive_recall": None,
            "image_negative_fpr": None,
            "multi_vehicle_recall": None,
            "multi_vehicle_fpr": None,
        },
        "protocol_metrics": {
            "protocol_success_rate": 1.0,
            "inference_failure_count": 0,
            "parse_failure_count": 0,
            "latency_p50": None,
            "latency_p95": None,
            "note": "No VLM inference was run; protocol success here only covers artifact generation and ROI unit-test protocol.",
        },
    }


def build_frozen_hashes() -> dict:
    return {
        "execution_date": TODAY,
        "hash_algorithm": "sha256",
        "files": {str(path): sha256_file(path) for path in INPUT_FILES},
        "v2_frozen_files": {
            str(OPT_ROOT / "12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md"): sha256_file(
                OPT_ROOT / "12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md"
            ),
            str(OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv"): sha256_file(
                OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv"
            ),
            str(OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv"): sha256_file(
                OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv"
            ),
            str(OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json"): sha256_file(
                OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json"
            ),
        },
    }


def build_input_manifest(
    split_counts: Counter,
    dev_group_counts: Counter,
    detection_records: list[dict],
    vehicle_rows: list[dict[str, str]],
    image_rows: list[dict[str, str]],
) -> dict:
    parking_media_rows = read_parking_media_rows()
    source_counts = Counter(row.get("source_type", "") for row in parking_media_rows)
    return {
        "execution_date": TODAY,
        "execution_cwd": "/home/yanbo/net_vlm_yanboversion",
        "revision_root": str(REVISION_ROOT),
        "read_key_files": [str(path) for path in INPUT_FILES],
        "v2_split_counts": dict(split_counts),
        "dev_group_counts": dict(sorted(dev_group_counts.items())),
        "dev_detection_record_count": len(detection_records),
        "dev_vehicle_detection_count": len(vehicle_rows),
        "v3_image_label_rows": len(image_rows),
        "v3_vehicle_label_rows": len(vehicle_rows),
        "source_data_boundary": "Only v2_split.csv split=DEV media were used for label overlay and pilot visual review.",
        "old_parking_data_all_ai_generated_confirmed": all(row.get("source_type") == "ai_generated" for row in parking_media_rows),
        "formal_parking_media_source_type_counts": dict(source_counts),
        "current_real_robot_direct_parking_data_confirmed": False,
        "current_real_robot_direct_parking_data_evidence": "No parking_order_violation media row with source_type=robot_direct was found in 01_annotations/media.csv; capture_protocol.md mentions robot_direct as an allowed source, not as existing data.",
        "old_v2_val_holdout_consumed": False,
        "model_api_used": False,
        "ollama_preflight_executed": False,
        "ollama_preflight_reason": "ROI main route did not require VLM inference; per policy, no model request was started.",
        "model_request_count": 0,
        "model_concurrency": 0,
        "model_latency_p50": None,
        "model_latency_p95": None,
        "git_status_net_vlm_yanboversion": run_command(["git", "-C", str(YANBO_ROOT), "status", "--short", "--branch"]),
        "git_status_production_vlm": run_command(["git", "-C", str(PRODUCTION_VLM), "status", "--short", "--branch"]),
        "git_status_parking_optimization": run_command(["git", "-C", str(OPT_ROOT), "status", "--short", "--branch"]),
        "cuda_check": run_command(["bash", "-lc", "command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L || echo 'nvidia-smi not found'"]),
        "rule_test_result": "8 synthetic tests passed via standard-library runner; python3 -m pytest was unavailable because pytest is not installed.",
    }


def build_validation_report(input_manifest: dict, frozen_hashes: dict) -> dict:
    required_outputs = [
        REVISION_ROOT / "README.md",
        REVISION_ROOT / "00_definition/vehicle_parked_on_road_v3.0.md",
        REVISION_ROOT / "01_v3_gt_overlay/v3_dev_vehicle_labels.csv",
        REVISION_ROOT / "01_v3_gt_overlay/v3_dev_image_labels.csv",
        REVISION_ROOT / "02_roi_config/roi_schema.json",
        REVISION_ROOT / "02_roi_config/example_route_roi.json",
        REVISION_ROOT / "04_roi_rule/roi_rule.py",
        REVISION_ROOT / "04_roi_rule/test_roi_rule.py",
        REVISION_ROOT / "05_dev_eval/metrics.json",
        REVISION_ROOT / "05_dev_eval/report.md",
        REVISION_ROOT / "06_audit/input_manifest.json",
        REVISION_ROOT / "06_audit/frozen_hashes.json",
        REVISION_ROOT / "06_audit/validation_report.json",
        REVISION_ROOT / "EXECUTION_REPORT.md",
    ]
    return {
        "execution_date": TODAY,
        "required_outputs_present": {str(path): path.exists() for path in required_outputs},
        "all_required_outputs_present_after_generation": all(path.exists() for path in required_outputs),
        "v2_frozen_hashes_recorded": bool(frozen_hashes.get("v2_frozen_files")),
        "v2_split_dev_val_holdout": input_manifest["v2_split_counts"],
        "old_v2_val_holdout_consumed": False,
        "production_vlm_modified_by_this_revision": False,
        "production_vlm_preexisting_dirty": input_manifest["git_status_production_vlm"].strip() not in {"## main...origin/main", ""},
        "formal_parking_data_all_ai_generated": input_manifest["old_parking_data_all_ai_generated_confirmed"],
        "real_robot_direct_parking_data_confirmed": input_manifest["current_real_robot_direct_parking_data_confirmed"],
        "v3_label_coverage": "partial",
        "production_integration_ready": False,
        "real_robot_validation": "NOT_EXECUTED",
        "aigc_results_are_not_production_accuracy": True,
        "blocking_conditions": [
            "BLOCKED_VISUAL_REVIEW",
            "BLOCKED_MISSING_REAL_CAMERA_ROI",
            "BLOCKED_INCOMPLETE_V3_LABELS",
            "FAIL_DATA_DOMAIN_GAP",
        ],
    }


def write_text_reports(input_manifest: dict, metrics: dict, validation_report: dict) -> None:
    (REVISION_ROOT / "05_dev_eval/report.md").write_text(dev_eval_report(metrics, validation_report))
    (REVISION_ROOT / "06_audit/BLOCKED_VISUAL_REVIEW.md").write_text(blocked_visual_review(metrics))
    (REVISION_ROOT / "06_audit/BLOCKED_MISSING_REAL_CAMERA_ROI.md").write_text(blocked_missing_roi())
    (REVISION_ROOT / "06_audit/BLOCKED_INCOMPLETE_V3_LABELS.md").write_text(blocked_incomplete_labels(metrics))
    (REVISION_ROOT / "EXECUTION_REPORT.md").write_text(execution_report(input_manifest, metrics, validation_report))


def dev_eval_report(metrics: dict, validation_report: dict) -> str:
    return f"""# V3 DEV Prototype Evaluation Report

Execution date: {TODAY}

## Status

- V3_LABEL_COVERAGE=partial
- PRODUCTION_CLAIM=NOT_AUTHORIZED
- PRODUCTION_INTEGRATION_READY=false
- REAL_ROBOT_VALIDATION=NOT_EXECUTED
- AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY
- OLD_V2_VAL_HOLDOUT_CONSUMED=false

## Coverage

- DEV images represented: {metrics['dev_image_count']}
- DEV vehicle detections represented: {metrics['dev_vehicle_detection_count']}
- Pilot visually reviewed images: {metrics['reviewed_pilot_image_count']}
- Pilot visually reviewed vehicle rows: {metrics['reviewed_pilot_vehicle_row_count']}
- Image review coverage ratio: {metrics['image_review_coverage_ratio']}
- Vehicle review coverage ratio: {metrics['vehicle_review_coverage_ratio']}

## Metrics Decision

Formal recall/FPR metrics are not authorized because labels are partial, the dataset is AIGC, and no real fixed-camera ROI exists. Null metric values in `metrics.json` are intentional and prevent accidental production claims.

## Rule Tests

Synthetic ROI rule tests passed by direct standard-library runner. `pytest` is not installed in the current environment, so no dependency installation was attempted.

## Blockers

{chr(10).join(f'- {blocker}' for blocker in validation_report['blocking_conditions'])}
"""


def blocked_visual_review(metrics: dict) -> str:
    return f"""# BLOCKED_VISUAL_REVIEW

Execution date: {TODAY}

Full per-vehicle visual review for all 238 old DEV images was not completed in this execution. The overlay CSV includes all DEV detector rows, but non-reviewed rows are intentionally marked `uncertain` with `review_status=BLOCKED_VISUAL_REVIEW`.

- DEV images represented: {metrics['dev_image_count']}
- DEV vehicle rows represented: {metrics['dev_vehicle_detection_count']}
- Pilot reviewed images: {metrics['reviewed_pilot_image_count']}
- Pilot reviewed vehicle rows: {metrics['reviewed_pilot_vehicle_row_count']}
- V3_LABEL_COVERAGE=partial
- PRODUCTION_CLAIM=NOT_AUTHORIZED

No unreviewed row should be treated as v3 human gold.
"""


def blocked_missing_roi() -> str:
    return f"""# BLOCKED_MISSING_REAL_CAMERA_ROI

Execution date: {TODAY}

The old DEV source is an AIGC parking batch and does not provide a verified real fixed camera, route calibration, homography, production parking bay geometry, road area, or gate queue area.

The included `example_route_roi.json` is `PROTOTYPE_ONLY_SYNTHETIC_FIXTURE`, not a production ROI and not evidence of real-world accuracy.
"""


def blocked_incomplete_labels(metrics: dict) -> str:
    return f"""# BLOCKED_INCOMPLETE_V3_LABELS

Execution date: {TODAY}

The generated v3 overlay is complete as a row-level DEV manifest but incomplete as human-gold labeling.

- Image review coverage ratio: {metrics['image_review_coverage_ratio']}
- Vehicle review coverage ratio: {metrics['vehicle_review_coverage_ratio']}
- Metric blockers: {', '.join(metrics['metric_blockers'])}

Do not tune thresholds to this partial overlay or publish Winner/production claims from it.
"""


def execution_report(input_manifest: dict, metrics: dict, validation_report: dict) -> str:
    read_files = "\n".join(f"- `{path}`" for path in input_manifest["read_key_files"])
    dev_groups = "\n".join(f"- {group}: {count}" for group, count in input_manifest["dev_group_counts"].items())
    return f"""# V3 Parked-On-Road Execution Report

## 1. Execution

- Execution date: {TODAY}
- Execution cwd: `{input_manifest['execution_cwd']}`
- Revision root: `{input_manifest['revision_root']}`
- Production project modified: false
- Git commit/push/reset: not executed

## 2. Read Key Files

{read_files}

## 3. Confirmed Facts

- `/home/yanbo/net_vlm_yanboversion` is not itself a Git repository in this environment.
- `/home/yanbo/net_vlm_yanboversion/vlm` is a Git repository and was already dirty before this v3 revision work.
- `/home/yanbo/net_vlm_parking_optimization` was available as the clean optimization repository before new v3 files were created.
- Local CUDA was not available via `nvidia-smi`.
- v2 split counts are DEV/VAL/HOLDOUT = {input_manifest['v2_split_counts'].get('DEV')}/{input_manifest['v2_split_counts'].get('VAL')}/{input_manifest['v2_split_counts'].get('HOLDOUT')}.
- Old formal parking media rows are confirmed as AIGC source rows, not real robot evidence.
- No `parking_order_violation` media row with `source_type=robot_direct` was confirmed in the current main annotation metadata.
- No v2 VAL/HOLDOUT media were opened or used for this revision.
- No model API request was sent.

## 4. Reasoned Conclusions

- The new v3 definition cannot reuse v2 labels directly because p02/p04/p05/p06 and gate-queue semantics changed materially.
- The old AIGC DEV set can support a labeling overlay and synthetic ROI-rule prototype, but cannot establish fixed-camera ROI generalization.
- Because only partial visual review was completed, `uncertain` placeholders are safer than inferred labels from filename, group intent, or v2 GT.

## 5. Unverified Assumptions

- Real site camera IDs, route IDs, homography, parking bay polygons, road polygons, and gate queue polygons remain unavailable.
- Full per-vehicle human visual review of all 238 DEV images remains unavailable.
- Real robot validation data for this event remains unavailable.

## 6. New Business Definition

- `positive_road`: vehicle clearly parked in road/driving aisle and not in gate queue.
- `positive_two_bays`: vehicle clearly occupies two adjacent parking bays.
- `negative_in_bay`: vehicle normally in one bay or valid marked parking area.
- `negative_line_touch_or_minor_overrun`: line touch/minor side overrun without clear two-bay occupancy.
- `negative_nose_tail_overhang`: slight nose/tail protrusion while body remains in one bay.
- `negative_gate_queue`: normal gate queue.
- `uncertain`: insufficient road/bay evidence; no alert.
- Image positive uses OR logic over per-vehicle positives.

## 7. Old Data Use Scope

- Used old v2 DEV detections and manifests only.
- DEV images represented: {metrics['dev_image_count']}
- DEV vehicle detections represented: {metrics['dev_vehicle_detection_count']}
- Pilot images visually reviewed from contact sheet: {metrics['reviewed_pilot_image_count']}
- Pilot vehicle rows visually reviewed from contact sheet: {metrics['reviewed_pilot_vehicle_row_count']}
- VAL/HOLDOUT consumed: false

## 8. DEV Group Counts

{dev_groups}

## 9. V3 Label Completion

- V3_LABEL_COVERAGE=partial
- Vehicle label counts: `{json.dumps(metrics['vehicle_label_counts'], ensure_ascii=False, sort_keys=True)}`
- Image label counts: `{json.dumps(metrics['image_label_counts'], ensure_ascii=False, sort_keys=True)}`
- Non-reviewed rows are deliberately `uncertain` and must not be treated as human gold.

## 10. ROI Work

- ROI config count: 1 synthetic example config.
- Real production ROI count: 0.
- ROI schema supports camera_id, route_id, image_size, homography, parking_bays, parking_area, road_area, gate_queue_area, ignore_area, and thresholds.
- Rule engine provides `evaluate_vehicle_in_roi(vehicle, roi_config)` and `aggregate_image_decision(vehicle_decisions)`.
- Rule tests: {input_manifest['rule_test_result']}

## 11. Model API

- Model API used: false
- `/api/tags` preflight executed: false
- Reason: ROI main route did not require VLM inference.
- Model request count: 0
- Model concurrency: 0
- Latency p50/p95: null/null

## 12. DEV Result

Formal DEV recall/FPR metrics are not authorized. `metrics.json` records null metrics plus blockers instead of reporting misleading production-style scores.

## 13. Risks

- Partial labels can bias threshold tuning if treated as gold.
- AIGC geometry and lighting do not represent a real robot fixed camera distribution.
- Synthetic ROI fixtures prove code mechanics only, not deployment behavior.
- Existing dirty state in production `vlm` means future integration needs a separate clean audit before edits.

## 14. Blocking Conditions

{chr(10).join(f'- {blocker}' for blocker in validation_report['blocking_conditions'])}

## 15. Required Final Flags

- PRODUCTION_INTEGRATION_READY=false
- REAL_ROBOT_VALIDATION=NOT_EXECUTED
- AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY
- OLD_V2_VAL_HOLDOUT_CONSUMED=false

## 16. Next Steps

1. Obtain real fixed-camera route metadata and ROI polygons from production deployment.
2. Complete independent per-vehicle v3 labeling for DEV without using filename/group intent as gold.
3. Add segmentation or BEV footprint source before attempting positive decisions from real images.
4. Run a real-robot DEV/validation protocol only after ROI and labels are frozen.
5. Keep production integration blocked until real data, independent validation, latency, and FPR gates pass.
"""


def read_parking_media_rows() -> list[dict[str, str]]:
    media_path = DATASET_ROOT / "01_annotations/media.csv"
    rows = read_csv(media_path)
    return [row for row in rows if row.get("capture_batch") == "20260902_ai_generated_parking_order_violation_pov_b1_397" or row.get("scenario_id", "").startswith("POV_PARKING_B1_")]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.stdout.strip()


if __name__ == "__main__":
    main()
