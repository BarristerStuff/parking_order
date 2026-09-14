# 15_v3_roi_r1

R1 continues the `vehicle_parked_on_road_v3` ROI route after the accepted scaffold in `14_v3_parked_on_road/`.

This revision fixes coordinate-space handling and geometry validation in a new independent directory. It does not modify the v2 frozen files, the `14_v3` scaffold, production `vlm`, or old VAL/HOLDOUT media.

## Status

- R1_CODE_AND_TESTS_ACCEPTED: pending final audit
- R1_REAL_ROI_EVALUATION: false unless real camera inventory proves otherwise
- REAL_ROBOT_VALIDATION: NOT_EXECUTED
- PRODUCTION_INTEGRATION_READY: false

## Scope

- Implement explicit `image`/`bev` coordinate-space handling.
- Implement homography image-to-BEV conversion path.
- Reject or safely fail unsupported polygons.
- Avoid duplicate overlap from overlapping ROI polygons by union-area calculation.
- Inventory real parking camera/robot data without using old v2 VAL/HOLDOUT.
- Keep all results non-production until real ROI, labels, and robot validation exist.
