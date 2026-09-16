# v2.2 180-image collection plan

Status: **PLAN_ONLY; images unavailable**. No model evaluation may use this manifest until images are generated/acquired, visually reviewed, and challenge GT/split manifests are frozen with hashes.

Seed: `20260916_V22_FINAL_CHALLENGE`. Total 180: positive 75, negative 75, uncertain 30. Scenario groups are kept within one split by deterministic assignment; generation intent is not GT. All positive images and boundary negatives N22_02/N22_03/N22_06 require visual review; unresolved items enter human review queue.

The CSV contains one complete prompt row per planned image, provenance placeholders (`generation_model=TBD` until generation), stable seed, date, and split.
