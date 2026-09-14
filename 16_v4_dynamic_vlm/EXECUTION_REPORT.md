# V4 Dynamic Context VLM Execution Report

**Date:** 2026-09-09  
**Event:** `parking_order_violation`  
**Final status:** `NO_QUALIFIED_CANDIDATE`

## 1. Independent judgment: facts, inference, risks

### Facts

- The frozen v2 definition already included road/open-aisle positives, substantive two-bay positives, minor-line/nose-tail negatives, and normal gate-queue negatives. V4 did not change the business definition.
- DEV inventory was 238 images; VAL/HOLDOUT metadata was 80/79. Only DEV media were allowlisted and decoded. The fixed pilot contains 60 DEV images with the requested group-stratified counts and seed `20260909`.
- The old DEV detector cache has 238 image rows and 1,089 raw detection rows. On the pilot, 259 raw boxes were present; fixed cross-class IoU `>0.80` deduplication retained 252 targets and suppressed 7 duplicates. Pixel review matched 240 detector targets to reviewed vehicle instances and marked 12 non-vehicle fragments/overlap boxes as false detections; no reviewed pilot vehicle was a cache miss.
- Reference review was completed before formal model requests from original pixels, numbered full-scene images, and full-vehicle context crops. `REFERENCE_BASIS=AI_VISUAL_REVIEWED_PROVISIONAL`; `HUMAN_GOLD=false`; 240 reviewed vehicle instances; 32 positive, 195 negative, 13 visual uncertain, 0 disputed.
- Direct Ollama preflight succeeded. `/api/tags` contained `qwen3.5:4b`; `/api/ps` was recorded. No tunnel, proxy, server change, CUDA setting, model pull, production edit, or VAL/HOLDOUT image read was used.
- R0 completed 108 physical pilot requests. 107 returned HTTP 200/valid JSON; one request returned HTTP 500 because the model runner unexpectedly stopped. It was not retried because server execution state was unknown.
- R1 completed the same 108 physical pilot requests. All 108 returned HTTP 200/valid JSON. R1 changed only the input protocol from a multi-image array to one composite JPEG per request; model, prompt semantics, crop geometry, detector cache, reference labels, decisioner, and pilot media were frozen unchanged.

### Inference

- The global-scene/full-vehicle hypothesis was not supported by this Qwen route. R1 improved image alert recall only from 2/32 to 3/32, while two-bay recall stayed 0/18 and decisive coverage fell from 169/227 to 141/227.
- The dominant failure was model spatial-relation reasoning and field consistency, not detector coverage or JSON parsing. R1 produced 93 semantic conflicts at the target-decision level; the evaluator retained them as conservative uncertain outcomes. A representative raw response asserted `road_or_drive_aisle=yes` together with `in_one_bay_or_designated_area=yes`, which correctly became `SEMANTIC_CONFLICT` rather than an alert.
- The composite protocol fixed the R0 single protocol failure and reached required-target schema coverage 60/60, but did not produce a qualified candidate. It is therefore not justified to continue prompt/crop/model sweeps on this DEV pilot.

### Risks and boundaries

- All metrics below are `AIGC_ONLY`, based on provisional AI visual review, and are `NOT_REAL_ROBOT_ACCURACY`.
- This pilot is small and stratified for development. Six gate images with zero image-level false alarms can only be reported as “no false alarm observed in this pilot,” not as proof of FPR below 5%.
- The old detector cache validates only this historical DEV cache path. It does not establish detector coverage, latency, or target identity on arbitrary new images.
- R1 is a same-pilot correction, not an independent validation set. It must not be used as an unbiased confirmation of R0.
- VLM requests were batched up to three targets, but each multi-vehicle image costs multiple physical requests. Pilot request count was 108 per candidate; p50/p95 requests per image were 2/4, with more requests on high-count images.
- A production camera/ROI/BEV package and real parking frames were not available. Their absence limits production conclusions but was not the V4 AIGC development blocker.

## 2. Frozen contracts and artifacts

