# V2.3 decomposed relation rationale

V2.2 history is immutable. R0 collapsed toward A (recall 0.048387, FPR 0); R1 shifted toward C (recall 0.677419, FPR 0.335821). Vehicle-level R1 Q1 counts are `{'C': 146, 'A': 149}`; B=0 and D=0. This confirms that one four-way decision did not provide a stable separation of outside, multibay, inside, and uncertainty.

V2.3 retains the v2.2 business definition but decomposes perception into independent binary specialists: Q_OUTSIDE on frozen View A and Q_MULTIBAY on deterministic local View B, followed by the frozen Q_GATE only for a candidate violation. No scoring or learned threshold is introduced.
