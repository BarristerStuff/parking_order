# ParkScope segmentation feasibility P0 report

## Decision

- `FINAL_STATUS=PARKSCOPE_SEGMENTATION_P0_GO`
- `PARKSCOPE_P0_GATE=GO`
- `READY_FOR_P1_STRUCTURED_GEOMETRY=true`
- This is a perception-feasibility decision only. It is not parking-violation accuracy, a DEV champion, robot validation, or production readiness.

## Frozen execution

- Upstream commit: `fbcfac7be597dd263570bbcd0377096c8a43d146`
- Checkpoint SHA256: `6d70bf088b7c324401afb97e09cf898afcc639d8ac837f4da7ef4afbc38d3d9b`
- Frozen Pilot manifest SHA256: `be44f0a84221fd54c018a80fe74f0fe8be9a5a50b5bd068bd3651b3db9a4b3c3`
- CPU-only, one default Ultralytics predict pass, 70/70 successful, zero technical errors.
- No Ollama/VLM request, parameter sweep, retraining, VAL, or HOLDOUT execution.

## Visual feasibility metrics

| Metric | Result |
|---|---:|
| Selected vehicle targets | 89 |
| Vehicle mask GOOD / PARTIAL / FAIL | 88 / 0 / 1 |
| Vehicle mask usable rate | 0.988764 |
| Parking geometry GOOD / PARTIAL / FAIL | 53 / 33 / 3 |
| Parking geometry usable rate | 0.966292 |
| Normal marked-bay geometry usable | 10/10 (1.000000) |
| p01 outside evidence usable | 8/10 (0.800000) |
| p03 separator evidence usable | 10/10 (1.000000) |
| Catastrophic wrong masks | 1/89 (0.011236) |

## Class semantics audit

`CLASS2_OBSERVED_SEMANTICS=MIXED`. Across all 38 images containing class 2, overlays show both thin line/separator-like masks and broader parking-space/area-like masks. Runtime names remain unchanged. In addition, class 1 (runtime name `no parking sign`) frequently forms broad parking-surface/line masks, so downstream P1 must not rely on the nominal class label alone without a frozen semantics policy.

## Important boundary and risk

The GO is narrow: the front end produced enough visually usable vehicle and nearby parking geometry on the preregistered Pilot to justify investigating a structured geometry algorithm. It does not prove that these masks support accurate final violation decisions. The class-semantic inconsistency and one catastrophic frozen-target binding case are explicit P1 risks. The p01 gate passed exactly at 8/10, leaving no margin.
