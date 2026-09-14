# V3 Parked-On-Road Execution Report

## 1. Execution

- Execution date: 2026-09-09
- Execution cwd: `/home/yanbo/net_vlm_yanboversion`
- Revision root: `/home/yanbo/net_vlm_parking_optimization/14_v3_parked_on_road`
- Production project modified: false
- Git commit/push/reset: not executed

## 2. Read Key Files

- `/home/yanbo/net_vlm_yanboversion/docs/parking_order/codex-handoff.md`
- `/home/yanbo/net_vlm_parking_optimization/README.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/00_definition/vehicle_not_in_bay_v2.0.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/STEP1_REPORT.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/01_gt_and_split/v2_split.csv`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/04_vlm_dev_baseline/dev_baseline_report.md`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/04_vlm_dev_baseline/metrics.json`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/04_vlm_dev_baseline/single_rgb_route_closure.md`
- `/home/yanbo/net_vlm_parking_optimization/13_spatiolm_successor_gate/final_report.md`
- `/home/yanbo/net_vlm_parking_optimization/08_final_audit/final_report.md`
- `/home/yanbo/net_vlm_parking_optimization/09_v1_1_error_review/v1_1_error_review_report.md`
- `/home/yanbo/net_vlm_parking_optimization/10_v1_2_fasttrack/final_fasttrack_report.md`
- `/home/yanbo/net_vlm_parking_optimization/11_p3_lite_geometry/final_report.md`
- `/home/yanbo/net_vlm_yanboversion/vlm/script/prompts.py`
- `/home/yanbo/net_vlm_yanboversion/vlm/script/alerts.py`
- `/home/yanbo/net_vlm_yanboversion/vlm/script/tts_publisher.py`
- `/home/yanbo/net_vlm_yanboversion/vlm/w_v/realtime_worker.py`
- `/home/yanbo/net_vlm_yanboversion/vlm/w_v/yolo_gate.py`
- `/home/yanbo/net_vlm_parking_optimization/02_ingest/manifests/formal_media_mapping.csv`
- `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl`

## 3. Confirmed Facts

- `/home/yanbo/net_vlm_yanboversion` is not itself a Git repository in this environment.
- `/home/yanbo/net_vlm_yanboversion/vlm` is a Git repository and was already dirty before this v3 revision work.
- `/home/yanbo/net_vlm_parking_optimization` was available as the clean optimization repository before new v3 files were created.
- Local CUDA was not available via `nvidia-smi`.
- v2 split counts are DEV/VAL/HOLDOUT = 238/80/79.
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
- DEV images represented: 238
- DEV vehicle detections represented: 1089
- Pilot images visually reviewed from contact sheet: 23
- Pilot vehicle rows visually reviewed from contact sheet: 85
- VAL/HOLDOUT consumed: false

## 8. DEV Group Counts

- hn01-gate-queue: 18
- hn02-faded-lines-but-confirmably-inside: 6
- hn03-perspective-looks-like-crossing: 6
- hn04-large-vehicle-compliant: 6
- hn05-adjacent-vehicle-occludes-lines: 6
- hn06-shadows-cracks-curbs-mimic-lines: 6
- n01-standard-inside-bay: 18
- n02-close-to-line-but-inside: 15
- n03-diagonal-bay-correct: 9
- n04-parallel-bay-correct: 9
- n05-multiple-all-correct: 9
- n06-special-marked-space-geometry-correct: 12
- p01-outside-legal-bay-clear: 23
- p02-cross-single-boundary-line: 21
- p03-span-two-bays: 18
- p04-angled-footprint-outside: 14
- p05-multi-vehicle-at-least-one-violation: 12
- p06-nose-or-tail-intrudes-aisle: 6
- u01-insufficient-parking-visual-evidence: 9
- u02-markings-severely-missing-or-occluded: 6
- u03-vehicle-cut-by-frame-edge: 3
- u04-night-or-blur-boundary-unreadable: 3
- u05-gate-queue-or-parking-ambiguous: 3

## 9. V3 Label Completion

- V3_LABEL_COVERAGE=partial
- Vehicle label counts: `{"negative_gate_queue": 3, "negative_in_bay": 13, "negative_line_touch_or_minor_overrun": 2, "negative_nose_tail_overhang": 1, "positive_road": 1, "positive_two_bays": 1, "uncertain": 1068}`
- Image label counts: `{"negative": 2, "positive": 2, "uncertain": 234}`
- Non-reviewed rows are deliberately `uncertain` and must not be treated as human gold.

## 10. ROI Work

- ROI config count: 1 synthetic example config.
- Real production ROI count: 0.
- ROI schema supports camera_id, route_id, image_size, homography, parking_bays, parking_area, road_area, gate_queue_area, ignore_area, and thresholds.
- Rule engine provides `evaluate_vehicle_in_roi(vehicle, roi_config)` and `aggregate_image_decision(vehicle_decisions)`.
- Rule tests: 8 synthetic tests passed via standard-library runner; python3 -m pytest was unavailable because pytest is not installed.

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

- BLOCKED_VISUAL_REVIEW
- BLOCKED_MISSING_REAL_CAMERA_ROI
- BLOCKED_INCOMPLETE_V3_LABELS
- FAIL_DATA_DOMAIN_GAP

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
