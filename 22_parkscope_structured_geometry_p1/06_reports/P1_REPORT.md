# ParkScope Structured Geometry P1 Pilot

## Decision

`PARKSCOPE_P1_CALIBRATION_NO_SAFE_GEOMETRY_RULE`

The preregistered 729-configuration calibration grid completed on the 30-image CAL partition. No configuration met both safety filters (precision >= 0.90 and FPR <= 0.10), so the protocol requires an immediate stop before independent EVAL. No EVAL, gate-secondary diagnostic, FULL DEV, VAL, or HOLDOUT was run.

## Calibration envelope

- Grid configurations: 729
- Safe configurations: 0
- Maximum observed CAL precision: 0.545455
- Minimum observed CAL FPR: 0.666667
- Maximum observed CAL recall: 0.800000
- Maximum observed CAL F1: 0.648649

These extrema need not come from one configuration. They are diagnostic only and were not used to alter the grid or rules.

## Integrity

- Frozen P0 inference reused; new ParkScope requests: 0.
- Ollama requests: 0.
- Targets: 89; raw geometry components: 228; invalid anchors: 1.
- EVAL remains unopened because calibration failed.
