# V4 Artifact Index

This index is the final deliverable map. All paths are relative to `/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm` and are covered by `contracts/final_hash_manifest.json` except the hash manifest itself.

- `README.md`, `ADR.md`, `EXECUTION_REPORT.md`: scope, architecture decision, and final conclusion.
- `contracts/`: DEV allowlist, forbidden split metadata, fixed pilot, run/config/prompt/decision contracts, preflight, trial registry, and initial state.
- `reference/`: frozen provisional image/vehicle labels, target-level detector review, recheck logs, pixel-review sheets, and freeze record. `REFERENCE_FREEZE_DRAFT_INVALIDATED.json` is retained as an invalidated draft history record and was never used for metrics.
- `inference/`: direct Ollama runner, reusable `classify_image`, and the two smoke clients.
- `evaluator/`, `tests/`: strict response parser, deterministic decisioner, auditable metrics, synthetic fixtures, and standard-library test runner.
- `inputs/pilot/`, `inputs/pilot_r1/`: frozen R0/R1 prepared scene/crop/composite inputs and target batches.
- `outputs/pilot_r0/`, `outputs/pilot_r1/`: physical request logs, raw responses, target predictions, image predictions, and run summaries.
- `metrics/pilot_r0/`, `metrics/pilot_r1/`: evaluator inputs, metrics with Wilson intervals, subgroup tables, error rows/locators, and latency.
- `audit/`: independent integrity audit and metric recomputation for both candidates.
- `logs/`: direct Ollama tags/ps preflight and smoke response evidence.
