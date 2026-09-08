# parking_order_violation v1.2 shadow GT mapping

## Confirmed facts

- Source: frozen v1.1 P0 DEV manifest only.
- Split guard: 239/239 rows are `train` (DEV).
- Unique media binding: 239/239.
- V1.2 DEV manifest: 204 rows.
- Primary binary: 179 rows (59 positive, 120 negative).
- GT uncertain: 25 rows, excluded from binary confusion matrix.
- Boundary challenge: 35 p02 rows, excluded from primary metrics.
- VAL_CONSUMED=false.
- HOLDOUT_CONSUMED=false.

## Mapping rule

- Positive core: p01 and p05 -> `positive`.
- Negative core: original DEV negative/hard-negative groups -> `negative`.
- Original uncertain groups -> `uncertain`.
- p02 -> `boundary_unresolved`.

## Evidence limitation and risk

This is an auditable generation-intent shadow GT, not per-image Human Gold. Subgroup names and their DEV generation prompts are semantically consistent with v1.2, but individual generated pixels have not been visually adjudicated. Metrics from this manifest are proxy development evidence and must not be presented as production accuracy. In particular, p02 is not mechanically relabeled.

## Frozen references

- Source manifest SHA-256: `ac4796d5f5d03c837f87056865c53d06e9823b58e6e3ee3e1e98bc226e9e8ee0`
- Definition SHA-256: `64a3f3e73a31e97b1468827be24b1cdfbb713d531e76a60b6b36cfde8623cc67`
- Prompt SHA-256: `a6ae853aad36ed5e0ecf3856761b7ae34d0cf6933218ad68f3901dfa7cf1458d`
- V1.2 DEV manifest SHA-256: `8a2d44f8c6b949486d46275e8f9b189c6b7605093ccc38ab6d0ef6c7cae6d525`
- Boundary manifest SHA-256: `3ef4da8e13dc5c37a84c24ba1943a0617070e5cf7beee00f2be5aaaab9073797`
