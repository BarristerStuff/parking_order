# V12_F2_896_CONTEXT DEV report

> Generation-intent shadow GT only; not per-image Human Gold or production accuracy.

## Primary operational binary metrics

- TP/FP/TN/FN: 0/5/115/59
- Precision: 0.0
- Recall: 0.0
- F1: None
- Accuracy: 0.6424581005586593
- Specificity: 0.9583333333333334
- FPR: 0.041666666666666664
- Balanced Accuracy: 0.4791666666666667
- ordinary-negative FPR: 0.02857142857142857
- hard-negative FPR: 0.06
- gate-queue FPR: 0.1
- model uncertain rate: 0.35195530726256985
- p01 recall: 0.0
- p05 recall: 0.0

## Boundary challenge (excluded from primary)

- P02_TOTAL: 35
- P02_MODEL_POSITIVE: 0
- P02_MODEL_NEGATIVE: 15
- P02_MODEL_UNCERTAIN: 20
- P02_FAILURE: 0

## Protocol and latency

- Protocol success rate: 1.0
- HTTP success rate: 1.0
- JSON/schema success rate: 1.0
- Semantic protocol success rate: 1.0
- Logical latency mean/P50/P90/P95/max: 20.324186481171548/22.541878/23.81788/24.077925/24.698312
- Images per logical request mean/min/max: {'mean': 3.5397489539748954, 'min': 2, 'max': 4}
- Physical request count: 846
- Extra crop count: 607
- Extra model request count: 607

## Decision

- DEV_GATE_PASSED: false
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false
