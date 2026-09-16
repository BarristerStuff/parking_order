# ParkScope Structured Geometry P1 Protocol

Date: 2026-09-16. This is a geometry-only pilot using frozen P0 segmentation metadata. No new ParkScope or Ollama requests are permitted.

The 60 primary images are deterministically split 30 CAL / 30 EVAL with seed `20260916_PARKSCOPE_P1_CAL_EVAL`, exactly 5 images from each of the six frozen strata per side. Ten gate-secondary images are diagnostics only. Features and the 729-configuration grid are frozen before evaluation. Safe calibration requires precision >=0.90 and FPR <=0.10. Winner order: recall, F1, lower uncertain rate, lexicographically smallest parameter tuple. EVAL is run once with the winner.

An absent geometry detection never implies outside; it yields uncertain. Invalid anchors remain uncertain. Strict positive recall counts uncertain positives as FN; uncertain negatives are not FP but reduce coverage.
