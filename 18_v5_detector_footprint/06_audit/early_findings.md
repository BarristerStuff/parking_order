# C independent early findings

## Verified
- protected_before: 1121/1121 hashes equal; expected keyset reconstructed from 17, no missing keys in current snapshot.
- 17 manifest: 115/115; 16 reference freeze: 8/8. 60 allowlisted originals hashed only, no pixel decoding.
- Matching independently recomputed with descending IoU >= .5, reference-index/detection-index ties, labels not passed into matcher.
- R0: 196 raw / 195 kept / 155 geometric matches; R1: 222 raw / 221 kept / 178 geometric matches.
- Frozen support: overall 240, road 14, two bays 18. R1 geometric upper bound 178/240 and 16/18 already below .90; detector gate cannot pass even if all those matches are visually confirmed.
- R1 config changes only classes. Evidence chronology and visual reviews require final checks.
- Production git porcelain equals baseline, which was already dirty. Protected snapshot hashes additionally checked; this is not proof for untracked/unprotected content.

## Code/evidence limitations to address in reports
1. contracts/preflight.py filters protected files with is_file(); missing paths could be silently omitted. Current independent keyset comparison passes, so this is a preventive robustness issue, not an observed missing file.
2. A run_detector.py socket monkeypatch is application-level only (not OS sandbox, not all possible connection APIs). runtime network='blocked' is not a proof of no physical network activity.
3. A completion counts are constants 60. Auditor independently checks raw, kept, matching, log image sets and counts, rather than trusting completion JSON.
4. A reference geometry is joined from frozen 16 adapted_inputs, not contained in reference_instances. Auditor checks exact join and immutable source hashes, and never uses labels to create matches.
5. B final source policy is documented as selected R0/R1, but run() alone only checks source basename/parent; orchestrator selection must be verified separately. Development output from 17 must never be promoted as final 18 output.
6. B verified_image hashes bytes then decodes those bytes (good); A checked_image hashes a path then reopens it (TOCTOU window). The current snapshot hash check cannot exclude concurrent replacement during that gap. This does not establish any actual replacement.
7. Rule metrics are explicitly synthetic only and formal recalls/FPR are null. Synthetic pass count cannot establish pilot accuracy.

## Pending
A completed per-match visual evidence, B final selected-detector outputs/review, main evaluation and test evidence, manifest. No final acceptance is given by this interim memo.
