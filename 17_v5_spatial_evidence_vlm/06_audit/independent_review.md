# Independent read-only review

Date: 2026-09-10. Reviewer: separately delegated agent Lovelace (not the implementation author). No model/network calls, no writes, no forbidden image/label access by reviewer.

## Pass 1 — independently checked
- 60 unique allowlist image IDs/paths/hashes, manifest equality, DEV membership and exclusion of non-DEV IDs.
- 3 copied reference files byte-identical to V4 and matched freeze; 60 image and 240 instance references.
- 60 raw image outputs, 196 raw detections, 1 suppression, 195 kept detections, 60 log rows; raw/kept linkage consistent.
- All 195 mask polygons finite and within original 1920x1080 bounds; area independently recomputed within 0.1 of stored values.
- All 195 ground polygons null and unvalidated. Footprint gate fails, despite numeric mask success.
- 876 of 1005 protected source/doc hashes independently rechecked; no changes. Coordinator's separate automated audit later rechecked all 1005.
- Individual overlays IMG_007529/IMG_007702 confirm vehicles despite zero detections; IMG_007672 confirms body silhouette is not ground footprint.

Findings: explicit P0 rejection was missing; prepare could overwrite its initial baseline and create self-hash on rerun. Both repaired without rerunning models. Full alignment, source-image byte hashing and all missed vehicles were not personally reviewed by this reviewer in pass 1; coordinator's audit rehashes only 60 allowed source images.

## Pass 2 — independently checked
- Independently recomputed complete greedy one-to-one IoU matching: 155/240, with 85 unmatched reference and 40 unmatched new targets; all stored associations agree.
- Current gate returns rejection with 0/195 validated ground contact.
- Found unsafe validated flag + mask fallback that could generate positive; wrong-image ROI could also be used. Added explicit actual ground polygon/source and image ID/hash/size/status binding plus regression cases.
- Found future PASS gate trusted status declarations and stale review without artifact binding. Current gate now explicitly has NO promotion authority and always rejects; a full future authorized gate is deliberately NOT implemented or claimed.
- Found raw empty detections could be ignored. Added detector completeness flag, default uncertain for empty detection, explicit confirmed absence permits ignore.
- Found detector_miss.count=85 and duplicate count=1 mixed candidates/algorithmic suppression with confirmed errors. Counts are now null, with separately named candidate/suppression fields. Mask-match numerator now checks matched mask status.

## Remaining limits
This is scoped integrity and code review, not independent validation of a parking classifier. There is no pixel-level mask/ground truth, calibrated pilot ROI, complete target review, production-grade artifact-bound promotion gate, or VLM dispatcher. Runtime network prevention is a Python guard, not OS/network isolation. Initial segmentation runner is a one-run offline probe, not a hardened resumable production service; future reuse requires stronger input-contract verification and atomic output handling. Posthoc metrics are explicitly a fixed P0 snapshot, not a reusable end-to-end evaluator.

## Final confirmation
Reviewer independently reran 19 rule tests and 6 contract tests with bytecode disabled: 25/25 passed. Confirmed all listed targeted fixes and continued rejection-only state. Final conclusion: blocked fixed-snapshot P0 diagnostic may be closed, but complete V5/production acceptance has not been achieved. The five visual observations combine three coordinator observations with two auditor observations; they are not five independently reviewed, reference-matched misses. Internal synthetic rule functions are not an authenticated production trust boundary.
