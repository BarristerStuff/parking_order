# V2.2_MARKED_BAY_REQUIRED_FAST_CLOSE execution report

Date: 2026-09-16 (Asia/Shanghai)

## Verified facts

- Repository: `/home/yanbo/net_vlm_parking_optimization`.
- Pre-change `main` was clean and `HEAD == origin/main == 9ae06828441e49b502f9c050acd084bbf9f3cbfd`.
- Required v2.1.1 commit `7b31daa24f95cf4b666fbe7ecb423e95bf42a815` is an ancestor.
- Existing numeric directories reached `18_*`; therefore the new revision is `19_v2_2_marked_bay_required`, not `14_*`.
- The v2.1.1 pipeline remains untouched. Q3 bytes are identical (SHA256 `5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc`).
- No v2.2 180-image challenge images were present at the start of this task.

## Implemented

- Frozen v2.2 definition.
- Forked pipeline under `02_pipeline/`.
- Changed only Q1 semantic prompt and the direct Q1/Q3 fusion/request condition; YOLO, selection, View A, Q3, Ollama settings and checkpoint remain copied/frozen.
- Added complete Q1/Q3 truth-table and frame-priority tests; bundled Python unittest: 2 tests passed.
- Added legacy DEV shadow GT migration. High-confidence groups are mapped; p02/p04/p05/p06 and all uncertain groups remain explicitly `needs_human_review`; formal labels were not modified.
- Added the required 180-row collection plan and complete prompt/provenance manifest. It is plan-only and contains no images.

## Stop state

`FINAL_STATUS=V2_2_SCAFFOLD_READY_GT_REVIEW_REQUIRED`

This status records scaffold readiness only: R0 was **not** executed because the required p02/p04/p05/p06 legacy DEV visual review is unresolved. The DEV review and R0 may proceed without waiting for the separate fresh challenge set. No old VAL or HOLDOUT was run or reinterpreted. No production project, MQTT, robot, TTS, alerting, shadow canary, or SSH tunnel was touched.

## Required gates not yet evidenced

`READY_FOR_R0=false`; `R0_EXECUTED=false`; `DEV_CHAMPION=NONE`; `NEW_CHALLENGE_IMAGES_AVAILABLE=false`; `NEW_CHALLENGE_TOTAL=0`; `VAL_EXECUTED=false`; `HOLDOUT_EXECUTED=false`; `OFFLINE_SUBMISSION_READY=false`; `REAL_ROBOT_VALIDATED=false`; `PRODUCTION_READY=false`.
