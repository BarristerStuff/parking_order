# Detector coverage audit

Metric basis: `AI_PROVISIONAL_REFERENCE_COVERAGE`; this is not true detector Recall and the 240 frozen references are not human gold.

## Runs

R0 reproduced YOLOE26m segmentation on all 60 allowlisted DEV images with classes `car, truck, bus`, imgsz 640, confidence 0.25, model IoU 0.7, max_det 50, retina masks, CPU and four torch threads. R1 changed one main factor only: it added `pickup truck, van`. Both runs used frozen weights/encoder hashes and class-agnostic confidence-ordered dedup at IoU > 0.8. Total local detector image calls: 120. Physical VLM requests: 0.

| Run | Raw | Dedup | Geometric /240 | Road /14 | Two-bay /18 | Unmatched ref candidates | Unmatched det candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| R0 | 196 | 195 | 155 (64.58%) | 5 (35.71%) | 11 (61.11%) | 85 | 40 |
| R1 | 222 | 221 | 178 (74.17%) | 13 (92.86%) | 16 (88.89%) | 62 | 43 |

Matching is label-blind one-to-one bbox IoU >= 0.5. Geometric associations are an upper bound under this frozen matcher, not automatic visual confirmations. R1 fails the 90% gate on overall and two-bay coverage even at that upper bound.

## Visual audit

All 10 R0 sheets, all 10 R1 sheets and two focused R1 risk sheets were viewed. Contact-sheet resolution does not support target-level confirmation for every tiny, occluded or overlapping vehicle, so unresolved remains a valid outcome.

For R1, 23 matched references were explicitly confirmed as the same visible vehicle, a conservative lower bound of 23/240. Four clear unmatched foreground references were classified `confirmed_detector_miss`: `IMG_007547/T01`, `IMG_007601/T02`, `IMG_007650/T04`, and `IMG_007606/T02`. The other 58 unmatched references were not automatically called misses. `IMG_007340/T05` appears to enclose a gate booth rather than a vehicle and remains a disputed provisional reference in the denominator.

Six unmatched R1 detections were confirmed as visible vehicles without one-to-one frozen references. `IMG_007542/S004` is `possible_false_detection`, not confirmed false. In `IMG_007672`, raw_0006/raw_0007 represent the same background vehicle; raw_0007 is the one confirmed suppressed duplicate proposal.

The `review_status_counts` metric also includes unmatched detections and suppression records; it is not a reference denominator. The authoritative reference denominator remains 240, including 14 road and 18 two-bay references.

## Decision

`V5_DETECTOR_COVERAGE_BLOCKED`. No R2 is permitted. Footprint work is diagnostic only; formal pilot spatial rules and VLM are not executed.
