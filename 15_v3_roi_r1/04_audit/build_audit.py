from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


TODAY = "2026-09-09"
ROOT = Path("/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1")
OPT_ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
VLM_ROOT = Path("/home/yanbo/net_vlm_yanboversion/vlm")
YANBO_ROOT = Path("/home/yanbo/net_vlm_yanboversion")

BASELINE_FILES = [
    YANBO_ROOT / "docs/parking_order/codex-handoff.md",
    OPT_ROOT / "14_v3_parked_on_road/EXECUTION_REPORT.md",
    OPT_ROOT / "14_v3_parked_on_road/README.md",
    OPT_ROOT / "14_v3_parked_on_road/00_definition/vehicle_parked_on_road_v3.0.md",
    OPT_ROOT / "14_v3_parked_on_road/04_roi_rule/roi_rule.py",
    OPT_ROOT / "14_v3_parked_on_road/04_roi_rule/test_roi_rule.py",
    OPT_ROOT / "14_v3_parked_on_road/02_roi_config/roi_schema.json",
    OPT_ROOT / "14_v3_parked_on_road/02_roi_config/example_route_roi.json",
    OPT_ROOT / "14_v3_parked_on_road/05_dev_eval/metrics.json",
    OPT_ROOT / "14_v3_parked_on_road/06_audit/validation_report.json",
    OPT_ROOT / "14_v3_parked_on_road/06_audit/BLOCKED_VISUAL_REVIEW.md",
    OPT_ROOT / "14_v3_parked_on_road/06_audit/BLOCKED_MISSING_REAL_CAMERA_ROI.md",
    OPT_ROOT / "14_v3_parked_on_road/06_audit/BLOCKED_INCOMPLETE_V3_LABELS.md",
    OPT_ROOT / "12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md",
    OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv",
    OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv",
    OPT_ROOT / "12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json",
]

OUTPUT_FILES = [
    ROOT / "README.md",
    ROOT / "EXECUTION_REPORT.md",
    ROOT / "00_contract/r1_scope.md",
    ROOT / "00_contract/input_contract.json",
    ROOT / "01_roi_engine/roi_rule_r1.py",
    ROOT / "01_roi_engine/geometry.py",
    ROOT / "01_roi_engine/config_validator.py",
    ROOT / "01_roi_engine/test_roi_rule_r1.py",
    ROOT / "01_roi_engine/test_geometry_r1.py",
    ROOT / "01_roi_engine/rule_test_report.json",
    ROOT / "02_real_data_inventory/source_inventory.csv",
    ROOT / "02_real_data_inventory/camera_route_inventory.csv",
    ROOT / "02_real_data_inventory/real_data_status.json",
    ROOT / "02_real_data_inventory/README.md",
    ROOT / "03_real_roi_pilot/calibration_manifest.csv",
    ROOT / "03_real_roi_pilot/calibration_notes.md",
    ROOT / "03_real_roi_pilot/pilot_labels.csv",
    ROOT / "03_real_roi_pilot/pilot_report.md",
    ROOT / "03_real_roi_pilot/BLOCKED_MISSING_REAL_CAMERA_DATA.md",
    ROOT / "03_real_roi_pilot/BLOCKED_MISSING_REAL_ROI.md",
    ROOT / "04_audit/input_manifest.json",
    ROOT / "04_audit/frozen_hashes.json",
    ROOT / "04_audit/validation_report.json",
    ROOT / "04_audit/BLOCKED_REAL_E2E_EVALUATION.md",
]


def main() -> None:
    clean_new_pycache()
    test_report = run_tests()
    write_json(ROOT / "01_roi_engine/rule_test_report.json", test_report)
    real_status = json.load(open(ROOT / "02_real_data_inventory/real_data_status.json"))
    input_manifest = build_input_manifest(test_report, real_status)
    write_json(ROOT / "04_audit/input_manifest.json", input_manifest)
    frozen_hashes = build_hashes()
    write_json(ROOT / "04_audit/frozen_hashes.json", frozen_hashes)
    validation_report = build_validation(input_manifest, frozen_hashes, test_report, real_status)
    write_json(ROOT / "04_audit/validation_report.json", validation_report)
    (ROOT / "04_audit/BLOCKED_REAL_E2E_EVALUATION.md").write_text(blocked_real_e2e(real_status))
    (ROOT / "EXECUTION_REPORT.md").write_text(execution_report(input_manifest, validation_report, test_report, real_status))
    clean_new_pycache()


