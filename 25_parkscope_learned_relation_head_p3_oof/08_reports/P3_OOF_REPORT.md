# ParkScope Learned Relation Head P3 OOF Report

## Decision

- Final status: `P3_LEARNED_RELATION_HEAD_NO_SAFE_THRESHOLD`
- Safe threshold count: `0`
- P3 OOF gate pass: `false`
- Ready for sealed EVALUATION: `false`
- Sealed EVALUATION executed: `false`

## Frozen OOF evidence

- Primary/OOF frames: 166
- Scorable/unscorable: 166/0
- Coverage: 1.000000
- OOF score SHA256: `a30f4f7d2861a7a8a2b008f7cd469da09406ddf0735a995b2b962bce11e5e68e`
- ROC-AUC (diagnostic): 0.616485
- PR-AUC (diagnostic): 0.379381

The fixed 19-threshold grid contained no threshold satisfying both Precision >= 0.85 and FPR <= 0.10. Therefore no winner threshold exists and TP/FP/TN/FN, winner-based subgroup metrics, bootstrap confidence intervals, and fold threshold metrics are correctly reported as N/A rather than computed at an unauthorized fallback threshold.

## Boundary

This is frozen synthetic-development OOF feasibility only. No sealed EVALUATION image, GT, ParkScope output, raster, or learned-head prediction was used. No Ollama request was made. No second architecture, threshold, seed, or training run is permitted.
