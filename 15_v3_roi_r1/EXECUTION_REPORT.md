# V3 ROI R1 Execution Report

## 1. Execution

- Execution date: 2026-09-09
- Working directory: `/home/yanbo/net_vlm_yanboversion`
- R1 root: `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1`
- Git commit/push/reset/clean: not executed

## 2. R1 Inputs

- `/home/yanbo/net_vlm_yanboversion/docs/parking_order/codex-handoff.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/EXECUTION_REPORT.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/README.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/00_definition/vehicle_parked_on_road_v3.0.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/04_roi_rule/roi_rule.py`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/04_roi_rule/test_roi_rule.py`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/02_roi_config/roi_schema.json`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/02_roi_config/example_route_roi.json`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/05_dev_eval/metrics.json`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/06_audit/validation_report.json`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/06_audit/BLOCKED_VISUAL_REVIEW.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/06_audit/BLOCKED_MISSING_REAL_CAMERA_ROI.md`
- `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road/06_audit/BLOCKED_INCOMPLETE_V3_LABELS.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/v2_split.csv`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json`

## 3. R1 Outputs

- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/README.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/EXECUTION_REPORT.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/00_contract/r1_scope.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/00_contract/input_contract.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/roi_rule_r1.py`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/geometry.py`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/config_validator.py`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/test_roi_rule_r1.py`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/test_geometry_r1.py`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/01_roi_engine/rule_test_report.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/02_real_data_inventory/source_inventory.csv`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/02_real_data_inventory/camera_route_inventory.csv`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/02_real_data_inventory/real_data_status.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/02_real_data_inventory/README.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/calibration_manifest.csv`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/calibration_notes.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/pilot_labels.csv`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/pilot_report.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/BLOCKED_MISSING_REAL_CAMERA_DATA.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/03_real_roi_pilot/BLOCKED_MISSING_REAL_ROI.md`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/04_audit/input_manifest.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/04_audit/frozen_hashes.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/04_audit/validation_report.json`
- `/home/yanbo/net_vlm_parking_optimization/15_v3_roi_r1/04_audit/BLOCKED_REAL_E2E_EVALUATION.md`

## 4. Confirmed Facts

- `14_v3_parked_on_road/` was read as scaffold baseline and not edited by R1.
- Production `vlm` was read/status-checked only and not edited by R1.
- Old v2 split counts remain DEV/VAL/HOLDOUT = 238/80/79.
- Old v2 VAL/HOLDOUT media opened or consumed: false.
- CUDA check: `nvidia-smi not found`.
- Ollama/model API used: false.
- Standard-library tests passed: 24.
- Real parking camera data available: false.
- Real ROI calibration available: false.

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

- `py_compile`: return code 0.
- Geometry tests: `TEST_GEOMETRY_R1_PASSED=6`.
- ROI rule tests: `TEST_ROI_RULE_R1_PASSED=18`.
- Total standard-library tests passed: 24.
- Pytest used: false.

## 11. Real Data Inventory

- Source inventory rows: 412.
- Parking real-camera rows: 0.
- Fixed camera/route candidates: 0.
- Camera/route inventory rows: 1.
- REAL_CAMERA_DATA_AVAILABLE=false
- REAL_ROI_CALIBRATION_AVAILABLE=false
- R1_REAL_E2E_EVALUATION_BLOCKED=true

## 12. Real ROI Pilot

- Real ROI calibration completed: false.
- End-to-end real evaluation executed: false.
- `03_real_roi_pilot/` contains blocking records and empty manifest/report placeholders, not fake ROI configs.

## 13. Current Blockers

- BLOCKED_MISSING_REAL_CAMERA_DATA
- BLOCKED_MISSING_REAL_ROI
- BLOCKED_REAL_E2E_EVALUATION

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

R1_CODE_AND_TESTS_ACCEPTED=true
R1_REAL_ROI_EVALUATION=false
REAL_ROBOT_VALIDATION=NOT_EXECUTED
AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY
OLD_V2_VAL_HOLDOUT_CONSUMED=false
PRODUCTION_INTEGRATION_READY=false
