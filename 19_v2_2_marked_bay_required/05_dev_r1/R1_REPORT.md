# V2.2 R1 Recall DEV Report

FINAL_STATUS=V2_2_R1_DEV_GATE_FAIL

Coverage: 238/238 unique=238. GT SHA exact=True. Logical protocol success=1.000000. Historical timeout evidence remains preserved.

Primary denominator: 196 (positive 62, negative 134); uncertain and gate-secondary GT are excluded from primary confusion.

R0: TP=3 FP=0 TN=134 FN=59
R1: TP=42 FP=45 TN=89 FN=20
Precision=0.482759 Recall=0.677419 F1=0.563758 FPR=0.335821 BalancedAccuracy=0.670799
P01Recall=0.913043 P03Recall=0.388889
UnmarkedOrOutsideRecall=0.781250 MultibayRecall=0.538462 MinorCrossingFPR=0.500000 GateQueueFPR=0.000000

R0 to R1: delta TP=39 FP=45 FN=-39 Recall=0.629032 FPR=0.335821 F1=0.471451.
Positive GT R0-all-A to R1 B/C=40; negative GT R0-all-A to R1 B/C=45.

R1_GATE_PASS=false
DEV_CHAMPION=NONE
R2_ALLOWED=false

No VAL or HOLDOUT was executed. Taxonomy is diagnostic and not asserted as proven root cause.
