# PARKSCOPE_LEARNED_RELATION_HEAD_P3_OOF Protocol

Frozen on 2026-09-16 before supervised training.

## Purpose

Test whether frozen ParkScope segmentation masks contain a learnable frame-level parking-relation signal using one preregistered tiny MIL CNN. This is development OOF feasibility, not parking production validation.

## Data and seal

- Frozen v2.2 DEV GT SHA256: `413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56`.
- Frozen CAL/EVAL split SHA256: `bf8d5ba02dc0a2c5a0f1384ca0dfacd9afe3dcdbd440c7775b9cdd943d68b332`.
- 30 sealed EVALUATION media IDs are exclusion-only. Their GT, subgroup, images, ParkScope outputs, rasters, and predictions are not used.
- Exclude 24 uncertain and 18 gate-secondary frames. Primary pool is 166 frames: 47 positive and 119 negative.
- Supervision is frame-level only. No target-level pseudo-labels are created.

## Frozen perception and raster

- ParkScope upstream commit `fbcfac7be597dd263570bbcd0377096c8a43d146`.
- Checkpoint SHA256 `6d70bf088b7c324401afb97e09cf898afcc639d8ac837f4da7ef4afbc38d3d9b`.
- P0 prediction records are reused only for nonsealed primary media; remaining primary media use the exact default P0 CPU call.
- Target selection is reused exactly from matching v2.2 R0/R1 historical bbox artifacts.
- Relation raster is fixed float32 `4x96x96`; details are in `relation_raster_spec.json`.

## OOF model

- `TINY_MIL_CNN_V1`, 4,313 parameters.
- Frame logit is max over valid target logits.
- 5-fold StratifiedGroupKFold with authorized `media_id` fallback, seed 20260916.
- Adam, lr 0.001, weight decay 0.0001, 100 epochs, frame batch 8, fold-local pos_weight, CPU deterministic training.
- No augmentation, early stopping, architecture search, seed sweep, handcrafted P1 features, RGB, Ollama, or VLM.

## Threshold and stop rules

All OOF scores must be frozen before selection on the fixed 19-point grid 0.05..0.95. Safe thresholds require Precision >=0.85 and FPR <=0.10. The winner and OOF gate are selected exactly as specified in `threshold_protocol.json`. No sealed EVALUATION is opened in this phase, including after PASS.
