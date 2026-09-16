# V2.2 DEV GT Integrity Repair

- Authorization: `GT_INTEGRITY_REPAIR_AUTHORIZED=true`
- Mode: `RESTORE_CANONICAL_CRLF_BYTES`
- Cause: commit `06af643` normalized the already-frozen CSV from CRLF to LF while the canonical SHA bindings remained unchanged.
- Repair: restored CRLF bytes only.
- Semantic change: **none**. Header, row order, all 238 rows, and every field value were byte-decoded and compared before replacement.
- Canonical SHA256: `413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56`.

This is a line-ending integrity repair. It is not GT migration, relabeling, visual re-adjudication, or post-hoc metric manipulation. R0 was not rerun and no model request was made during repair.
