# ParkScope Mask-Grounded VLM P2 CAL Report

## Boundary

CALIBRATION only: 30 images, 42 frozen selected targets. EVALUATION and GATE_SECONDARY remained sealed. ParkScope inference was not rerun.

## Result

- FINAL_STATUS: `PARKSCOPE_MASK_GROUNDED_VLM_P2_CAL_FAIL`
- TP / FP / TN explicit / FN strict: `0 / 0 / 15 / 15`
- Precision: `0.000000`
- Strict recall: `0.000000`
- F1: `0.000000`
- FPR: `0.000000`
- Uncertain: `0/30` (`0.000000`)
- Decision coverage: `1.000000`
- P01 recall: `0/5 = 0.000000`
- P03 recall: `0/5 = 0.000000`
- Minor-crossing FPR: `0/2 = 0.000000`
- Protocol success: `1.000000`

## Gate

```json
{
  "fpr_lte_0_10_and_fp_lte_1": true,
  "minor_crossing_fpr_lte_0_10": true,
  "p01_recall_gte_0_60_and_tp_gte_3": false,
  "p03_recall_gte_0_60_and_tp_gte_3": false,
  "precision_gte_0_90": false,
  "protocol_success_eq_1": true,
  "strict_recall_gte_0_70_and_tp_gte_11": false,
  "uncertain_rate_lte_0_30_and_count_lte_9": true
}
```

## Diagnostics

- Field distributions: `{"clearly_outside_marked_bay": {"NO": 42, "UNCERTAIN": 0, "YES": 0}, "one_marked_bay": {"NO": 0, "UNCERTAIN": 0, "YES": 42}, "separator_through_vehicle": {"NO": 42, "UNCERTAIN": 0, "YES": 0}}`
- Target decisions: `{"NEGATIVE": 42}`
- MULTIBAY_COLLAPSE: `true`
- OUTSIDE_COLLAPSE: `true`
- INBAY_DISCRIMINATION_WEAK: `true`

The in-bay diagnostic threshold was preregistered because the source instruction described this flag qualitatively; it does not affect the CAL gate.

## Provenance and execution accounting

- Protocol freeze commit: `c284cd16d77b559b848ad963d9ee8abf273fa534`
- ParkScope new requests: `0`
- Model logical requests / physical attempts / schema successes / timeouts: `42 / 42 / 42 / 0`
- Target prediction SHA256: `e15e02cb84915eb6104977e42c097537ce66b128191abddc3ed95236196b5393`