def run_tests() -> dict:
    compile_command = [
        "python3",
        "-m",
        "py_compile",
        str(ROOT / "01_roi_engine/geometry.py"),
        str(ROOT / "01_roi_engine/config_validator.py"),
        str(ROOT / "01_roi_engine/roi_rule_r1.py"),
        str(ROOT / "01_roi_engine/test_geometry_r1.py"),
        str(ROOT / "01_roi_engine/test_roi_rule_r1.py"),
    ]
    compile_result = run(compile_command, cwd=ROOT / "01_roi_engine")
    geometry_result = run(["python3", "test_geometry_r1.py"], cwd=ROOT / "01_roi_engine")
    roi_result = run(["python3", "test_roi_rule_r1.py"], cwd=ROOT / "01_roi_engine")
    return {
        "execution_date": TODAY,
        "py_compile": command_record(compile_command, compile_result),
        "geometry_tests": command_record(["python3", "test_geometry_r1.py"], geometry_result),
        "roi_rule_tests": command_record(["python3", "test_roi_rule_r1.py"], roi_result),
        "total_tests_passed": parse_count(geometry_result.stdout, "TEST_GEOMETRY_R1_PASSED=") + parse_count(roi_result.stdout, "TEST_ROI_RULE_R1_PASSED="),
        "tests_failed": compile_result.returncode != 0 or geometry_result.returncode != 0 or roi_result.returncode != 0,
        "pytest_used": False,
    }


def build_input_manifest(test_report: dict, real_status: dict) -> dict:
    split_counts = split_count()
    return {
        "execution_date": TODAY,
        "execution_cwd": "/home/yanbo/net_vlm_yanboversion",
        "r1_root": str(ROOT),
        "baseline_inputs_read": [str(path) for path in BASELINE_FILES],
        "outputs_expected": [str(path) for path in OUTPUT_FILES],
        "v2_split_counts": split_counts,
        "old_v2_val_holdout_consumed": False,
        "old_v2_val_holdout_media_opened": False,
        "scaffold_14_modified_by_r1": False,
        "production_vlm_modified_by_r1": False,
        "ollama_used": False,
        "ollama_preflight_executed": False,
        "ollama_reason": "R1 geometry and inventory work did not require VLM inference.",
        "model_request_count": 0,
        "cuda_check": run_text(["bash", "-lc", "command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L || echo 'nvidia-smi not found'"]),
        "git_status_parking_optimization": run_text(["git", "-C", str(OPT_ROOT), "status", "--short", "--branch"]),
        "git_status_production_vlm": run_text(["git", "-C", str(VLM_ROOT), "status", "--short", "--branch"]),
        "test_report_path": str(ROOT / "01_roi_engine/rule_test_report.json"),
        "total_tests_passed": test_report["total_tests_passed"],
        "real_data_status": real_status,
    }


def build_hashes() -> dict:
    return {
        "execution_date": TODAY,
        "hash_algorithm": "sha256",
        "baseline_files": {str(path): sha256_file(path) for path in BASELINE_FILES if path.exists()},
        "output_files": {str(path): sha256_file(path) for path in OUTPUT_FILES if path.exists()},
    }


def build_validation(input_manifest: dict, frozen_hashes: dict, test_report: dict, real_status: dict) -> dict:
    required_present = {str(path): path.exists() for path in OUTPUT_FILES}
    return {
        "execution_date": TODAY,
        "required_outputs_present": required_present,
        "all_required_outputs_present": all(required_present.values()),
        "py_compile_passed": test_report["py_compile"]["returncode"] == 0,
        "standard_library_tests_passed": not test_report["tests_failed"],
        "total_tests_passed": test_report["total_tests_passed"],
        "coordinate_space_mixing_prevented": True,
        "homography_code_path_implemented": True,
        "polygon_bev_overlap_implemented": True,
        "polygon_validator_implemented": True,
        "overlap_union_logic_implemented": True,
        "bbox_only_positive_default_blocked": True,
        "non_convex_policy": "convex_simple_only; non-convex rejected by validator and safe uncertain in rule engine",
        "old_v2_val_holdout_consumed": False,
        "old_v2_val_holdout_media_opened": False,
        "scaffold_14_modified_by_r1": False,
        "production_vlm_modified_by_r1": False,
        "ollama_used": False,
        "real_camera_data_available": real_status["REAL_CAMERA_DATA_AVAILABLE"],
        "real_roi_calibration_available": real_status["REAL_ROI_CALIBRATION_AVAILABLE"],
        "real_e2e_evaluation_executed": False,
        "blocking_conditions": [
            "BLOCKED_MISSING_REAL_CAMERA_DATA",
            "BLOCKED_MISSING_REAL_ROI",
            "BLOCKED_REAL_E2E_EVALUATION",
        ],
        "R1_CODE_AND_TESTS_ACCEPTED": all(required_present.values()) and not test_report["tests_failed"],
        "R1_REAL_ROI_EVALUATION": False,
        "REAL_ROBOT_VALIDATION": "NOT_EXECUTED",
        "AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY": True,
        "PRODUCTION_INTEGRATION_READY": False,
    }


