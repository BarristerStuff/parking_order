# v2 single-RGB perception route closure

Status: CLOSED_BY_USER_DECISION_RULE  
Date: 2026-09-08  
Closed scope: V2_PERCEPTION_GROUND_BAND_BASELINE_R0 only  

## Binding outcome

The authorized DEV-only baseline completed with:

- primary TP/FP/TN/FN: 24 / 39 / 106 / 27;
- primary positive recall: 0.47058823529411764;
- primary negative FPR: 0.2689655172413793;
- logical and physical JSON/schema success: 1.0 / 1.0;
- DEV images: 238; VAL image reads: 0; HOLDOUT image reads: 0.

The user-defined branch closes the single-RGB plan when overall primary positive
recall remains at or below 0.70. The observed recall is 0.47058823529411764,
so this condition is met. The inherited negative safety gates also fail:
primary FPR is above 0.10 and p02 FPR is above 0.20.

## Consequences

- Do not make a prompt variant, prompt sweep, crop/preprocessing sweep, geometry
  threshold sweep, VLM rerun, or same-route retry from this DEV result.
- Do not change v2.0 GT, p05 adjudication, split, seed, detector cache, or any
  frozen Step 2 tool/input.
- Do not access VAL or HOLDOUT.
- This closure does not alter historical P0/F0/F1/F2/P3 artifacts and does not
  claim that the overall parking-order problem is impossible under different
  data, sensing, definition, or model constraints.

## Evidence

- dev_baseline_report.md
- metrics.json
- subgroup_metrics.csv
- decision.json
- independent_validation.json

All evidence is AIGC development-only and is not Human Gold, production,
robot-camera, or real-world accuracy evidence.
