# vehicle_parked_on_road_v3.0

## Business Goal

Detect a static vehicle that is either parked in a road/driving aisle or clearly occupying two parking bays. This version intentionally narrows the alert definition compared with older “not entirely inside one bay” interpretations.

## Core Assumptions

- All visible vehicles are treated as static vehicles for this event.
- The event does not infer motion, dwell time, authorization, payment, ownership, or driver intent.
- Uncertain evidence must not generate an alert.
- AIGC prototype data and real robot/camera data must remain separated in reports and claims.
- Old v2 GT must not be directly reused as v3 human gold because the v3 business definition changed.

## Vehicle-Level Labels

- `positive_road`: the vehicle footprint is clearly in a road, driveway, parking-lot driving aisle, or similar non-bay passage, and it is not a normal gate queue vehicle.
- `positive_two_bays`: the vehicle clearly occupies two adjacent parking bays, based on footprint/mask/BEV evidence rather than only a visual line touch.
- `negative_in_bay`: the vehicle is normally parked in one valid bay or marked parking area.
- `negative_line_touch_or_minor_overrun`: the vehicle touches/crosses a line or slightly exceeds a side boundary, but the main vehicle body remains attributable to one bay and does not clearly occupy two bays.
- `negative_nose_tail_overhang`: the vehicle nose or tail slightly protrudes beyond the bay while the vehicle body remains essentially parked in one bay.
- `negative_gate_queue`: the vehicle is in a normal gate/entrance queue or check-point lane context.
- `uncertain`: visual or spatial evidence is insufficient to decide road-vs-bay or two-bay occupancy reliably.
- `ignore`: no valid target vehicle for this event, false detector hit, or object outside event scope.

## Image-Level Labels

- `positive`: at least one valid vehicle is `positive_road` or `positive_two_bays`.
- `negative`: all valid, judgeable vehicles are negative labels.
- `uncertain`: no reliable positive evidence exists and at least one valid vehicle is `uncertain`.
- `ignore`: there is no effective target vehicle or the image is outside this task.

## Explicit Non-Alerts

- A wheel or body edge touching one line is not enough for positive.
- Slight side-line crossing without clear two-bay occupancy is not positive.
- Slight nose/tail overhang is not positive.
- Gate queue vehicles are not positive.
- Poor visibility, missing bay lines, occlusion, night blur, or ambiguous road/bay relationship is `uncertain`, not positive.

## Required Evidence Priority

1. Segmentation mask.
2. BEV vehicle footprint.
3. Vehicle bbox lower-half / bottom contact region.
4. Plain bbox only when uncertainty is explicitly preserved; weak bbox evidence must not be forced to positive.

## Development Boundary

The initial v3 overlay may use old v2 DEV images and detector cache only as a prototype source. It must report coverage, review status, and blocking conditions. No v3 Winner or production integration may be created until real fixed-camera ROI, independent labels, validation gates, and robot data evidence exist.
