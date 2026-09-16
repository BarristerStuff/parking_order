# V2.3 decomposed marked-bay relation protocol

V2.2 is closed after R1 DEV Gate failure; no R2 or R1b is permitted. V2.3 preserves the `vehicle_not_in_marked_bay_v2.2` business definition and frozen detector, selection, View A, Q_GATE, model, and GT.

Each selected vehicle receives independent Q_OUTSIDE on View A and Q_MULTIBAY on deterministic View B. Either YES creates a candidate violation and invokes frozen Q_GATE. Q_GATE A is gate-exempt negative, B/C preserves positive, and D is uncertain. With no YES, two NO answers are negative; otherwise an UNCERTAIN answer makes the vehicle uncertain. Frame fusion is positive-any, then uncertain-any, else negative.

The pilot is a one-shot frozen 60-primary plus 10 gate-secondary DEV sample. A pilot pass only authorizes returning for a separate full-DEV decision; this run cannot execute full DEV, VAL, or HOLDOUT.
