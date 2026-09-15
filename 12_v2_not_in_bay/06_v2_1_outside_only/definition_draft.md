# v2.1 definition draft: outside-only scope

- Draft date: 2026-09-14
- Status: **DRAFT / NOT FROZEN**
- Source lineage: evaluator-layer proposal based on the frozen v2.0 definition and frozen v2.0 GT/split.
- This draft does **not** edit `12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv`, `v2_split.csv`, or any historical artifact.
- This draft does **not** authorize a VAL/HOLDOUT run, model request, production integration, or robot-camera claim.

## 1. Purpose and scope

v2.1 narrows the evaluated event to a single event family:

> A stationary vehicle is clearly and completely outside a marked parking bay, on a driving aisle, or on an open area that is intended to remain passable.

The evaluator must have sufficient visual/geometric evidence that the vehicle's full relevant footprint is outside the marked bay / occupying the driving area. A line touch, small edge crossing, nose/tail overhang, or an ambiguous boundary is not enough.

The rule is image-level OR: an image is positive if at least one eligible vehicle clearly satisfies the outside-only definition. If no eligible vehicle satisfies it, the image is not positive. If the evidence cannot establish the condition, the result is `uncertain`, not an alert.

## 2. v2.1 labels

### positive

At least one stationary vehicle is clearly completely outside a marked parking bay and on a driving aisle/open passable area.

### negative

No eligible vehicle satisfies the outside-only definition. This includes:

- ordinary compliant parking inside one bay or a designated parking area;
- a vehicle that only touches or lightly crosses one separator line;
- a small single-boundary overrun;
- nose/tail overhang beyond a bay;
- angled parking that remains mainly within one bay;
- a large vehicle that remains mainly within one parking area;
- an ordinary gate queue (reported in the separate hn01 scope below).

### uncertain

Use `uncertain` when the available evidence cannot establish that the entire relevant vehicle footprint is outside the bay / on the driving area, including unreadable markings, occlusion, truncation, blur, poor geometry, or unresolved queue context. `uncertain` does not alert and is excluded from positive/negative recall and FPR denominators.

### out_of_scope

Use `out_of_scope` for a violation family intentionally excluded from v2.1. `out_of_scope` is not a negative label and is excluded from TP, FN, FP, and TN.

## 3. Evaluator-layer scope mapping

The following mapping is applied by the v2.1 evaluator at load time. It is not written back to GT/split files.

| existing group / row condition | v2.1 evaluator scope | v2.1 treatment | reason |
|---|---|---|---|
| `p01-outside-legal-bay-clear` | `primary_binary` | positive | This is the intended outside/aisle event family, subject to the row's evidence being clear. |
| `p02-cross-single-boundary-line` | `primary_binary` | negative | Single-line crossing is explicitly not sufficient. |
| `p03-span-two-bays` | `out_of_scope` | excluded; report separately | Two-bay spanning is removed from v2.1, even when it was positive in v2.0. |
| `p04-angled-footprint-outside` | `primary_binary` | negative unless separately re-adjudicated as fully outside | The existing group definition treats this as angled parking that remains mainly in one bay; the name alone cannot create a v2.1 positive. |
| `p05-multi-vehicle-at-least-one-violation`, existing `v2_gt=positive` rows | `out_of_scope` pending a row-level outside-only adjudication | excluded; report separately | The frozen p05 positive evidence is separator-line / two-bay evidence, not outside-only evidence. It must not be silently reused as v2.1 positive. |
| `p05-multi-vehicle-at-least-one-violation`, existing `v2_gt=negative` rows | `primary_binary` | negative | The frozen row-level adjudication says no qualifying violation. |
| `p06-nose-or-tail-intrudes-aisle` | `primary_binary` | negative | Small nose/tail intrusion is explicitly excluded. |
| `n01`–`n06` | `primary_binary` | negative | Compliant parking / non-violating controls remain negative. |
| `hn01-gate-queue` | `gate_queue_secondary` | excluded from primary; report separate FPR | Gate queue remains a separate hard-negative scope, not part of primary recall/FPR. |
| `hn02`–`hn06` | `primary_binary` | negative | Hard-negative controls remain negative unless a future frozen revision says otherwise. |
| `u01`–`u05` | `gt_uncertain` | excluded; report uncertainty separately | Existing uncertainty groups remain non-alarming and are not forced into binary metrics. |

### p05 governance note

The current p05 file is a mixed multi-vehicle set whose frozen positive rows were adjudicated for spanning-two-bays evidence. Because v2.1 is outside-only, those rows cannot be counted as v2.1 positives without a new, explicitly frozen row-level outside-only adjudication. That adjudication is a future task; it is not performed by this draft.

## 4. Metric contract for a future v2.1 evaluator

- Primary recall: TP / (TP + FN) over rows mapped to `primary_binary` with v2.1 positive ground truth.
- Primary FPR: FP / (FP + TN) over rows mapped to `primary_binary` with v2.1 negative ground truth.
- `out_of_scope` rows are omitted from every primary confusion-matrix denominator and are reported as a separate count/list.
- `gate_queue_secondary` (`hn01`) is not merged into primary FPR; report its FPR separately.
- `gt_uncertain` rows are not converted into negative rows and do not contribute to primary recall/FPR.
- The evaluator must fail closed when a row lacks a frozen v2.1 scope mapping; it must not infer scope from a model answer, filename, prompt text, or prediction.
- No metric is valid for v2.1 until the row-level mapping is frozen and independently checked.

## 5. Evidence and boundary requirements

A future v2.1 positive requires evidence sufficient to support “completely outside / driving aisle.” A visible mask, bbox lower band, or model Q1 answer is not by itself ground-contact proof. If geometry is not trustworthy, the evaluator must return `uncertain` or `out_of_scope` rather than manufacture a positive.

This draft deliberately does not define a new VLM prompt, threshold, detector configuration, or production rule implementation. It only defines the intended event scope and the evaluator-side mapping boundary.

## 6. Non-mutation and execution boundary

- GT and split source files remain the v2.0 originals.
- No VAL/HOLDOUT image is opened or evaluated by this draft.
- No model request is made by this draft.
- This document is a proposal for review; it is not a frozen v2.1 release and does not authorize a new run.
