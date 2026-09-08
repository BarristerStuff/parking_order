# parking_order_violation P0 final audit

- Audit date: 2026-09-03
- Status: **PASSED**
- Scope: DEV/`train` only
- VAL_CONSUMED=false
- HOLDOUT_CONSUMED=false

## Dataset

- Formal batch rows: 1
- Media / labels / splits / review links: 397 / 397 / 397 / 397
- Split counts: train=239, validation=80, holdout=78
- Cross-split groups: 0
- Full validate: valid, errors=0, warnings=687
- Totals: media=7716, labels=6620, splits=3315, batches=50

## P0

- Predictions: 239 unique DEV IDs; all split=train; all status=ok
- Prediction intersection with VAL: 0
- Prediction intersection with HOLDOUT: 0
- Frozen hashes: match
- HOLDOUT seal hash: f8792c1aa3d747613b2705c5c8d2818983ca0dcdcf94978efcb7c3d6b488c081 (match)

## Boundaries

- Local task, no Worktree created
- No P1/P2/P3/P4
- No SSH; no server-file modification
- No Git commit
- Formal `vlm` status unchanged from initial observation; pre-existing dirty state preserved

## Limitation

Metrics use unreviewed synthetic generation-intent GT, not Human Gold or production evidence.
