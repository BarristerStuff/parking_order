# v2.1 HOLDOUT final evaluation (resumed)

Date: 2026-09-15  
Status: **V2_1_HOLDOUT_PASS_READY_FOR_SHADOW_INTEGRATION**

## Facts

- This was a continuation after the first run stopped with `ENOSPC`; it was not a restart.
- Frozen allowlist: 79 HOLDOUT images. Detector results were reused from `holdout_detections.jsonl`; detector was not rerun.
- Attempt-1 ledger rows recorded: 215. Attempt-2 new successful model requests: 14 (8 Q1 + 6 Q3). Existing successful answers were reused by `(sample_token, vehicle_rank, question)`.
- Ollama preflight passed against `http://192.168.20.62:11434`; model `qwen3.5:4b` was present. Concurrency: 2.

### Gates and metrics

| Metric | Result | Wilson 95% CI | Gate | Status |
|---|---:|---:|---:|---|
| p01 recall | 8/8 = 100.00% | [67.56%, 100.00%] | >= 6/8 | PASS |
| negative FPR | 1/47 = 2.13% | [0.38%, 11.11%] | <= 5% | PASS |
| hn01 alert rate | 0/6 = 0.00% | [0.00%, 39.03%] | <= 2/6 | PASS |
| uncertain rate | 0/8 = 0.00% | [0.00%, 32.44%] | <= 10% | PASS |

Additional single-label reporting: p03 alert rate 0/6 = 0.00% (Wilson [0.00%, 39.03%]); p05 alert rate 0/4 = 0.00% (Wilson [0.00%, 48.99%]). p03/p05 are out-of-scope and are not included in TP/FP denominators. hn01 is reported separately and is not part of the negative FPR denominator.

- Per-image total latency: P50 1.778s; P95 4.209s.
- Per-image request count: total 121, P50 1.0, P95 2.0.
- Negative FP: `IMG_007452` (view in `evidence_fp/IMG_007452.png`).
- p01 FN: none.
- p01 suppressed by gate rule: none.
- Positive decisions outside the primary binary denominator (uncertain groups): `IMG_007690`, `IMG_007691`, `IMG_007680`, `IMG_007696`, `IMG_007698`, `IMG_007716`; these are not counted as negative FPs.

### DEV / VAL / HOLDOUT comparison

**更正（2026-09-15）：** DEV Q3 后数字已按 `07_gate_suppression_dev/q3_metrics.json` 重算并替换。DEV 的 negative FP 为 `IMG_007433`；uncertain 分母为全 DEV 238 张。HOLDOUT uncertain 同时报告全集 79 张分母，避免与 uncertain 组分母混淆。

| Set | p01 recall | negative FPR | hn01 alert rate | uncertain rate |
|---|---:|---:|---:|---:|
| DEV (Q3) | 19/23 = 82.61% | 1/143 = 0.70% | 0/18 = 0.00% | 1/238 = 0.42% |
| VAL (Q3) | 8/8 = 100.00% | 0/48 = 0.00% | 0/6 = 0.00% | 0/80 = 0.00% |
| HOLDOUT | 8/8 = 100.00% | 1/47 = 2.13% | 0/6 = 0.00% | 0/79 = 0.00% (全集；uncertain 组为 0/8) |

## Inference and decision

All four pre-registered HOLDOUT gates pass. The result is eligible for shadow integration only; it is not production validation. No tuning or rerun was performed after completion.

## Risks and boundaries

- AIGC/domain gap and possible dataset construction bias remain.
- The reference is evaluator-defined, not a new human-gold annotation.
- HOLDOUT was consumed once; `HOLDOUT_CONSUMED.lock` is final and must not be removed.
- Positive decisions on uncertain groups are separately listed and do not improve the primary metrics.
- Latency is from this environment and model server; production latency, robot behavior, and deployment reliability are not established.
- Ledger contains the preserved interrupted attempt history; one final partial line from the ENOSPC interruption was retained as raw evidence and is not treated as a successful result.
