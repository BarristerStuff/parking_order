# vehicle_not_in_marked_bay v2.2

**Status: FROZEN**  
**Event name:** `parking_order_violation`  
**Revision:** `V2.2_MARKED_BAY_REQUIRED`

## Decision contract

Judge whether a stationary vehicle clearly belongs to **one marked parking bay**, not whether any pixel touches or crosses a line.

### Positive
- Clearly not belonging to any marked parking bay.
- Unmarked roadside, curbside, shoulder, open pavement, or driving aisle parking.
- Only a curb, road edge, or single roadside line without a bay.
- Clearly occupying substantial parts of two or more marked bays.
- A multi-vehicle frame is positive if at least one vehicle is positive.

### Negative
- Clearly belonging overall to one marked bay.
- Minor line contact, one-tire contact/crossing, small bumper overhang, small-area crossing, or mild angle.
- Large vehicle close to a bay boundary but still compliant.
- Faded/partly occluded markings that still establish one bay.
- Normal gate/checkpoint waiting or queueing.

### Uncertain
- Markings or parking context are too occluded, faded, blurred, dark, or cut off to determine reliably whether a marked bay exists, including unresolved queue-versus-parking context.

## Frozen semantic flags

```text
MINOR_LINE_CONTACT_IS_NOT_VIOLATION=true
UNMARKED_CURBSIDE_PARKING_IS_VIOLATION=true
CLEAR_MULTI_BAY_OCCUPANCY_IS_VIOLATION=true
GATE_QUEUE_IS_EXEMPT=true
OFFLINE_IMAGE_ONLY=true
```
