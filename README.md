# parking_order_violation P0 optimization workspace

- Task: `parking_order_violation`
- Frozen event definition: `v1.1`
- Source batch: `/home/yanbo/下载/batch_20260902_115647_parking-order-violation-batch1-400-retry`
- Formal dataset: `/home/yanbo/net_vlm_xunjian_dataset`
- Formal project: `/home/yanbo/net_vlm_yanboversion/vlm` (read-only; not used for edits)
- Inference endpoint: `http://192.168.20.62:11434/api/generate`
- Model: `qwen3.5:4b`

## Split naming

The frozen dataset schema allows `train`, `validation`, `test`, and `holdout`, but not `DEV` or `VAL` literals. This task uses the existing convention:

- `train` = DEV
- `validation` = VAL
- `holdout` = HOLDOUT

All P0 code asserts that only `train`/DEV rows are loaded. VAL and HOLDOUT are sealed before inference and are not consumed.

## Ground-truth basis

All labels from this AIGC batch are explicitly `GT_BASIS=generation_intent` and `GT_REVIEW_STATUS=unreviewed`. They are prompt/source-intent-derived synthetic labels, not human visual gold labels and not model predictions. Any metrics are therefore development evidence for this synthetic auxiliary set, not production accuracy.

## Scope constraints

This workspace does not SSH, modify server files, modify `/home/yanbo/net_vlm_yanboversion/vlm`, run P1/P2/P3/P4, or create a Git commit.