- `contracts/dev_image_allowlist.csv` — 238 DEV-only rows.
- `contracts/forbidden_split_metadata.csv` — VAL/HOLDOUT metadata only; no image decoding.
- `contracts/pilot_manifest.csv` — fixed 60-image manifest, seed `20260909`.
- `contracts/run_contract.json` — R0 model/preprocess/detector/request contract.
- `contracts/r1_protocol_freeze.json` — one evidence-driven input-only R1 change.
- `contracts/prompt_v4_r0.txt`, `contracts/prompt_v4_r1.txt` — frozen prompts.
- `contracts/decision_rules.md` — deterministic decision contract.
- `reference/REFERENCE_FREEZE.json` — reference SHA freeze before formal requests.
- `reference/reference_images.jsonl`, `reference/reference_instances.jsonl`, CSV versions, review logs, and detector diagnostics.
- `inference/run_v4.py` — direct Ollama runner, strict schema handling, batch support, request logging, reusable `classify_image`.
- `evaluator/decision.py`, `evaluator/metrics.py`, `tests/run_tests.py` — strict parser, decisioner, evaluator, and ten standard-library tests.
- `audit/audit_result_r0.json`, `audit/audit_result_r1.json` — independent integrity checks and metric recomputation; both `PASS_INTEGRITY`.
- `outputs/pilot_r0/` and `outputs/pilot_r1/` — raw request logs, raw model responses, target predictions, image predictions, summaries.
- `metrics/pilot_r0/` and `metrics/pilot_r1/` — metrics, Wilson intervals, subgroup metrics, error rows, latency, evaluation inputs, and representative error images.

## 3. R1 primary metrics

All fractions are shown as integer numerator/denominator; intervals are Wilson 95%.

### Vehicle-level alert and semantic metrics

| Metric | Result |
|---|---:|
| Road positive alert recall | 2/14 = 0.142857; CI [0.040094, 0.399414] |
| Road positive subtype accuracy | 2/14 = 0.142857; CI [0.040094, 0.399414] |
| Two-bay positive alert recall | 0/18 = 0.000000; CI [0, 0.175879] |
| Two-bay positive subtype accuracy | 0/18 = 0.000000; CI [0, 0.175879] |
| Ordinary parking FPR | 1/120 = 0.008333; CI [0.001472, 0.045696] |
| Line/minor/nose-tail FPR | 0/55 = 0.000000; CI [0, 0.065285] |
| Gate queue FPR | 0/20 = 0.000000; CI [0, 0.161125] |
| Vehicle alert TP/FP/TN/FN | 2/1/194/30; support 227 |
| Vehicle alert recall | 2/32 = 0.062500; CI [0.017311, 0.201471] |
| Vehicle alert FPR | 1/195 = 0.005128; CI [0.000906, 0.028472] |
| Vehicle decisive coverage | 141/227 = 0.621145; CI [0.556519, 0.681741] |
| Vehicle protocol failure rate | 0/240 = 0.000000 |
| Model semantic uncertain rate | 89/240 = 0.370833 |
| Reference visual-uncertain vehicles | 13/240; excluded from primary binary metrics |

### Image-level alert metrics

Primary binary reference images are 32 positive and 22 negative; six reference-uncertain images are excluded from primary binary confusion but reported.

- Alert TP/FP/TN/FN = **3/0/22/29**, support 54.
- Recall = **3/32 = 0.093750**, Wilson 95% CI **[0.032402, 0.242181]**.
- Precision = **3/3 = 1.000000**, Wilson 95% CI **[0.438503, 1.000000]**.
- FPR = **0/22 = 0.000000**, Wilson 95% CI **[0, 0.148655]**.
- Image uncertain/incomplete = **51/60 = 0.850000**.
- Required-target schema coverage = **60/60 = 1.000000**.
- Gate-queue image false alarms = **0/6**; no false alarm was observed in these six pilot images.

### Detector and protocol diagnostics

