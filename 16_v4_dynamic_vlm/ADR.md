# ADR: V4 dynamic context input route

- **Date:** 2026-09-09
- **Status:** Accepted for AIGC development experiment only
- **Decision:** Reuse the frozen DEV detector cache, deduplicate cross-class duplicate boxes with fixed class-agnostic IoU `>0.80`, and send the complete scene plus full vehicle context to `qwen3.5:4b` in batches of at most three targets. After R0 showed systematic target-correspondence and spatial-relation errors, allow exactly one R1 that changes only the transport image representation to one composite JPEG with an explicitly ordered scene/crop layout.

## Context

The old v2 ground-band route already attempted local line-sensitive inputs and failed its development gates. V4 therefore tests a distinct context hypothesis without fixed camera ROI, invented geometry, or model replacement. Real parking-camera evidence is absent, so this is an AIGC development route only.

## Consequences

Positive: scene context, full vehicle extent, and nearby ground are available without synthetic bay lines or GT leakage; detector duplicates and all target batches are traceable. Negative: one composite may still be ambiguous to a small VLM; multiple targets increase request cost and correspondence risk; old cache means arbitrary new-image detection is not validated; provisional AIGC visual review and small support limit conclusions. The route remains outside production until an independent real-camera validation passes.
