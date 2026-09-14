# V3 DEV Prototype Evaluation Report

Execution date: 2026-09-09

## Status

- V3_LABEL_COVERAGE=partial
- PRODUCTION_CLAIM=NOT_AUTHORIZED
- PRODUCTION_INTEGRATION_READY=false
- REAL_ROBOT_VALIDATION=NOT_EXECUTED
- AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY
- OLD_V2_VAL_HOLDOUT_CONSUMED=false

## Coverage

- DEV images represented: 238
- DEV vehicle detections represented: 1089
- Pilot visually reviewed images: 23
- Pilot visually reviewed vehicle rows: 85
- Image review coverage ratio: 0.096639
- Vehicle review coverage ratio: 0.078053

## Metrics Decision

Formal recall/FPR metrics are not authorized because labels are partial, the dataset is AIGC, and no real fixed-camera ROI exists. Null metric values in `metrics.json` are intentional and prevent accidental production claims.

## Rule Tests

Synthetic ROI rule tests passed by direct standard-library runner. `pytest` is not installed in the current environment, so no dependency installation was attempted.

## Blockers

- BLOCKED_VISUAL_REVIEW
- BLOCKED_MISSING_REAL_CAMERA_ROI
- BLOCKED_INCOMPLETE_V3_LABELS
- FAIL_DATA_DOMAIN_GAP
