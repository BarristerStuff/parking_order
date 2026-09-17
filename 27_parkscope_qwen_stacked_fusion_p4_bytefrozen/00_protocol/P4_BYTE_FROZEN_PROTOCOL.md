# P4 Byte-Frozen P3 Raster + Qwen Stacked OOF Protocol

## Objective

Preserve the exact retained P3 relation representation byte-for-byte, add the frozen v2.2 R1 Qwen semantic channel, and evaluate complementarity with strict nested OOF stacking.

## Phase A canonical artifact

- Baseline commit: `5e0a1b241b1e2ca7091ef3afccc9c64e86f34c94`
- Accepted root cause: `OPENCV_DIST_MASK_PRECISE_FLOAT32_CROSS_PROCESS_NONDETERMINISM`
- Canonical input: exact retained `.npy` bytes, 213/213 source and destination SHA verified.
- Raster recomputation, ParkScope inference, and distance-transform calls for P4 input are prohibited.

## Phase B frozen development experiment

- Primary: 166 frames, 47 positive, 119 negative.
- Legacy evaluation: 30 media IDs used only as an exclusion set; permanently quarantined.
- Qwen: `qwen3.5:4b`, frozen v2.2 R1 Q1/Q3 prompts, exactly two frame features.
- Base model: TINY_MIL_CNN_V1, byte-frozen rasters only.
- Validation: 5 outer folds and 4-fold inner OOF base scores.
- Meta model: StandardScaler + fixed balanced L2 liblinear logistic regression.
- Thresholds: 0.05 through 0.95 by 0.05, evaluated only after OOF score freeze.

## Boundaries

No independent EVAL, legacy quarantined evaluation, VAL, HOLDOUT, prompt/model/feature sweep, ParkScope inference, raster regeneration, real-robot validation, or production modification is authorized. Even an OOF pass leaves `CURRENT_DEVELOPMENT_WINNER=NONE`.
