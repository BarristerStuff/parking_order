# ADR — V5 Detector and Ground-contact Stage

Date: 2026-09-10. Scope: AIGC diagnostic development, no production integration.

## Decisions

1. Preserve prior 12/14/15/16/17 directories and production. All new experiment code, caches and results live under 18_v5_detector_footprint. Read formal source images only via the frozen 60-image DEV allowlist.
2. Fresh detector R0 exactly reproduces prior YOLOE26m/classes/conf/imgsz/NMS/max-det/retina-mask/CPU settings. R1 is the sole allowed candidate change: explicit `pickup truck` and `van` class prompts, supported by documented R0 visual misses. No threshold, resolution or crop sweep; no R2.
3. Matching is fixed before inference, label-blind descending IoU >= .50 greedy one-to-one with deterministic ties. Reference class labels join only in evaluation. A geometry match is not automatically a visually confirmed match; reference-unmatched is not automatically detector miss.
4. Visible body mask, mask-derived lower contact band and bbox-lower proxy are separate fields. No method can manufacture ground truth by setting a status string. Ground-contact polygon remains null without independent geometric validation. At most two fixed diagnostic methods are evaluated; class labels never enter either method.
5. Pilot rule evaluation needs confirmed detector coverage plus credible footprint plus trusted geometry. Abstract rectangle fixtures may test rule mechanics without satisfying these gates. The rule adapter is restricted to synthetic test IDs/scope; it is not a production trust boundary or authorized pilot pipeline.
6. VLM requests are forbidden throughout this stage. No `/api/tags`, `/api/ps`, `/api/generate` or `/api/chat`; local detector calls are counted separately from physical remote model requests.

## Consequences and limits

The reused 60-image AIGC pilot remains consumed diagnostic data; any apparent detector improvement is not independent real-world validation. Sparse/tiny/occluded reference targets can remain unresolved even if a geometric matching algorithm assigns them. More class prompts can recover vehicle subclasses while changing scores/duplicate proposals; all unchanged parameters must be audited.

Polygon-export validity and dense-mask quality are different. A single exported polygon may lack component provenance; contact-band construction must reject uncertain or disconnected geometry instead of bridging gaps into an apparent footprint. Bbox lower strips are weak proxies even when numerically valid. No footprint IoU is reported without ground geometry.

Reusing the already installed local runtime avoids installation/model-download costs, but version/weight hashes must be retained. CPU timings of this diagnostic script exclude downstream rules, VLM and robot I/O, and cannot be treated as production latency. Any next candidate, ROI collection or VLM stage needs a new explicit contract and directory; never overwrite this history.
