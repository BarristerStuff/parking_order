# parking_order v2.0 Step 2 DEV-only stronger VLM baseline

STAGE=V2_STEP2_STRONGER_VLM_DEV_BASELINE
PILOT_OR_DEV=DEV_BASELINE_DIAGNOSTIC
SOURCE_TYPE=AIGC
GT_BASIS=group_intent_v2.0_with_p05_visual_adjudication
PRODUCTION_CLAIM=NOT_AUTHORIZED
TP=24
FP=39
TN=106
FN=27
RECALL=0.47058823529411764
FPR=0.2689655172413793
P01_RECALL=0.17391304347826086
P03_RECALL=0.7222222222222222
P04_FPR=0.2857142857142857
P05_RECALL=0.7
P05_FPR=0.0
P06_FPR=0.5
HN01_FPR=0.1111111111111111
P50=2.2806145
P95=6.245387
OLLAMA_REQUESTS=338
GEOMETRY_ONLY_RECALL=N/A
VLM_ONLY_RECALL=0.47058823529411764
LOGICAL_JSON_SUCCESS_RATE=1.0
PHYSICAL_JSON_SCHEMA_SUCCESS_RATE=1.0
VAL_IMAGE_READS=0
HOLDOUT_IMAGE_READS=0

## Interpretation boundary

This is one DEV-only AIGC baseline using frozen v2 GT and a single frozen
five-question perception prompt. It is neither Human Gold nor a production,
robot-camera, real-world, VAL, or HOLDOUT accuracy claim. The baseline does not
authorize a subsequent prompt or preprocessing change.

## Main metrics

- Primary binary TP/FP/TN/FN: 24/39/106/27
- Primary positive recall: 0.47058823529411764 with Wilson 95% interval [0.3405299020949959, 0.6047669578990353]
- Primary negative FPR: 0.2689655172413793 with Wilson 95% interval [0.20344255259370747, 0.3464140496536988]
- hn01 gate-queue secondary FPR: 0.1111111111111111 over n=18
- GT-uncertain excluded from primary confusion matrix: 24
- No eligible detector box: 1

## Requested subgroup focus

| Group | Correct metric | Value | Denominator |
|---|---|---:|---:|
| p01 | positive recall | 0.17391304347826086 | 23 |
| p03 | positive recall | 0.7222222222222222 | 18 |
| p04 | negative FPR | 0.2857142857142857 | 14 |
| p05 positive | positive recall | 0.7 | 10 |
| p05 negative | negative FPR | 0.0 | 2 |
| p06 | negative FPR | 0.5 | 6 |
| hn01 | secondary negative FPR | 0.1111111111111111 | 18 |

## Decision signal

Recommendation: CLOSE_SINGLE_RGB_PLAN__RETURN_TO_USER

- Definition-narrowing signal (p03 recall >=0.70 and p06 FPR <=0.10 while p01 recall <0.70 or p04 FPR >0.10): False
- Primary recall strictly greater than 0.70: False
- Primary FPR <=0.10 and p02 FPR <=0.20: False
- No automatic next step is authorized. Return to the user with this report before changing prompt, preprocessing, definition, GT, split, or data access.
