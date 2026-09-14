# 14_v3_parked_on_road

This revision starts the v3 development line for `parking_order_violation` under the revised business definition: detect vehicles parked in a driving road/aisle, or vehicles clearly occupying two parking bays. It does **not** continue the frozen v2 definition, prompt sweeps, SpatioLM route, or production integration work.

## Scope

- Event working name: `vehicle_parked_on_road_v3`.
- Source data allowed in this revision: old v2 `DEV` split only, used as AIGC prototype input.
- Production project `/home/yanbo/net_vlm_yanboversion/vlm` is read-only for this revision.
- Old v2 GT, split, prompts, predictions, metrics, and closure artifacts are frozen inputs and must not be modified.
- Old v2 `VAL` and `HOLDOUT` media must not be opened or consumed.

## Current Status

- `V3_LABEL_COVERAGE=partial`
- `PRODUCTION_CLAIM=NOT_AUTHORIZED`
- `PRODUCTION_INTEGRATION_READY=false`
- `REAL_ROBOT_VALIDATION=NOT_EXECUTED`
- `AIGC_RESULTS_ARE_NOT_PRODUCTION_ACCURACY`
- `OLD_V2_VAL_HOLDOUT_CONSUMED=false`

## Artifacts

- `00_definition/vehicle_parked_on_road_v3.0.md` defines v3 labels and image-level aggregation.
- `01_v3_gt_overlay/v3_dev_vehicle_labels.csv` contains DEV detection rows with explicit review status.
- `01_v3_gt_overlay/v3_dev_image_labels.csv` contains DEV image-level labels with explicit review status.
- `02_roi_config/roi_schema.json` defines the fixed-camera ROI configuration contract.
- `02_roi_config/example_route_roi.json` is a synthetic `PROTOTYPE_ONLY` example, not a production ROI.
- `04_roi_rule/roi_rule.py` implements a pure-function ROI rule engine.
- `04_roi_rule/test_roi_rule.py` verifies core rule behavior on synthetic fixtures.
- `05_dev_eval/metrics.json` and `05_dev_eval/report.md` document why DEV metrics are not production evidence.
- `06_audit/` contains manifests, hashes, validation, and blocking records.

## Key Boundary

The old DEV images are AIGC and are not a fixed real camera route with verified calibration. Therefore this revision can validate schema/rule mechanics and labeling workflow, but cannot prove production accuracy or authorize integration.
