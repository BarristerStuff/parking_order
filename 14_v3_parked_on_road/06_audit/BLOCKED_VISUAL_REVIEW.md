# BLOCKED_VISUAL_REVIEW

Execution date: 2026-09-09

Full per-vehicle visual review for all 238 old DEV images was not completed in this execution. The overlay CSV includes all DEV detector rows, but non-reviewed rows are intentionally marked `uncertain` with `review_status=BLOCKED_VISUAL_REVIEW`.

- DEV images represented: 238
- DEV vehicle rows represented: 1089
- Pilot reviewed images: 23
- Pilot reviewed vehicle rows: 85
- V3_LABEL_COVERAGE=partial
- PRODUCTION_CLAIM=NOT_AUTHORIZED

No unreviewed row should be treated as v3 human gold.
