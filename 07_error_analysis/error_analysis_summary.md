# parking_order_violation P0 error analysis

> Scope: DEV/`train` only. Synthetic generation-intent labels are unreviewed; this is not Human Gold or production accuracy evidence.

- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false
- Independent visual adjudication performed: **no**

## Confirmed facts

- Predictions: 239/239 parsed successfully; inference failures 0; parse failures 0.
- Output distribution: 0=231, 1=8, uncertain=0.
- Positive prediction rate: 3.3473%.
- Binary confusion: TP=5, FP=3, TN=117, FN=89.
- Precision=0.625000, Recall=0.053191, F1=0.098039, Accuracy=0.570093.
- Specificity=0.975000, FPR=0.025000, Balanced Accuracy=0.514096.
- p01 recall: 3/39 (7.6923%); p02 recall: 2/35 (5.7143%); p05 recall: 0/20 (0%).
- False positives: n02=2, hn04=1; all other DEV negative groups=0.
- All 25 GT-intent uncertain samples were predicted 0; model uncertain rate=0%.
- Always-negative binary baseline accuracy=0.560748; current delta=+0.009346 (2 net additional correct decisions / 214).

## Reasoned findings

1. **Dominant negative bias.** The model detects only 5/94 intent-positive rows while correctly rejecting 117/120 intent-negative rows.
2. **No uncertainty behavior.** A zero uncertain rate is not calibration success: the model also forces every intent-uncertain row to 0.
3. **Boundary/angle sensitivity drives FP.** All three FP explanations cite diagonal placement or crossing a painted boundary/travel lane.
4. **Multi-vehicle failure is systematic.** `p05-multi-vehicle-at-least-one-violation` recall is 0/20, consistent with difficulty locating a violating member in a full-frame scene after 448x336 preprocessing.
5. **Minimal gain over trivial baseline.** Five TP are offset by three FP, yielding only two net extra correct binary decisions compared with always predicting 0.

## Risks and unverified hypotheses

- The 89 intent-FN rows are **not proven visual false negatives**. Some generated images may have failed to realize the intended violation.
- Representative model explanations describe apparent compliance on many intent-positive rows. That is sufficient to prioritize human DEV review, but model self-explanation is not independent evidence.
- No numeric acceptance threshold was supplied, so no formal gate pass/fail is asserted. Recall/F1 are unsuitable for a recall-sensitive production use case, but production fitness cannot be inferred from this unreviewed synthetic DEV set.

## Existing queues

- `false_negatives.csv`: 89
- `false_positives.csv`: 3
- `hard_negative_false_positives.csv`: 1
- `gate_queue_false_positives.csv`: 0
- `model_uncertain.csv`: 0
- `parse_failures.csv`: 0
- `inference_failures.csv`: 0

## Next step within current boundary

Human-review the DEV mismatch and intent-uncertain queues before proposing any change. P1/P2/P3/P4 remain prohibited and were not run.