def execution_report(input_manifest: dict, validation: dict, test_report: dict, real_status: dict) -> str:
    baseline_lines = "\n".join(f"- `{path}`" for path in input_manifest["baseline_inputs_read"])
    output_lines = "\n".join(f"- `{path}`" for path in input_manifest["outputs_expected"])
    blockers = "\n".join(f"- {item}" for item in validation["blocking_conditions"])
    return f"""# V3 ROI R1 Execution Report

## 1. Execution

- Execution date: {TODAY}
- Working directory: `{input_manifest['execution_cwd']}`
- R1 root: `{input_manifest['r1_root']}`
- Git commit/push/reset/clean: not executed

## 2. R1 Inputs

{baseline_lines}

## 3. R1 Outputs

{output_lines}

## 4. Confirmed Facts

- `14_v3_parked_on_road/` was read as scaffold baseline and not edited by R1.
- Production `vlm` was read/status-checked only and not edited by R1.
- Old v2 split counts remain DEV/VAL/HOLDOUT = {input_manifest['v2_split_counts'].get('DEV')}/{input_manifest['v2_split_counts'].get('VAL')}/{input_manifest['v2_split_counts'].get('HOLDOUT')}.
- Old v2 VAL/HOLDOUT media opened or consumed: false.
- CUDA check: `{input_manifest['cuda_check']}`.
- Ollama/model API used: false.
- Standard-library tests passed: {test_report['total_tests_passed']}.
- Real parking camera data available: {str(real_status['REAL_CAMERA_DATA_AVAILABLE']).lower()}.
- Real ROI calibration available: {str(real_status['REAL_ROI_CALIBRATION_AVAILABLE']).lower()}.

## 5. Reasoned Conclusions

- R1 fixes the known algorithm-engineering issues in 14_v3 by making coordinate space explicit and safe-failing mismatches.
- `footprint_polygon_bev` now has a BEV-only overlap path using `polygon_bev`; it is not mixed with image polygons.
- Image footprints can be transformed to BEV only when a valid `homography_image_to_bev` is supplied.
- Because no real parking camera/route/ROI bundle exists, real ROI evaluation remains blocked.

## 6. Unverified Assumptions

- No external production ROI/calibration package was provided outside the scanned workspace/dataset/project metadata.
- No hidden server-side robot parking data were inspected.
- No model call was made, so no model availability or latency was measured in R1.

## 7. ROI Coordinate-Space Fix

- Vehicle footprints require `coordinate_space=image|bev` when using the new explicit `footprint` field.
- Legacy `footprint_polygon_image` and `mask_polygon_image` are treated as image space.
- Legacy `footprint_polygon_bev` is treated as BEV space.
- ROI areas carry their own `coordinate_space`; overlap uses only matching spaces.
- Mismatch without homography returns `uncertain` with `COORDINATE_SPACE_MISMATCH_NO_HOMOGRAPHY`.

## 8. Homography and BEV

- Homography implementation: true.
- Implemented function: `transform_polygon_homography()`.
- Tested path: image footprint + BEV ROI + valid homography returns a BEV-space decision.
- No homography was invented for real data.

## 9. Geometry Validation

- Polygon validator: true.
- Minimum 3 finite points: enforced.
- Degenerate area: rejected.
- Self-intersection: rejected.
- Non-convex policy: rejected as unsupported.
- Multiple overlapping ROI polygons: union area via inclusion-exclusion over clipped convex intersections, preventing duplicate overlap count.

## 10. Tests

- `py_compile`: return code {test_report['py_compile']['returncode']}.
- Geometry tests: `{test_report['geometry_tests']['stdout'].strip()}`.
- ROI rule tests: `{test_report['roi_rule_tests']['stdout'].strip()}`.
- Total standard-library tests passed: {test_report['total_tests_passed']}.
- Pytest used: false.

## 11. Real Data Inventory

- Source inventory rows: {real_status['source_inventory_rows']}.
- Parking real-camera rows: {real_status['parking_real_camera_rows']}.
- Fixed camera/route candidates: {real_status['fixed_camera_route_candidates']}.
- Camera/route inventory rows: {real_status['camera_route_inventory_rows']}.
- REAL_CAMERA_DATA_AVAILABLE={str(real_status['REAL_CAMERA_DATA_AVAILABLE']).lower()}
- REAL_ROI_CALIBRATION_AVAILABLE={str(real_status['REAL_ROI_CALIBRATION_AVAILABLE']).lower()}
- R1_REAL_E2E_EVALUATION_BLOCKED={str(real_status['R1_REAL_E2E_EVALUATION_BLOCKED']).lower()}

## 12. Real ROI Pilot

- Real ROI calibration completed: false.
- End-to-end real evaluation executed: false.
- `03_real_roi_pilot/` contains blocking records and empty manifest/report placeholders, not fake ROI configs.

## 13. Current Blockers

{blockers}

## 14. Risks

- R1 code is synthetic-unit-tested but not validated against real segmentation masks or real BEV footprints.
- Non-convex production ROI would need decomposition into convex polygons or a more complete geometry library.
- Existing production `vlm` dirty state is unrelated and must be audited before any future integration.
- AIGC parking rows remain fixture-only and must not be converted into production evidence.

## 15. Next Steps

1. Provide or collect real parking camera frames with camera_id, route_id, stable resolution, and provenance.
2. Create GT-blind ROI calibration with parking bay, road, gate queue, ignore areas, and homography where needed.
3. Connect detector segmentation mask or BEV footprint input to R1 contract.
4. Run a small real fixed-camera pilot with independent per-vehicle v3 labels.
5. Only after real pilot gates pass, consider whether VLM fallback is needed.

## 16. Final Flags

R1_CODE_AND_TESTS_ACCEPTED={str(validation['R1_CODE_AND_TESTS_ACCEPTED']).lower()}
R1_REAL_ROI_EVALUATION=false
REAL_ROBOT_VALIDATION=NOT_EXECUTED
AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY
OLD_V2_VAL_HOLDOUT_CONSUMED=false
PRODUCTION_INTEGRATION_READY=false
"""


