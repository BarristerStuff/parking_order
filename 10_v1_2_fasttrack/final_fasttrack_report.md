# parking_order_violation V1.2 Fast-Track final report

Report date: 2026-09-07

## Machine-readable final status

```text
FINAL_STATUS=STOPPED_VLM_ONLY_FASTTRACK_INSUFFICIENT

F0_ALREADY_EXISTED=true
F0_RERUN=false

F0_PRECISION=1.0
F0_RECALL=0.01694915254237288
F0_F1=0.03333333333333333
F0_P01_RECALL=0.02564102564102564
F0_P05_RECALL=0.0
F0_P95=5.6898014

F1_EXECUTED=true
F1_PRECISION=null
F1_RECALL=0.0
F1_F1=null
F1_P01_RECALL=0.0
F1_P05_RECALL=0.0
F1_P95=6.6986953

F2_EXECUTED=true
F2_CONTEXT_METHOD=detector_guided
F2_PRECISION=0.0
F2_RECALL=0.0
F2_F1=null
F2_P01_RECALL=0.0
F2_P05_RECALL=0.0
F2_P95=24.077925

WINNER=V12_F0_448_DIRECT
WINNER_DEV_GATE_PASSED=false

VLM_ONLY_FASTTRACK_INSUFFICIENT=true

VAL_EXECUTED=false
VAL_PRECISION=not_applicable
VAL_RECALL=not_applicable
VAL_F1=not_applicable

READY_FOR_VAL=false
READY_FOR_P4=false

VAL_CONSUMED=false
HOLDOUT_CONSUMED=false

PROJECT_CODE_MODIFIED=false
SERVER_FILES_MODIFIED=false
SSH_USED=false
```

`null` above preserves the analyzer result rather than inventing a value. F1 never
predicted positive, so Precision and F1 are undefined. F2 has Precision=0 and
Recall=0; its harmonic-mean denominator is zero, so the analyzer reports F1 as
`null`.

## Confirmed facts

### Frozen inputs and F0 recovery

- The v1.2 definition SHA-256 is
  `64a3f3e73a31e97b1468827be24b1cdfbb713d531e76a60b6b36cfde8623cc67`,
  matching the recorded hash.
- The frozen prompt SHA-256 is
  `a6ae853aad36ed5e0ecf3856761b7ae34d0cf6933218ad68f3901dfa7cf1458d`,
  matching the recorded hash.
- F0 already contained 239 unique predictions and a completed run summary before
  this recovery run. F0 was not rerun.
- F0 config, manifest, predictions, and prompt hashes were checked before and
  after analysis and remained unchanged.
- The shadow DEV evaluation contains 179 primary binary samples, 25 GT-uncertain
  samples, and 35 p02 boundary-challenge samples. The p02 samples remain excluded
  from TP/FP/TN/FN.
- All three candidates used the same frozen 239-row manifest and frozen prompt.
- All F0, F1, and F2 logical results completed with 239/239 protocol successes;
  HTTP, JSON/schema, and semantic protocol success were 100%.

### Candidate comparison

| Candidate | TP/FP/TN/FN | Precision | Recall | F1 | p01 recall | p05 recall | Hard-negative FPR | Gate-queue FPR | P95 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V12_F0_448_DIRECT | 1/0/120/58 | 1.0 | 0.016949 | 0.033333 | 0.025641 | 0.0 | 0.0 | 0.0 | 5.689801 s |
| V12_F1_896_LETTERBOX | 0/0/120/59 | undefined | 0.0 | undefined | 0.0 | 0.0 | 0.0 | 0.0 | 6.698695 s |
| V12_F2_896_CONTEXT | 0/5/115/59 | 0.0 | 0.0 | undefined | 0.0 | 0.0 | 0.06 | 0.10 | 24.077925 s |

F1 used the required transformation:

```text
1920x1080 source
-> proportional resize to 896x504
-> 896x672 black canvas with 84 px top and bottom padding
-> JPEG Q70
```

It did not stretch 1920x1080 directly to 896x672. Relative to F0, F1 lost the
only true positive, reduced Recall from 1/59 to 0/59, reduced p01 recall from
1/39 to 0/39, left p05 recall at 0/20, and increased P95 latency by 1.008894 s
(17.7%).

F2 used the local, hash-verified YOLO11n checkpoint through the existing local
detector environment. Detection was restricted to `car`, `bus`, and `truck`.
Each logical sample contained the full letterboxed view plus up to three
1.75x-expanded vehicle-context crops. It made 846 physical VLM requests: 239
full views and 607 context views, or 3.54 views per logical sample on average.

