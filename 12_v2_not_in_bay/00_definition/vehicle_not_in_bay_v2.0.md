# vehicle_not_in_bay v2.0 definition

Status: FROZEN_PENDING_CHECKPOINT_1_CONFIRMATION  
Freeze date: 2026-09-08  
Source type: AIGC  
GT basis: group_intent_v2.0, except p05 uses the required per-image visual adjudication  
Production claim: NOT_AUTHORIZED

## Question

Given a single frame whose vehicles are already known to be stationary, determine whether at least one vehicle is clearly:

1. completely parked outside a marked parking bay or on the driving aisle/open pavement; or
2. spanning two parking bays, with a bay-separator line passing beneath the vehicle footprint and the vehicle occupying area on both sides of that separator.

## Labels

### positive

At least one vehicle clearly satisfies either of the two conditions above.

### negative

No vehicle satisfies the positive definition. The following remain negative:

- a tire or body edge merely touching or pressing a line;
- a small single-boundary overhang that does not clearly occupy two bays;
- the nose or tail extending slightly beyond a bay;
- angled parking that remains substantially within one bay;
- ordinary compliant parking;
- gate-queue scenes for v2.0 GT purposes, although hn01-gate-queue is excluded from primary metrics and reported separately.

### uncertain

The available visual evidence is insufficient to distinguish positive from negative, including severe occlusion, truncation, blur, darkness, unreadable bay markings, or ambiguous parking/queue context.

## Mechanical GT mapping

- p01-outside-legal-bay-clear, p03-span-two-bays -> positive
- p05-multi-vehicle-at-least-one-violation -> per-image visual adjudication before split assignment
- p02-cross-single-boundary-line, p04-angled-footprint-outside, p06-nose-or-tail-intrudes-aisle -> negative
- n01 through n06, and hn02 through hn06 -> negative
- hn01-gate-queue -> negative, scope gate_queue_secondary
- u01 through u05 -> uncertain, scope gt_uncertain

All other positive and negative rows use scope primary_binary.

## Governance

- The mapping is a development/evaluation label based on AIGC generation intent and the user-approved v2.0 rule. It is not Human Gold and must not be described as production or robot-camera accuracy.
- No model prediction may create or modify GT.
- p05 visual decisions are frozen before random split assignment; split membership is not consulted during visual review.
- VAL and HOLDOUT images must not be opened after split assignment during the current stage.
- Historical P0, F0, F1, F2, and P3L-A artifacts remain immutable.
- The production tree, formal shared labels, server files, and Ollama models are out of scope.
