# V12_F0_448_DIRECT DEV report

> Generation-intent shadow GT only; not per-image Human Gold or production accuracy.

## Primary operational binary metrics

- TP/FP/TN/FN: 1/0/120/58
- Precision: 1.0
- Recall: 0.01694915254237288
- F1: 0.03333333333333333
- Accuracy: 0.6759776536312849
- Specificity: 1.0
- FPR: 0.0
- Balanced Accuracy: 0.5084745762711864
- ordinary-negative FPR: 0.0
- hard-negative FPR: 0.0
- gate-queue FPR: 0.0
- model uncertain rate: 0.0
- p01 recall: 0.02564102564102564
- p05 recall: 0.0

## Boundary challenge (excluded from primary)

- P02_TOTAL: 35
- P02_MODEL_POSITIVE: 0
- P02_MODEL_NEGATIVE: 35
- P02_MODEL_UNCERTAIN: 0
- P02_FAILURE: 0

## Protocol and latency

- Protocol success rate: 1.0
- HTTP success rate: 1.0
- JSON/schema success rate: 1.0
- Semantic protocol success rate: 1.0
- Logical latency mean/P50/P90/P95/max: 5.073181435146444/5.03844/5.4109692/5.6898014/12.181513
- Images per logical request mean/min/max: {'mean': 1.0, 'min': 1, 'max': 1}
- Physical request count: 239
- Extra crop count: 0
- Extra model request count: 0

## Decision

- DEV_GATE_PASSED: false
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false
