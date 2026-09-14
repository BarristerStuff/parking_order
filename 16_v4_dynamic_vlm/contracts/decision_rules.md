# V4_R0 deterministic decision contract

This file is frozen before any Qwen request. Labels are not read from the prompt or filenames.

## Per-target input

Required fields: `target_id`, `vehicle_valid`, `evidence_sufficient`, `road_or_drive_aisle`, `occupies_two_bays`, `in_one_bay_or_designated_area`, `minor_line_or_nose_tail_only`, `normal_gate_queue`, `evidence`.
All enumerations except `evidence` are exactly `yes|no|unclear`; `evidence` is a short string.

## Per-target decision

1. `vehicle_valid=no` -> `ignore`.
2. If identity is unclear or `evidence_sufficient != yes` -> `uncertain`, reason `INSUFFICIENT_EVIDENCE`.
3. `normal_gate_queue=yes` -> `negative_gate_queue`; roadway status does not override a normal gate queue.
4. `normal_gate_queue=unclear` -> `uncertain`, reason `GATE_QUEUE_UNCLEAR` (never treat !=yes as no).
5. With queue=no and sufficient evidence:
   - `road_or_drive_aisle=yes` and no semantic conflict -> `positive_road`.
   - `occupies_two_bays=yes` and no semantic conflict -> `positive_two_bays`.
6. `minor_line_or_nose_tail_only=yes` and `occupies_two_bays=yes` -> `uncertain`, reason `SEMANTIC_CONFLICT`.
   Also conflict when mutually exclusive yes values include `in_one_bay_or_designated_area=yes` with road=yes or two_bays=yes, or `minor_only=yes` with road=yes.
7. `road=no`, `two_bays=no`, and (`in_one_bay=yes` or `minor_only=yes`) -> `negative`.
8. `road=no`, `two_bays=no` without explicit in-bay/minor evidence -> `uncertain`, reason `PARKING_RELATION_UNCLEAR`.
9. Invalid/missing/duplicate/omitted target response -> `protocol_failure`; never coerce to negative.

## Image aggregation

- Any reliable positive -> `positive`.
- No positive and any uncertain/protocol failure/unprocessed required target -> `uncertain`.
- All valid, judgeable targets explicit negative -> `negative`.
- No valid targets or detector miss is distinct from evidence of no violation; it cannot be auto-negative.
