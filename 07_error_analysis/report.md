# parking_order_violation P0 results

> Synthetic generation-intent DEV evidence only; not human visual gold or production accuracy.

- Scope: DEV/`train` only (239 images)
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false

## Binary decisive metrics

- TP: 5
- FP: 3
- TN: 117
- FN: 89
- precision: 0.625
- recall: 0.05319148936170213
- f1: 0.09803921568627451
- accuracy: 0.5700934579439252
- specificity: 0.975
- fpr: 0.025
- balanced_accuracy: 0.5140957446808511
- decisive_binary_count: 214

## Negative-slice FPR

- ordinary_negative: {'count': 70, 'FP': 2, 'TN': 68, 'fpr': 0.02857142857142857, 'model_uncertain_count': 0, 'failure_count': 0, 'decisive_coverage': 1.0}
- hard_negative: {'count': 50, 'FP': 1, 'TN': 49, 'fpr': 0.02, 'model_uncertain_count': 0, 'failure_count': 0, 'decisive_coverage': 1.0}
- gate_queue: {'count': 30, 'FP': 0, 'TN': 30, 'fpr': 0.0, 'model_uncertain_count': 0, 'failure_count': 0, 'decisive_coverage': 1.0}

## Abstention, failures, latency

- uncertain_rate: 0.0
- binary_gt_model_uncertain_rate: 0.0
- inference_failure_count: 0
- parse_failure_count: 0
- latency_seconds: {'count': 239, 'mean': 29.946019330543933, 'median': 29.506709, 'p95': 38.0389901, 'min': 9.519752, 'max': 44.340816}

## Error queues

- false_positives.csv: 3
- false_negatives.csv: 89
- hard_negative_false_positives.csv: 1
- gate_queue_false_positives.csv: 0
- model_uncertain.csv: 0
- parse_failures.csv: 0
- inference_failures.csv: 0
