# P3-lite geometry-only pilot report

Date: 2026-09-07

## Decision

`FINAL_STATUS=P3_LITE_GEOMETRY_NOT_VIABLE`

The frozen one-shot pilot did not pass the
promising gate. Immediate fail reasons: positive_recall_below_0.50, p01_recall_below_0.50.

Because `PILOT_GATE_PASSED=false`, the next
stage is stopped; no Ollama and no full DEV.

## Metrics

```text
PILOT_COUNT=60
TP=0
FP=0
TN=20
FN=40
Precision=0.000000
Recall=0.000000
F1=0.000000
p01_recall=0.000000
p05_recall=0.000000
negative_FPR=0.000000
gate_queue_FPR=0.000000
geometry_coverage=0.033333
YOLO_vehicle_detection_rate=1.000000
```

## Error decomposition

```json
{
  "geometry_rule_failure": 2,
  "line_detection_failure": 12,
  "slot_structure_failure": 26
}
```

The categories are assigned after inference by the evaluator. The geometry
engine itself did not receive group, role, GT, source_id, evaluation scope, or
media_id.

## Latency and request discipline

The detector was not rerun. Detector latency is the historical F2 measurement
bound to the cached detection. Geometry was measured locally in this run.

```text
P50_total_logical_seconds=0.262874
P95_total_logical_seconds=0.469474
VLM_gate_request_count=0
VLM_gate_request_rate=0
```

## Frozen bindings

```text
pilot_manifest_sha256=2f2f8de90026ed5edd7c00b4e64b16d59fa502010078955c7a7d9339e5afcce0
geometry_params_sha256=42e6a6e84d9c471ffb951b9fe898ed44af187ce43921dc59bdbdf08085036d72
geometry_evidence_sha256=9d801167e1a6f41057e7d53dff6a62a2d6332ab776aef09caeab7965b3059e56
YOLO_RERUN=false
VAL_CONSUMED=false
HOLDOUT_CONSUMED=false
```
