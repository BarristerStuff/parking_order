# parking_order_violation v1.2

```text
event_name=parking_order_violation
event_definition_version=v1.2
status=FROZEN
frozen_date=2026-09-07
```

## Upstream premise and scope

All vehicles entering this event classifier are already confirmed stationary by an upstream component.

This event does not judge vehicle movement, parking duration, parking permission, fees, owner identity, or eligibility for special spaces.

Core question:

> Is this vehicle clearly and substantially parked outside a normal single parking space?

## Positive

Return `positive` only when at least one non-gate-queue vehicle has a clear and substantial parking-order violation:

- The vehicle body is clearly and substantially outside a normal legal parking space.
- The vehicle clearly occupies multiple parking spaces.
- The vehicle is severely angled across parking spaces and materially intrudes into adjacent parking space.
- The vehicle clearly occupies a normal parking/driving aisle.
- In a multi-vehicle scene, at least one vehicle meets one of the conditions above.

## Negative

Return `negative` for:

- A vehicle with an overall normal relationship to one legal parking space.
- A tire touching or slightly crossing a line.
- A vehicle edge or bumper extending slightly beyond a line.
- A vehicle close to a line, slightly off-center, or mildly angled.
- A large SUV, MPV, pickup, or van that clearly belongs to one parking space.
- A clearly normal gate queue.

## Uncertain

Return `uncertain` when the parking-space relationship cannot be judged reliably, including:

- No reliable parking area or parking-space basis is visible.
- The vehicle is severely truncated or occluded.
- Markings or environmental evidence are severely insufficient.
- Night, blur, or glare prevents a reliable judgment.
- Normal parking cannot be distinguished from a clear violation.
- A normal gate queue cannot be confirmed or excluded.

## Explicit exclusions

Do not use any of the following as a positive rule:

- Whether the vehicle is 100% inside a parking-line polygon.
- Whether any pixel crosses a line.
- Whether any tire touches or crosses a line.
- Whether a bumper crosses a line.
- Centimeter, pixel, or crossing-percentage estimates.

## Evaluation status

V1.2 is first evaluated with a DEV-only generation-intent shadow GT. This shadow GT is not per-image Human Gold and must not be presented as production accuracy. `p02-cross-single-boundary-line` is unresolved without per-image human adjudication and is excluded from primary binary metrics.

