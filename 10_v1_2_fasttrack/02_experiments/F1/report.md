# V12_F1_896_LETTERBOX DEV report

> Generation-intent shadow GT only; not per-image Human Gold or production accuracy.

## Primary operational binary metrics

- TP/FP/TN/FN: 0/0/120/59
- Precision: None
- Recall: 0.0
- F1: None
- Accuracy: 0.6703910614525139
- Specificity: 1.0
- FPR: 0.0
- Balanced Accuracy: 0.5
- ordinary-negative FPR: 0.0
- hard-negative FPR: 0.0
- gate-queue FPR: 0.0
- model uncertain rate: 0.0
- p01 recall: 0.0
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
- Logical latency mean/P50/P90/P95/max: 6.169359531380754/6.001635/6.5320024/6.6986953/17.528092
- Images per logical request mean/min/max: {'mean': 1.0, 'min': 1, 'max': 1}
- Physical request count: 239
- Extra crop count: 0
- Extra model request count: 0

## Decision

- DEV_GATE_PASSED: false
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false
