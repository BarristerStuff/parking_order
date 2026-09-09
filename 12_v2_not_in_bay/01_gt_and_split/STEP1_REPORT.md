# parking_order v2.0 — Step 1 checkpoint report

Status: STEP1_COMPLETE__CHECKPOINT_1_REQUIRED__CHECKPOINT_4_ALERT
Date: 2026-09-08
Source type: AIGC
GT basis: group_intent_v2.0, with pre-split p05 per-image visual adjudication
Model predictions used for GT: no
Next-step authorization: required from user

## Inputs frozen

- Definition SHA-256: 0e9c6b0afc6220f96969ff04f8ed27592c10a64a6e31a7b6cc83d23487032a10
- Formal media mapping SHA-256: 0780f3e659fcae4655ea06b00365f7c8c37c089f44b21453f4eb6acbaa8080a6 (397 rows)
- p05 visual-review SHA-256: ab9931264c72daf17d7df29a5bed99e7c70e49e31f8572cb3125125ba8f006d0 (20 rows)

## GT statistics

- gate_queue_secondary / negative: 30
- gt_uncertain / uncertain: 40
- primary_binary / negative: 241
- primary_binary / positive: 86

## p05 visual adjudication

- positive: 17
- negative: 3
- The 20 p05 images were visually adjudicated before any split assignment. No model output was used to produce these labels.

## Per-group split result

- Total: DEV=238, VAL=80, HOLDOUT=79
- Exact group counts: see split_counts_by_group.csv.
- Allocation method and fixed seed: see v2_split_protocol.json.

## Required stop

The fixed 60/20/20 per-group allocation yields DEV=3 for u03-vehicle-cut-by-frame-edge, u04-night-or-blur-boundary-unreadable, u05-gate-queue-or-parking-ambiguous. This is below the execution brief Section 4 immediate-stop threshold of DEV < 5 per subgroup. The issue is preserved as a checkpoint alert; no Step 2 tool implementation, detector use, VLM/Ollama call, pilot, or Full DEV evaluation was started.

## Scope boundary

This is AIGC development/evaluation governance only. It is not Human Gold and cannot support production, robot-camera, or real-world accuracy claims. VAL and HOLDOUT images were not opened after split assignment in this stage.
