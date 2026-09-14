# ADR V5-001 — Spatial evidence before semantic verification

Date: 2026-09-10. Status: Accepted for diagnostic code; P0 blocked, no candidate.

## Decision
Use the existing local YOLOE-26m-seg checkpoint and its matching MobileCLIP2 encoder read-only, CPU, one sequential run on 60 frozen V4 DEV images. Do not change production gate code. Keep reference physically separate from prediction. Fresh Sxxx targets are not old Txx targets; posthoc one-to-one bbox association is evaluator-only.

Visible-body silhouette, bbox bottom-20%-rectangle and validated ground-contact polygon are separate concepts. This run generates the first two, not the third. Neither is authorized to generate positives without ground-contact validation. No fabricated homography or GT-conditioned ROI.

P0 failure closes downstream pilot rules and VLM. `06_audit/check_p0_gate.py` returns exit 2 for this run. Abstract image-raster geometry tests may still run, but are never classification measurements on the pilot. BEV input is rejected rather than silently mixed with image coordinates. Missing overlap remains null, not zero. ROI union uses Boolean raster union; bay adjacency is explicit.

## Rationale and alternatives
Raw RGB V4 R0/R1 did not produce a qualified candidate. A fresh segmentation probe can expose detector/geometry limitations without spending Qwen requests. Auto-drawing ROI after seeing reference would create circular evidence, so not selected. New AIGC generation is postponed because P0 is blocked on already-permitted fixed images, not because a generator was proven unavailable. No additional checkpoint, class-list or threshold sweep is performed.

The rules accept externally validated context for gate queue and boundary direction. A ratio alone cannot distinguish nose/tail overhang from side overrun. Queue overlap alone cannot prove a *normal* queue.

## Maintenance limits
Image rasterization is diagnostic, resolution-sensitive and not metric BEV. The current implementation prefers false abstention for missing context. Existing segmentation runtime is borrowed read-only from another local experiment; recorded file/version/weight hashes are needed for reproduction. Any future ground-contact method, calibration bundle or runtime change requires a new frozen run directory/contract, not overwriting this probe.

## Audit-driven hardening after the probe
Added explicit P0 gate; made preparation refuse existing baseline/freeze; excluded freeze self-reference. These changes were not followed by a model rerun and are not described as pre-inference changes. Posthoc evaluator IoU=0.50 is diagnostic, not a pre-registered classifier threshold. Initial raw inference outputs remain untouched.

Final audit hardening: validated status cannot transfer through a visible-mask fallback. ROI identity/hash/size are checked. Empty detections require explicit detector completeness to produce ignore. The current gate is rejection-only and has no promotion authority; future PASS needs a separately reviewed, artifact-bound gate and downstream dispatcher. No VLM dispatcher exists in this blocked run.
