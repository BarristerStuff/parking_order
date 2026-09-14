# V5 detector / footprint execution report

Date: 2026-09-10  
Work directory: `/home/yanbo/net_vlm_parking_optimization/18_v5_detector_footprint/`

## Facts

The input is a frozen allowlist of 60 unique AIGC DEV pilot images reused from V4. The provisional reference contains 240 vehicles: 14 `positive_road` and 18 `positive_two_bays`. It is AI visually reviewed, not human gold. Split metadata reports DEV 238, VAL 80 and HOLDOUT 79; only the 60 allowlisted DEV images were decoded by this stage.

R0 ran all 60 images with YOLOE26m, classes `car, truck, bus`, imgsz 640, confidence 0.25, IoU 0.7, max_det 50, retina masks, CPU and four torch threads. It produced 196 raw detections and 195 deduplicated targets. Frozen label-blind matching associated 155/240 (64.58%), road 5/14 (35.71%), and two-bay 11/18 (61.11%).

R1 was justified by visible R0 misses of pickup/van vehicles and changed one main factor only: classes became `car, truck, bus, pickup truck, van`; every other setting remained fixed. R1 ran all 60 images and produced 222 raw detections and 221 deduplicated targets. Geometric associations were 178/240 (74.17%), road 13/14 (92.86%), and two-bay 16/18 (88.89%). These are `AI_PROVISIONAL_REFERENCE_COVERAGE` upper bounds under the frozen matcher, not true detector Recall.

All R0/R1 overview sheets and both focused R1 risk sheets were reviewed. R1 has 23/240 explicitly confirmed matched-reference identities as a deliberately conservative audit-progress lower bound, four `confirmed_detector_miss`, 58 other unmatched references not promoted to confirmed misses, one disputed booth-like reference, one `possible_false_detection`, and one confirmed duplicate proposal. Unresolved identity/localization is retained where the available visual scale is insufficient.

Footprint diagnostics used all 221 R1 targets and exactly two methods, yielding 442 method records. Exported visible-mask polygons are numerically valid for 221/221; this is not semantic mask quality or footprint accuracy. Stricter exported-polygon topology passes 185/221 and rejects 36/221, while original dense-mask/component provenance is unavailable for 221/221. A stratified visual sample reviewed 20/221 vehicles: mask-bottom candidates were locally plausible proxies for 6, bbox-lower proxies for 11; no population extrapolation is made.

`mask_bottom_contact_band` produced 185 uncertain and 36 failed records, with 0 validated. `bbox_lower_conservative_proxy` produced 176 proxy and 45 uncertain records, with 0 validated. Across both methods, ground-contact validated count is 0; every `ground_contact_polygon` and footprint IoU is null. A visible mask or bbox lower band is never named or accepted as true ground footprint.

No trusted road/bay/gate geometry exists for the reused pilot. Therefore `SPATIAL_EVIDENCE_FORMAL_EVALUATION=BLOCKED_NO_TRUSTED_GEOMETRY`; formal pilot rules-only evaluation was not executed and all classification Recall/FPR values are null. Eleven synthetic fixture expectations passed, but they are code tests only, not algorithm accuracy.

R0 plus R1 made 120 local detector image calls. VLM execution was false and physical model requests were 0. No VAL/HOLDOUT image or label was consumed. Pre/post protected hashes cover 1,121 files; the V4 freeze verified 8/8 and the prior V5 manifest verified 115/115. Production and protected old-directory Git/status evidence remained unchanged from baseline; pre-existing dirty state was not modified.

Tests: all Python files compiled; 58/58 standard-library tests passed (11 matching, 24 footprint, 6 contracts, 5 synthetic rules, 6 metrics, 6 integration guards). Independent audit code recomputed R0/R1 matching and integrity checks with 55 checks passing and no failures before final-manifest verification.

## Reasoning

The immediate blocking gate is detector coverage: R1's best possible frozen geometric association is only 74.17% overall and 88.89% for two-bay, below the required 90%. Expanding class prompts improved road coverage and recovered pickups/vans, but it did not make the detector eligible for formal spatial rules or a VLM verifier.

Ground-contact remains a second independent bottleneck. Numeric mask validity is high, but neither tested transformation is physically validated; the mask band is uncertain/failed and the bbox band is explicitly only a proxy. Even after detector coverage improves, a method needs retained dense-mask components plus independent ground-contact geometry or human geometric annotation before formal use.

Geometry is a third blocked dependency: old AIGC pilot images have no trusted road/bay/gate polygons. The synthetic fixture validates rule behavior and coordinate safeguards only. There is no basis for formal pilot Recall/FPR.

There is reason to continue V5 only through a new, separately frozen detector experiment and geometry acquisition, not through VLM or threshold/prompt sweeping in this run. The next detector revision must change one evidence-backed main factor, preferably resolution/model capability for tiny, background and truncated vehicles, and must be authorized as a new stage because R2 is prohibited here.

## Risks

- AIGC domain gap: these 60 images do not establish real-camera or robot behavior.
- AI provisional reference: denominator defects and duplicate/non-vehicle references may exist; no human gold is available.
- Matching uncertainty: IoU associations can miss true identity matches or pair nearby vehicles; geometric coverage is neither Recall nor visual confirmation.
- Visible mask versus ground footprint: vehicle silhouette includes elevated bodywork and occlusion and does not identify tire/ground contact.
- Synthetic geometry leakage: fixture geometry is evaluator-controlled and cannot be presented as real-image evidence.
- Real robot behavior, camera calibration, production latency and end-to-end production integration remain unverified.

## Required flags

```text
BUSINESS_DEFINITION=v3.0_user_confirmed
ALGORITHM_REVISION=V5_DETECTOR_FOOTPRINT
SOURCE_TYPE=AIGC
REFERENCE_BASIS=AI_VISUAL_REVIEWED_PROVISIONAL
HUMAN_GOLD=false
V4_PILOT_REUSED=true
DETECTOR_R0_EXECUTED=true
DETECTOR_R1_EXECUTED=true
FOOTPRINT_EXECUTED=true
TRUSTED_GEOMETRY_AVAILABLE=false
RULE_ONLY_EXECUTED=false
VLM_EXECUTED=false
PHYSICAL_MODEL_REQUESTS=0
OLD_V2_VAL_HOLDOUT_CONSUMED=false
PRODUCTION_INTEGRATION_READY=false
CURRENT_STATUS=V5_DETECTOR_COVERAGE_BLOCKED
```

## Next steps

1. Start a separately authorized detector stage with one frozen capability change targeting tiny/background/truncated vehicles; do not reopen this run as R2.
2. Acquire independent human ground-contact geometry or a frozen image-plus-geometry AIGC batch while retaining dense masks and contour-component provenance.
3. Re-enter spatial-rule and VLM gates only after detector, footprint and trusted-geometry gates all pass.
