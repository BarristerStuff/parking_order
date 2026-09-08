# P3-lite Geometry Fast Gate — Frozen design

Date: 2026-09-07

## Scope and decision boundary

This is a one-shot feasibility gate, not a complete parking-space system. It
uses the existing F2 YOLO detections, local deterministic image geometry, and
no VLM in P3L-A. It may proceed to a full-scene gate-queue veto only if the
fixed 60-sample pilot passes every promising-gate threshold.

Only the `train` DEV shadow set is in scope. VAL and HOLDOUT are prohibited.

## Confirmed facts

- F0/F1/F2 are frozen and are not rerun or modified.
- The F2 cache binds all 239 manifest images and contains 1,059 car/truck/bus
  detections; every sample has at least one detection.
- No local parking-slot-specific checkpoint was found. No checkpoint is
  downloaded and no optional model branch is entered.
- The ten debug samples are outside `primary_binary`: five p02 boundary
  challenges and five GT-uncertain samples.
- The pilot is frozen before inference: p01=20, p05=20, gate queue=8,
  ordinary normal=6, compliant large vehicle=3, close-to-line normal=3.

## Inference isolation

`geometry_engine.py` rejects input carrying GT, sample role, group, source_id,
evaluation scope, pilot stratum, or media_id. Its opaque key is the image
content SHA-256. The evaluator is a separate process and is the only component
that reads the pilot manifest's evaluation metadata.

## Frozen geometric evidence

For each eligible vehicle, the engine uses a bottom contact row inset by 8%
of bbox height and left/right contact anchors inset by 8% of bbox width. The
context width is 2.3 vehicle widths and preferentially includes the ground
below the vehicle.

Line candidates combine CLAHE, white/yellow masks, Canny, and OpenCV LSD.
Length, angle, brightness, local contrast, exposed fraction, and position are
filtered. Candidate lines are projected to the contact row and merged into
local separator hypotheses.

Positive is permitted only for:

- G1: at least one high-confidence adjacent slot exists wholly on one side of
  the vehicle contact anchors, with the vehicle clearly outside it; or
- G2: at least three high-confidence consecutive separators form plausible
  intervals and an internal separator crosses the vehicle's contact core.

A single line, bbox/line intersection, close-to-line placement, mild angle,
or unclear marking can only produce `insufficient`. High-confidence normal
requires a plausible paired slot containing the contact anchors.

## Debug freeze result

The single pre-pilot parameter set was run once on the ten fixed non-primary
debug samples. All ten were `insufficient`; no positive was triggered. This is
consistent with the intended conservative handling of single-boundary and
uncertain scenes, but it does not demonstrate recall. No parameter was changed
after this debug run.

## Known risk and stopping rule

Arbitrary front/oblique monocular scenes may not expose enough repeated slot
markings for local line pairing. If pilot positive recall or p01 recall is
below 0.50, or gate-queue FPR exceeds 0.10, P3-lite stops immediately. Even
without an immediate-fail trigger, failure to meet every promising-gate
threshold stops the task; it does not start a second threshold search.