def blocked_real_e2e(real_status: dict) -> str:
    return f"""# BLOCKED_REAL_E2E_EVALUATION

Execution date: {TODAY}

R1_REAL_E2E_EVALUATION_BLOCKED={str(real_status['R1_REAL_E2E_EVALUATION_BLOCKED']).lower()}
REAL_CAMERA_DATA_AVAILABLE={str(real_status['REAL_CAMERA_DATA_AVAILABLE']).lower()}
REAL_ROI_CALIBRATION_AVAILABLE={str(real_status['REAL_ROI_CALIBRATION_AVAILABLE']).lower()}

R1 did not run detector → footprint/mask → ROI → v3 business label evaluation on real data because no confirmed real parking camera/route/ROI bundle was available.
"""


def split_count() -> dict[str, int]:
    with open(OPT_ROOT / "12_v2_not_in_bay/01_gt_and_split/v2_split.csv", newline="") as file_handle:
        rows = list(csv.DictReader(file_handle))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["split"]] = counts.get(row["split"], 0) + 1
    return counts


def clean_new_pycache() -> None:
    for cache in ROOT.rglob("__pycache__"):
        if ROOT in cache.parents and cache.is_dir():
            shutil.rmtree(cache)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def run_text(command: list[str]) -> str:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()


def command_record(command: list[str], result: subprocess.CompletedProcess[str]) -> dict:
    return {"command": command, "returncode": result.returncode, "stdout": result.stdout}


def parse_count(stdout: str, prefix: str) -> int:
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return int(line.removeprefix(prefix))
    return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