F2 did not recover a single positive GT sample. For p01 it changed 18/39 results
from negative-like behavior to uncertain but produced 0 positives. For p05 all
20/20 samples remained negative. It also introduced five false positives:

- Three gate-queue samples were upgraded by context crops to `severe_angle`,
  giving gate-queue FPR=3/30=0.10.
- One standard-inside-bay sample was upgraded to `severe_angle`.
- One close-to-line-but-inside sample was upgraded to `outside_space`.

All five final positives came from context crops rather than the full view. This
shows that the frozen positive-OR fusion rule can amplify crop-induced loss of
scene context even when protocol/schema execution is perfect.

### Required output artifacts

F1 and F2 each contain non-empty:

```text
predictions.jsonl
run_summary.json
metrics.json
subgroup_metrics.csv
errors.csv
latency.json
report.md
```

### Dataset and safety audit

- Formal dataset validation command completed with `status=valid` and
  `error_count=0`.
- The validator also reported 687 non-blocking warnings, primarily existing
  `splits.csv` group/scenario naming mismatches. These are maintenance debt, not
  validation errors, and were not changed in this task.
- The formal project `/home/yanbo/net_vlm_yanboversion/vlm` contained 1,636 files.
  Its complete file-content tree hash was identical before and after the work:
  `e7cb1ef92f1af22b4333a7a9e53f3a95c3c56bc1971d51f8dd53fcf221263846`.
- No formal dataset labels were migrated or edited.
- No formal project files were edited.
- No Git commit was created.
- No SSH command or connection was used.
- Ollama was accessed only through HTTP at the configured endpoint. Only model
  listing and inference endpoints were used; no server-management or file-write
  operation was performed.
- No VAL or HOLDOUT data was accessed by the Fast-Track runners.

## Decision reasoning

F0 is the unique DEV winner because it is the only candidate with any true
positive and has no false positives. It nevertheless fails the minimum stopping
criteria by a very large margin: Recall=0.016949 and p01 recall=0.025641, both
below 0.70 and far below the DEV gate thresholds of 0.85.

F1 rejects the input-information hypothesis for simple higher-resolution
letterboxing: more pixels and preserved aspect ratio did not improve the target
signal. F2 rejects detector-guided context crops as a sufficient VLM-only fix:
it did not improve Recall or p05 and materially worsened latency, uncertainty,
hard-negative FPR, and gate-queue FPR.

Therefore:

```text
VLM_ONLY_FASTTRACK_INSUFFICIENT=true
READY_FOR_VAL=false
READY_FOR_P4=false
```

VAL was not run because no DEV candidate passed the frozen gate. HOLDOUT remains
untouched.

## Direct answers

1. **Did proportional 896x672 input significantly improve clear-violation Recall?**
   No. Recall fell from 1/59 (0.016949) in F0 to 0/59 in F1, and p01 fell from
   1/39 to 0/39. P95 latency increased by 17.7%.

2. **Did context input significantly improve p05 multi-vehicle scenes?**
   No. p05 remained 0/20. F2 added 607 model requests, increased logical P95 to
   24.077925 s, and introduced five false positives, including three gate-queue
   false positives.

3. **Is the qwen3.5:4b single-VLM route worth continuing in this Fast-Track?**
   No. The tested prompt, higher-resolution full image, and detector-guided
   context variants all failed the central Recall requirement. Further prompt
   candidates or repeated DEV tuning would consume evaluation evidence without
   addressing the observed geometry/context failure mode.

4. **Is P3-lite needed?**
   Yes. The next rational architecture is:

   ```text
   vehicle detector
   + vehicle-context crop
   + parking-space/parking-line/traffic-area geometry evidence
   + full-scene-aware VLM verifier
   ```

   Detector crops alone are insufficient. P3-lite should explicitly retain or
   reconstruct parking-space and traffic-area geometry and should not use an
   unconditional crop-positive OR without a full-scene/gate-queue consistency
   check.

5. **Can the task enter VAL or P4 now?**
   No. `READY_FOR_VAL=false`; therefore VAL was not consumed. P4 is also not
   ready and HOLDOUT remains unconsumed.

## Scope and remaining risks

- The current GT is unreviewed generation-intent shadow GT, not per-image Human
  Gold. The Fast-Track conclusion is strong for rejecting these three candidates
  on the frozen DEV proxy, but it is not a production-accuracy claim.
- The formal dataset's 687 warnings should be triaged separately. Fixing them is
  outside this Fast-Track and could change dataset metadata, so no corrective
  edit was made here.
- A future P3-lite evaluation should define its geometry evidence and crop/full
  fusion before consuming more DEV, and should preserve the same VAL/HOLDOUT
  discipline.