- Raw detector rows: **259**.
- Retained deduplicated targets: **252**.
- Fixed dedup suppressions: **7**.
- Reviewed detector false detections/non-vehicle fragments: **12/252**.
- Reviewed detector misses: **0/240**; this is cache-path pilot coverage only, not new-image detector accuracy.
- R0: **108** physical requests, **107/108** HTTP/schema-clean, **1/108** HTTP 500, schema-complete images **59/60**.
- R1: **108** physical requests, **108/108** HTTP/schema-clean, schema-complete images **60/60**.
- Total formal candidate requests: **216**. Total including two protocol smoke calls: **218**. Transport retries: **0**. Maximum client concurrency: **2**.

### Latency and cost

R1 is the final candidate timing. Local preprocess is from the historical cache-to-input preparation path; detector latency is not counted as a new end-to-end detector measurement.

- Request client elapsed P50/P95: **17.545 / 19.445 s**.
- Ollama reported total P50/P95: **17.540 / 19.437 s**.
- Ollama reported model load-duration P50/P95: **0.461 / 0.516 s**.
- Local context/composite preprocess P50/P95: **0.0375 / 0.0515 s per image**.
- Client scheduling queue wait P50/P95: **458.202 / 882.297 s** because all bounded futures were submitted to the two-worker executor; this is not a production server queue SLA.
- Requests per image P50/P95: **2 / 4**.
- No production realtime SLA was supplied or claimed.

## 4. Gate decision

R1 fails the pilot-entry gates:

- Road recall required `>=0.75`, observed **2/14 = 0.142857**.
- Two-bay recall required `>=0.75`, observed **0/18 = 0**.
- Ordinary, line/minor/nose-tail, gate, and primary image FPR were below their numeric thresholds in this pilot, but that cannot compensate for recall failure.
- Decisive coverage required `>=0.80`, observed **141/227 = 0.621145**.
- R1 schema coverage met **60/60**, but this is protocol completeness, not visual correctness.

No DEV expansion was executed because the only allowed candidate after R1 did not pass. No third candidate, prompt sweep, model replacement, ROI engine, or old validation/holdout access was performed.

## 5. Required final flags

```text
BUSINESS_DEFINITION=v3.0_user_confirmed
ALGORITHM_REVISION=V4_DYNAMIC_CONTEXT_VLM
SOURCE_TYPE=AIGC
REFERENCE_BASIS=AI_VISUAL_REVIEWED_PROVISIONAL
HUMAN_GOLD=false
PILOT_IMAGE_COUNT=60
DEV_IMAGE_COUNT=238
RAW_DETECTION_ROWS=259
UNIQUE_REVIEWED_VEHICLES=240
EXECUTED_CANDIDATES=2
PHYSICAL_MODEL_REQUESTS=218
MAX_CLIENT_CONCURRENCY=2
CURRENT_DEVELOPMENT_CANDIDATE=NONE
V4_INDEPENDENT_VALIDATION=NOT_EXECUTED
REAL_ROBOT_VALIDATION=NOT_EXECUTED
OLD_V2_VAL_HOLDOUT_CONSUMED=false
PRODUCTION_INTEGRATION_READY=false
```

## 6. Final conclusion and next steps

**Conclusion:** `NO_QUALIFIED_CANDIDATE`. The fixed pilot was fully executed for R0 and the one evidence-driven R1. Integrity audits passed and raw evidence is complete, but Qwen3.5:4b failed the required positive-recall and coverage gates. The evidence points primarily to persistent spatial relation/target interpretation failures, not to missing detector cache coverage or an incomplete request protocol.

Next steps, in evidence order:

1. Obtain a small independent real fixed-camera parking set with stable camera/route metadata and independently human-reviewed road, two-bay, minor-overrun, gate, and uncertain labels; do not reuse this AIGC pilot as V4 validation.
2. If a VLM route is still required, first test a stronger spatially grounded model or detector/geometry evidence path under a separately authorized experiment; do not continue Qwen prompt/crop sweeps on the consumed pilot.
3. Before any production consideration, validate new-image detector coverage, camera/ROI/BEV calibration, end-to-end latency, and robot alert behavior; production integration remains prohibited.
