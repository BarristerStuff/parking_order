# vehicle_not_in_bay v2.1 outside-only definition

- Status: FROZEN
- Freeze date: 2026-09-15
- Source type: AIGC
- Definition layer: evaluator-only; the frozen v2.0 GT and split files are not modified.
- Production, robot-camera, and Human-Gold claims: NOT AUTHORIZED.

## Event definition

All vehicles are treated as stationary. An image is positive only when at least one eligible vehicle is clearly outside any marked parking bay, standing on open pavement, a driving aisle, or another open passable area. Merely touching/crossing one line, spanning two bays, nose/tail overhang, angled but mainly single-bay parking, compliant large-vehicle parking, and ordinary gate queues are not primary positives.

## Frozen evaluator mapping

- `positive`: every `p01-outside-legal-bay-clear` row.
- `out_of_scope`: every `p03-span-two-bays` row and every `p05-multi-vehicle-at-least-one-violation` row, regardless of the v2.0 row label. These rows are excluded from TP/FP/TN/FN and reported only by alert rate.
- `secondary`: every `hn01-gate-queue` row. Excluded from primary FPR and reported as a separate FPR/alert rate.
- `uncertain`: every row in `u01` through `u05`. Excluded from primary recall/FPR; uncertain predictions never alert.
- `negative`: every remaining row.

The mapping is derived mechanically from the frozen `group_key`; model output, filename, target_bbox_hint, GT label, or split membership cannot change it.

## Frozen Q1-only decision

For each selected vehicle, ask only frozen R1 Q1 using View A. Image-level priority:

1. any selected vehicle answers `C` -> `positive`;
2. otherwise, any selected vehicle answers `D` or any required request fails -> `uncertain`;
3. otherwise -> `negative`.

Q1 `B` is negative under outside-only v2.1. Q2 is never asked. No eligible detection safely yields `uncertain`.

## Metrics

- Recall: alerts / all `positive` rows.
- Negative FPR: alerts / all primary `negative` rows.
- `hn01`: separate alert rate/FPR.
- `p03` and `p05`: separate alert rates, not recall or FPR.
- Uncertain rate: image predictions equal to `uncertain` divided by all evaluated images, with subgroup details also retained.
- Wilson 95% intervals are reported for binomial rates.

## Governance

This authorization covers exactly one 80-image VAL execution. HOLDOUT images must not be read. Parameters may not be adjusted after the run and the run may not be repeated. GT/split files and historical artifacts remain immutable.
