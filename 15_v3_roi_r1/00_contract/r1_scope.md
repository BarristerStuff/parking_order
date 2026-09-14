# R1 Scope Contract

## Confirmed Baseline

- `14_v3_parked_on_road/` is the accepted scaffold/audit baseline, not a validated algorithm.
- v3 business logic remains: road/aisle parking and clear two-adjacent-bay occupancy are positive; line touch, minor overrun, nose/tail overhang, and gate queue are negative; uncertainty is non-alert.
- Old v2 VAL/HOLDOUT media remain sealed for this work.

## R1 Work

1. Build a new ROI engine under `15_v3_roi_r1/01_roi_engine/`.
2. Require explicit coordinate spaces and prevent image/BEV overlap mixing.
3. Implement image-to-BEV homography only when a valid matrix is supplied.
4. Validate polygons before geometry operations.
5. Generate real data inventory and block real ROI evaluation if camera/route inputs are absent.

## Non-Goals

- No Qwen prompt/crop sweep.
- No SpatioLM.
- No v2 GT/split/prompt/metrics edits.
- No production `vlm` edits.
- No Winner or production integration.
