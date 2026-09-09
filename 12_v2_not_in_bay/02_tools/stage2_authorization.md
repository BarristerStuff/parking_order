# v2 Step 2 DEV-baseline authorization record

Status: ACTIVE_FOR_ONE_DEV_ONLY_DIAGNOSTIC_BASELINE  
Recorded: 2026-09-08  
Authority: user instruction received after Step 1 checkpoint  

## Accepted frozen inputs

- v2.0 GT is frozen and must not be edited.
- p05 remains 17 positive / 3 negative globally.
- Fixed-seed v2 split is frozen and must not be edited.
- u03, u04, and u05 are scope=gt_uncertain and are explicitly exempt from the DEV >= 5 immediate-stop rule. This exemption does not apply to primary or secondary groups.

## Authorized diagnostic scope

The authorized work is one stronger VLM baseline on the complete v2 DEV partition only. It must:

- use only qwen3.5:4b through direct http://192.168.20.62:11434;
- use at most two concurrent Ollama requests;
- make no prompt variants, prompt sweeps, post-result prompt edits, or preprocessing sweeps;
- not access any v2 VAL or HOLDOUT image;
- write per-subgroup metrics and separately highlight p01, p03, p04, p05, p06, and hn01;
- keep all new code and artifacts inside 12_v2_not_in_bay;
- not alter any frozen P0/F0/F1/F2/P3 artifact or formal dataset/production/server/model file.

This user-authorized diagnostic baseline supersedes the execution brief's normal
Step-2-tools -> Step-4-pilot ordering only for this single DEV-wide diagnostic
run, because the requested all-subgroup result includes p04, p06, and hn01,
which the prescribed 60-item pilot does not cover. It is not a DEV winner,
does not authorize prompt/preprocessing optimization, and never authorizes VAL
or HOLDOUT access.

## Decision interpretation for the resulting report

- p01 and p03 are positive groups: report recall.
- p04, p06, and hn01 are negative groups: report FPR.
- p05 contains both labels after visual adjudication: report positive recall and negative FPR separately.
- If p03 recall and p06 FPR meet the inherited 0.70 / 0.10 gates while p01 recall or p04 FPR fails its corresponding gate, flag a definition-narrowing signal.
- Otherwise, if primary positive recall is strictly greater than 0.70, the next decision may consider prompt plus preprocessing optimization after a separate authorization.
- If primary positive recall is at most 0.70, flag the single-RGB plan for closure. No next action is automatic.

## Mandatory immediate stops

- Ollama unavailable or final logical JSON/schema success below 95%;
- detector cache/input hash mismatch;
- any non-exempt primary or secondary subgroup with DEV count below 5;
- AIGC intent mismatch above 10% discovered during the authorized review;
- any attempted VAL/HOLDOUT input.

