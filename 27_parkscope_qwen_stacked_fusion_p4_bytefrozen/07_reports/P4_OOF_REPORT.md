# Byte-Frozen P3 Raster + Qwen Stacked P4 OOF Report

## Decision

- Final status: `P4_QWEN_STACKED_FUSION_OOF_FAIL`
- Safe threshold count: `1`
- Winner threshold: `0.85`
- Ready for new independent evaluation design: `false`
- Current development winner: `NONE`

## Frozen development evidence

- Frames: 166 (47 positive, 119 negative)
- OOF coverage: 1.000000
- P4 OOF score SHA256: `86f33885d7bb412221f1f2df3926bb102815e579679fe90a9338365de5cb528b`
- ROC-AUC: 0.721616
- PR-AUC: 0.575528
- Metrics: `{"FN": 44, "FP": 0, "TN": 119, "TP": 3, "coverage": 1.0, "f1": 0.12, "fpr": 0.0, "precision": 1.0, "recall": 0.06382978723404255}`
- P01 recall: `0.16666666666666666`
- P03 recall: `0.0`
- P05 recall: `0.0`
- Minor-crossing FPR: `0.0`

## Boundary

This is frozen development nested OOF evidence only. No independent EVAL, legacy quarantined evaluation, VAL, HOLDOUT, real-robot validation, or production integration was executed.
