# V4 Dynamic Context VLM — `parking_order_violation`

**Candidate:** `V4_R0_GLOBAL_TARGET_CONTEXT` and one evidence-driven successor `V4_R1_GLOBAL_TARGET_CONTEXT_COMPOSITE`  
**Algorithm revision:** `V4_DYNAMIC_CONTEXT_VLM`  
**Business definition:** `v3.0_user_confirmed`  
**Source:** AIGC only; results are not real robot accuracy.

## Scope and independent judgment

This task was authorized as an AIGC development experiment because missing real parking-camera frames and ROI calibration limit production conclusions but do not block testing a new VLM input hypothesis. The old v2 semantics already contained road/outside-bay positives, substantive two-bay positives, minor-line/nose-tail negatives, and normal gate-queue negatives; V4 does not claim these rules are new. V4 tests whether global scene context plus complete vehicle context and explicit target identity is better than the old local ground-band/line approach.

The production project and old v2 VAL/HOLDOUT media were not modified or opened. The detector cache is historical DEV-only YOLO11n output; it is not a new-image detector validation.

## Frozen candidate contract

- Direct endpoint: `http://192.168.20.62:11434/api/generate`; model `qwen3.5:4b`.
- DEV-only allowlist is `contracts/dev_image_allowlist.csv`; forbidden VAL/HOLDOUT metadata is `contracts/forbidden_split_metadata.csv`.
- Pilot is fixed before formal requests in `contracts/pilot_manifest.csv`, seed `20260909`, 60 images.
- Raw car/bus/truck boxes are class-agnostically deduplicated at IoU `>0.80`; no height/top-K truncation. Every raw box has a stable raw ID and every retained box has a target ID.
- R0 sends one panorama plus up to three complete context crops as an Ollama `images` array. R1 sends one composite JPEG per batch (scene top, requested crops below in target-ID order), changing only the input protocol after R0 correspondence errors.
- Input images contain no media ID, group, split, GT, prediction, filename, or label hints. Local logs may retain metadata for audit.
- Deterministic decisions are in `evaluator/decision.py`; strict parsing rejects missing/duplicate/invalid target responses. `evaluator/metrics.py` reports alert metrics with uncertain/protocol outcomes retained in the alert denominator, plus clean semantic confusion and decisive coverage.

## Evidence boundary

Reference labels are `AI_VISUAL_REVIEWED_PROVISIONAL`, `HUMAN_GOLD=false`. They were reviewed from the original DEV pixels, numbered panorama, and complete context crops before formal requests. AIGC intent/group is not a substitute for pixel review. Small or occluded visible vehicles are preserved as uncertain; non-vehicle fragments are recorded as detector false detections. This is a development reference, not human double-reviewed Gold.

## Reproduction

```bash
python3 /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/tools/freeze_manifests.py
python3 /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/tools/prepare_inputs.py
python3 /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/tests/run_tests.py
python3 /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/inference/run_v4.py \
  --batches /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/inputs/pilot/request_batches.jsonl \
  --outdir /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/outputs/pilot_r0 \
  --max-workers 2 --timeout 240
python3 /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/tools/evaluate_run.py \
  --run /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/outputs/pilot_r0 \
  --inputs /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/inputs/pilot \
  --outdir /home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm/metrics/pilot_r0
```

The first command is only a reconstruction command for a fresh V4 directory; it must not be run after a freeze in an audit replay. R1 reproduction uses the frozen `inputs/pilot_r1/request_batches.jsonl` and `contracts/prompt_v4_r1.txt`.

## Current status

Final status is recorded in `EXECUTION_REPORT.md`. A passing pilot would have required both positive subtypes to meet their minimum supports and all alert/coverage/schema gates. No pilot result authorizes production integration, real-camera validation, robot validation, or use of VAL/HOLDOUT.
