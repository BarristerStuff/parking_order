# P0 STOP — V5_BLOCKED_FOOTPRINT

2026-09-10. Segmentation inference worked, but ground_contact_polygon_image is null for all 195 detections. Verified physical footprint coverage is 0/195 (0/240 relative to prior reviewed instances), below the 0.60 gate. Full target/pixel alignment has not been verified. Mask numerical validity is not a physical footprint test.

A second blocker is missing pilot road/bay/gate ROI and adjacency. No GT-informed pilot geometry was invented. Downstream pilot rules, VLM smoke, /api/tags, prompt/request freeze, comparison and candidate evaluation are NOT_EXECUTED. This is a deliberate stop, not an API connectivity failure or classifier failure score.

Code-only image geometry and fail-closed tests have been executed. Scope-bounded integrity audit passed, which does not mean capability passed.
