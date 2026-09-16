# V2.2_MARKED_BAY_REQUIRED_FAST_CLOSE execution report

Date: 2026-09-16 (Asia/Shanghai)

FINAL_STATUS=V2_2_R0_DEV_GATE_FAIL_R1_RECALL_ALLOWED
READY_FOR_R0=true
R0_EXECUTED=true
DEV_CHAMPION=NONE
R1_ALLOWED=true
R1_RECOMMENDED=RECALL
R1_EXECUTED=false

The required DEV visual review covered exactly 53 images: 21 positive, 32 negative, 0 uncertain. The review was performed from source images by `codex_visual_review`, uses `v2.2_visual_adjudication`, and is explicitly `NOT_HUMAN_GOLD=true`.

The frozen shadow DEV GT contains 238 unique DEV media IDs: positive=62, negative=134, uncertain=24, secondary_gate_queue=18. Independent GT validation reported `error_count=0`. Shared dataset labels were not modified.

R0 primary denominator=196 (uncertain and gate secondary excluded): TP=3, FP=0, TN=134, FN=59; precision=1.0, recall=0.048387, F1=0.092308, FPR=0, balanced accuracy=0.524194. p01 recall=3/23; p03 recall=0/18; minor-crossing FPR=0/24; gate-queue FPR=0/18; protocol success=326/326. The frozen Gate failed Recall, F1, p01 Recall, and p03 Recall.

A first local invocation failed all items before any model request because system Pillow 9.0.1 lacks `Image.Resampling`. This was preserved as pre-request environment evidence. The actual R0 used the bundled runtime with Pillow 12.3.0 and made 326 successful physical requests. No prompt, rules, config, inputs, model, or server state changed.

No R1, VAL, HOLDOUT, production integration, robot shadow, MQTT, SSH tunnel, or server modification was performed. `NEW_CHALLENGE_PLANNED=180`; `NEW_CHALLENGE_IMAGES_AVAILABLE=0`.
