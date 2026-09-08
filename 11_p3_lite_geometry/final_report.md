# parking_order_violation v1.2 — P3-lite Geometry Fast Gate

Date: 2026-09-07

## Final decision

```text
FINAL_STATUS=P3_LITE_GEOMETRY_NOT_VIABLE

PILOT_COUNT=60

YOLO_VEHICLE_DETECTION_RATE=1.000000

GEOMETRY_PILOT_TP=0
GEOMETRY_PILOT_FP=0
GEOMETRY_PILOT_TN=20
GEOMETRY_PILOT_FN=40
GEOMETRY_PILOT_PRECISION=0.000000
GEOMETRY_PILOT_RECALL=0.000000
GEOMETRY_PILOT_F1=0.000000
GEOMETRY_PILOT_P01_RECALL=0.000000
GEOMETRY_PILOT_P05_RECALL=0.000000
GEOMETRY_PILOT_GATE_FPR=0.000000
GEOMETRY_COVERAGE=0.033333

PILOT_GATE_PASSED=false

FULL_DEV_EXECUTED=false

DEV_TP=N/A
DEV_FP=N/A
DEV_TN=N/A
DEV_FN=N/A
DEV_PRECISION=N/A
DEV_RECALL=N/A
DEV_F1=N/A
DEV_P01_RECALL=N/A
DEV_P05_RECALL=N/A
DEV_GATE_QUEUE_FPR=N/A
DEV_HARD_NEGATIVE_FPR=N/A

VLM_GATE_REQUEST_COUNT=0
VLM_GATE_REQUEST_RATE=0.000000

P50_LATENCY=0.262874
P95_LATENCY=0.469474

READY_FOR_VAL=false

VAL_CONSUMED=false
HOLDOUT_CONSUMED=false

PROJECT_CODE_MODIFIED=false
SERVER_FILES_MODIFIED=false
SSH_USED=false
```

Additional frozen execution facts:

```text
CACHE_SOURCE=F2_EXISTING_DETECTOR_RUN
YOLO_RERUN=false
OLLAMA_CALLED=false
P3L_B_EXECUTED=false
```

## Fast Gate result

The one-shot geometry-only pilot produced no positive decisions:

```text
positive=0
normal=2
insufficient=58
```

It therefore triggered both mandatory immediate-fail conditions:

```text
positive_recall < 0.50   (actual 0.000000)
p01_recall < 0.50        (actual 0.000000)
```

The pilot also missed all 20 p05 multi-vehicle positives. The promising gate
was not close: positive recall, p01 recall, and p05 recall all failed their
minimum thresholds. In accordance with the frozen protocol, no parameters or
samples were changed after the pilot, P3L-B was not started, Ollama was not
called, and the 179-sample full DEV evaluation was not run.

## What the numbers mean

The detector cache contained at least one car/truck/bus bbox for all 60 pilot
images, so the sample-level vehicle-detection availability rate was 100%.
This availability rate does not prove that every relevant vehicle was detected
or localized correctly.

Only 2/60 samples received any high-confidence geometry decision, both
`normal`. The error decomposition for the 40 missed positives was:

| Subgroup | Line detection failure | Slot structure failure | Geometry rule failure | Total misses |
|---|---:|---:|---:|---:|
| p01 outside legal bay | 11 | 9 | 0 | 20 |
| p05 multi-vehicle | 1 | 17 | 2 | 20 |
| Total | 12 | 26 | 2 | 40 |

The dominant failure is not missing vehicle bboxes. It is the inability to
recover a high-confidence repeated parking-slot structure from arbitrary
front/oblique monocular views. For p01, many images expose too little reliable
line evidence. For p05, lines may be present, but the local pairing stage does
not recover a decisive slot layout around any violating vehicle.

`gate_queue_FPR=0` and overall negative FPR=0 are consequences of the engine
never emitting positive, not evidence that gate-queue discrimination has been
solved. The full-scene VLM gate veto is only allowed to suppress geometry
positives; with zero geometry positives it cannot improve recall and therefore
was correctly skipped.

## Latency

```text
historical_cached_YOLO_P50=0.063552s
historical_cached_YOLO_P95=0.079836s
measured_geometry_P50=0.193729s
measured_geometry_P95=0.324266s
estimated_total_logical_P50=0.262874s
estimated_total_logical_P95=0.469474s
```

The reported total logical latency combines the historical per-sample F2 YOLO
latency with geometry latency measured in this pilot. YOLO was not rerun, so
these are operational estimates rather than a new end-to-end wall-clock run.
There was no VLM latency and no HTTP model request.

## Frozen inputs and leakage controls

The pilot was frozen before geometry inference and was not replaced:

```text
pilot_manifest_sha256=2f2f8de90026ed5edd7c00b4e64b16d59fa502010078955c7a7d9339e5afcce0
geometry_params_sha256=42e6a6e84d9c471ffb951b9fe898ed44af187ce43921dc59bdbdf08085036d72
geometry_evidence_sha256=9d801167e1a6f41057e7d53dff6a62a2d6332ab776aef09caeab7965b3059e56
```

The geometry engine received only image pixels/content hash and cached vehicle
detections. It explicitly rejects GT, sample role, group, source_id,
evaluation scope, pilot stratum, and media_id fields. Evaluation metadata was
joined only after all geometry evidence had been written.

Ten non-primary debug samples were used once before the pilot. They comprised
five p02 boundary challenges and five GT-uncertain samples. The same single
generic parameter set was then frozen; no primary pilot image was used to tune
or revise thresholds.

## Is this route worth continuing?

No, not in its current P3-lite form. The experiment answers the intended
question: a bbox plus deterministic local OpenCV line/slot geometry does not
provide enough coverage or recall on this arbitrary-view dataset to justify a
full DEV run. Continuing with additional Hough/LSD threshold sweeps would add
DEV overfitting risk without evidence that the missing scene geometry is
recoverable.

A production-grade classical geometry route would likely require camera/domain
constraints, perspective calibration, parking-marking training data, and a
dedicated slot/road-layout model. Those costs exceed this Fast Gate and should
not be hidden inside further parameter tuning.

## Required successor choices — do not execute automatically

Choose one only in a new revision:

1. Use a vision model better suited to spatial-relation reasoning. Freeze a
   new model/revision and establish a new DEV/VAL protocol before evaluation.
2. Narrow the business definition to only the most obvious cases: completely
   outside parking bays, spanning multiple complete bays, or clearly blocking
   a traffic area. Rebuild the data definition and labels for that narrower
   event before new experiments.

## Safety audit

- Formal dataset validator: `status=valid`, `error_count=0`. It reported 687
  existing non-blocking warnings; no label or dataset file was changed.
- Formal project file count before/after: 1,636.
- Formal project content-tree SHA-256 before/after:
  `e7cb1ef92f1af22b4333a7a9e53f3a95c3c56bc1971d51f8dd53fcf221263846`.
- Frozen v1.2 definition, prompt, DEV manifest, F2 config, and F2 predictions
  retained their verified hashes.
- No Git commit, SSH, server modification, model modification, checkpoint
  download, VAL access, or HOLDOUT access occurred.
- All new/modified files are under
  `/home/yanbo/net_vlm_parking_optimization/11_p3_lite_geometry`.
