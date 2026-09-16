# ParkScope Conservative Geometry P1.1

## Final status

`PARKSCOPE_P1_1_NO_SAFE_TRIAGE_RULE`

The protocol stopped at CALIBRATION. No safe configuration existed, so the sealed 30-image EVALUATION partition was not executed or used for rule development. Gate-secondary diagnostics were also not run.

## Old P1 failure attribution

- Old minimum FP: 10/15 negatives (FPR 0.666667)
- Minimum-FP configurations: 162
- FP-frame union/intersection: 10 / 10
- Configuration-frame FP occurrences: 1620
- Outside-fallback occurrences: 1620
- Separator occurrences: 0
- Both occurrences: 0

All minimum-FP-family false positives were caused by the old outside fallback. This supports removing that fallback, but does not establish that the remaining geometry rule is useful enough.

## P1.1 calibration

- Grid configurations: 729
- Safe configurations: 0
- FP range: 0–0
- Minimum explicit negative-on-positive count: 2
- Maximum p03 strict recall: 0.000000
- Maximum decision coverage: 0.300000
- Maximum strict overall recall: 0.200000
- Minimum uncertain rate: 0.700000
- Minimum minor-crossing FP: 0

Although every configuration achieved zero FP and conditional positive precision 1.0 on CAL, every configuration explicitly classified two positive frames as negative, no configuration identified any CAL p03 frame as positive, and maximum decision coverage was only 0.30. Therefore every configuration failed multiple preregistered safe-triage gates.

## Boundaries

- `OUTSIDE_FALLBACK_REMOVED=true`
- `OUTSIDE_POSITIVE_ENABLED=false`
- ParkScope new requests: 0
- Ollama requests: 0
- FULL DEV, VAL, HOLDOUT, and old Holdout rerun: not executed
- Current development winner: none
