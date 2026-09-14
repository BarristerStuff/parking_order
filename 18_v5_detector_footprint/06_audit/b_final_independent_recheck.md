# B final independent recheck — 2026-09-10

Status: PASS_B_DIAGNOSTIC_ARTIFACT_CHECKS. Whole run remains PENDING (A final visual audit, 05 integration, final tests and manifest).

## Actually executed
- B 14-entry listed-artifact hash manifest verified; frozen method code and contract payload unchanged.
- 221 R1 source targets / 442 unique target-method rows; source SHA256 76b2f0d1343c68ed32c2c4e608f17d8da27079bfa41bd30b5a39adfe53bd446d.
- All bbox/source/quality/evidence/status aliases joined to original targets and original fields. No ground promotion.
- 442 pure method replay rows equal saved geometry/status/reasons. Independent bbox lower-20% analytic check equal for 221 targets.
- Independent numeric and original exported polygon topology calculations: 221 numeric-valid; 36 topology rejected, including 2 zero-length-edge cases. This does not prove original dense masks failed.
- Mask band: 0 proxy / 185 uncertain / 36 failed; available candidates 170, not 185. Bbox: 176 proxy / 45 uncertain, available 221. Ground validated 0, footprintIoU null.
- Re-ran B suites with application-level side-effect guard: 14 method tests + 8 artifact/schema tests = 22 passed.
- Independent frozen-reference and IoU matching join reproduces all B reference counts. Road support 14: band available 9 / reviewed plausible 2, bbox available 13 / plausible 4. Two-bay support 18: band available 14 / plausible 1, bbox available 16 / plausible 2. These are geometric associations, not confirmed detector matches.

## Visual evidence boundary
20 documented sampled vehicles / 40 reviewed method rows, 201 vehicles unreviewed. B records 6 plausible band proxies and 11 plausible bbox proxies. C checked log/source/index associations, evidence file hashes, review application and unavailable-proxy rejection. C did not decode or independently visually review the pixels and did not independently observe B view_image tool calls. Do not elevate this to independent visual gold, population accuracy, or OS access proof.

The B manifest covers listed artifacts, not every visual media file. C hashes linked visual evidence separately in b_final_audit_result.json. The final whole-run manifest remains pending.

## Integration handoff
B schema adapter is separate from frozen footprint.py, whose hash is unchanged. Updated data_role is latest_completed_R1_diagnostic_NOT_winner. quality.algorithmic.exported_polygon_topology_pass describes the original exported polygon, not the clipped band: an original polygon can pass while its band is unavailable. Ground status mirrors method status and never asserts true ground validation.
