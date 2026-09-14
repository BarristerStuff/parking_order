# Spatial evidence: synthetic tests only

SPATIAL_EVIDENCE_FORMAL_EVALUATION=BLOCKED_NO_TRUSTED_GEOMETRY

No trusted road/bay/gate polygons were supplied for the 60 old AIGC pilot images. No label-informed ROI was drawn; no new AIGC geometry batch was generated. This stage compares detector/footprint, not generation capability. Robot/production data were not searched beyond the explicit allowed historical records.

Ten analytic rectangle cases plus one multi-vehicle OR aggregation were executed: road, adjacent two-bay, line touch, nose/tail, in-bay, normal queue, uncertain, coordinate mismatch, bbox-only abstention, non-adjacent abstention and positive OR. All 11 expectations passed. Fixture polygons and configuration were frozen before execution. These are deterministic code tests, not image classification metrics, segmentation annotations, or camera-calibrated geometry.

The adapter explicitly rejects non-SYNTH image IDs and non-test scope. Underlying image-raster core is a read-only-copy from prior reviewed V5. Source hashes/provenance are in fixture_freeze.json. BEV is unsupported and rejected; trusted synthetic coordinates must not be confused with real validated ground contact. Pilot Recall/FPR/uncertain-rate remain null.
