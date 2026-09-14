# V5 detector and footprint audit

This directory contains the bounded AIGC DEV audit for detector coverage and ground-contact footprint preparation. It reuses 60 V4 pilot images and an AI-reviewed provisional reference; it is not human-gold, real-camera, robot or production evidence.

Current status: `V5_DETECTOR_COVERAGE_BLOCKED`.

- `contracts/`: allowlist, pre-registration, preflight and integrity bindings.
- `01_detector_audit/`: R0/R1 raw detections, matching, visual review and coverage audit.
- `02_footprint_audit/`: two diagnostic proxy methods and qualitative review.
- `03_spatial_evidence/`, `04_rule_engine/`: synthetic fixtures and code tests only.
- `05_evaluation/`: integrated fail-closed metrics; pilot Recall/FPR are null.
- `06_audit/`: independently implemented integrity and denominator checks.
- `tests/`: standard-library test runner.

No VLM/Ollama endpoint was called. No R2, Winner, production candidate or production integration was created.
