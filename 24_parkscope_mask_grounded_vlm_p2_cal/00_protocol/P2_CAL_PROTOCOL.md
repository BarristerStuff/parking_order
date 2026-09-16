# PARKSCOPE_MASK_GROUNDED_VLM_P2_CAL Protocol

## Objective and boundary

This one-shot calibration evaluates a fixed mask-grounded VLM relation architecture on the frozen 30-image CALIBRATION partition only. The 30-image EVALUATION partition and 10-image GATE_SECONDARY partition remain sealed. No FULL DEV, VAL, HOLDOUT, or old Holdout is executed.

ParkScope segmentation is reused from P0 without new inference. The inference stage reads a GT-free request manifest and cannot access event labels, group keys, strata, historical predictions, or EVAL data. CAL GT is joined only after all target predictions have been written and SHA-frozen.

## Frozen perception and target binding

- ParkScope upstream commit: `fbcfac7be597dd263570bbcd0377096c8a43d146`
- ParkScope checkpoint SHA256: `6d70bf088b7c324401afb97e09cf898afcc639d8ac837f4da7ef4afbc38d3d9b`
- Reuse P0 predictions and P0 selected-target binding exactly.
- Invalid anchors become `UNCERTAIN_ANCHOR` and receive no VLM request.
- Class IDs 1 and 2 are displayed only as parking-geometry candidates; no business class name is supplied to the model.

## Composite

Each valid target receives exactly one deterministic 1792x672 JPEG: 896x672 full raw context with a red target bbox and 896x672 fixed local relation view. The relation background is multiplied by 0.45. The frozen target mask is red, class 1/2 candidate masks are cyan, and other vehicles have gray outlines. Rendering and JPEG options are frozen in `overlay_config.json`; images remain local and untracked.

## Model request

The only endpoint is `http://192.168.20.62:11434/api/generate`, model `qwen3.5:4b`. The prompt, JSON schema, request options, timeout, retries, and concurrency are byte-frozen in this directory. One logical semantic request is made per valid target. Up to two identical technical retries are allowed. Two consecutive exhausted logical failures without an intervening schema success trigger a technical stop.

## Fusion

The model emits three independent fields. Python applies only `fusion_rule.json`. It does not use P1/P1.1 PCA, elongation, thickness, bracket, area-support, or outside-fallback rules. Frame fusion is positive if any target is positive, negative only if every target is negative, and uncertain otherwise.

## Evaluation

Strict CAL confusion treats uncertain positive frames as FN and uncertain negative frames as non-FP but not explicit TN. The preregistered business gate is frozen in `preregistration.json`. All gate clauses must pass. A PASS only authorizes a later P2 EVAL; it does not execute EVAL or establish a development winner.

The source instruction described `MASK_GROUNDED_INBAY_DISCRIMINATION_WEAK` qualitatively. Before requests, this protocol fixes it as: negative-target `one_marked_bay=YES` rate minus positive-target rate is less than 0.20. This diagnostic does not affect the CAL gate.
