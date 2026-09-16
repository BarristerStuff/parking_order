# ParkScope Conservative Geometry P1.1 Protocol

Frozen on 2026-09-16 before accessing EVALUATION GT. P1.1 is a selective geometry triage frontend, not a complete parking-violation classifier.

- Frozen P0 inference and P1 features/split are reused read-only.
- New ParkScope requests: 0. Ollama requests: 0.
- `OUTSIDE_POSITIVE_ENABLED=false`; the old `geometry exists -> POSITIVE_OUTSIDE` fallback is removed.
- Target decisions are limited to `POSITIVE_MULTIBAY`, `NEGATIVE_IN_BAY`, `UNCERTAIN_NO_EVIDENCE`, `UNCERTAIN_CONFLICT`, and `UNCERTAIN_ANCHOR`.
- A frame is positive if any target is `POSITIVE_MULTIBAY`; negative only if every target is `NEGATIVE_IN_BAY`; otherwise uncertain.
- The existing 30 CAL / 30 EVAL split is reused exactly. EVAL remains sealed until one safe CAL winner is frozen.
- Exactly 729 preregistered configurations are enumerated. No additional parameter or outside threshold is searched.
- Safe CAL configurations require FP=0, explicit-negative-on-positive=0, conditional positive precision=1.0, p03 strict recall >=0.60, minor-crossing FP=0, and decision coverage >=0.40.
- Winner ordering: p03 recall, coverage, strict recall, lower uncertain rate, then lexicographically smallest parameter tuple.
