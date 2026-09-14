# V5 spatial evidence experiment — BLOCKED FOOTPRINT

**Final status: V5_BLOCKED_FOOTPRINT** (2026-09-10).

Actual work: 60 allowed V4 DEV images segmented once with existing local YOLOE; 196 raw detections, 195 after dedup; raw polygons and 60 overlays saved. 155/240 prior reviewed instances associated by posthoc bbox IoU, not classification Recall. No validated ground-contact footprint. No pilot road/bay ROI. Pilot rules and VLM NOT_EXECUTED.

Read `EXECUTION_REPORT.md`, `05_evaluation/p0_metrics.json`, `06_audit/audit_result.json`, and `06_audit/p0_gate.json`.

Runtime (already installed, no install required):
`/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/.venv_yoloe/bin/python`

Safe checks:
```bash
PYTHONDONTWRITEBYTECODE=1 /home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/.venv_yoloe/bin/python /home/yanbo/net_vlm_parking_optimization/17_v5_spatial_evidence_vlm/tests/run_all_tests.py
python3 /home/yanbo/net_vlm_parking_optimization/17_v5_spatial_evidence_vlm/06_audit/check_p0_gate.py
python3 /home/yanbo/net_vlm_parking_optimization/17_v5_spatial_evidence_vlm/06_audit/audit_v5.py
```
P0 gate intentionally exits 2. Test/audit scripts update only their own V5 reports; if run again after final hash generation, regenerate the final hash manifest and record the recheck. Do not rerun preparation or segmentation over existing results. No VLM client was created because the required gate failed; there are no empty fake VLM result files.
