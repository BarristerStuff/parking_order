"""Fail closed downstream authorization. Exit 2 is the expected blocked result."""
import pathlib,json,hashlib
R=pathlib.Path(__file__).resolve().parents[1]
def assess(root=R):
 contract=json.loads((root/'contracts/run_contract.json').read_text())
 rows=[json.loads(x) for x in (root/'01_footprint/footprint_outputs.jsonl').read_text().splitlines()]
 n=len(rows);k=sum(x.get('ground_contact_status')=='validated' and bool(x.get('ground_contact_polygon_image')) for x in rows)
 coverage=k/n if n else None
 # This gate is rejection-only. A future positive authorization requires a new
 # reviewed implementation with input/output hashes and complete target review.
 reasons=['BLOCKED_DIAGNOSTIC_GATE_HAS_NO_PROMOTION_AUTHORITY']
 if not n or coverage<contract['footprint_min_coverage']:reasons.append('BLOCKED_UNRELIABLE_VEHICLE_FOOTPRINT')
 # No completed pixel alignment review was produced for this run.
 review=root/'01_footprint/full_alignment_review.json'
 if not review.exists() or json.loads(review.read_text()).get('all_targets_verified') is not True:reasons.append('BLOCKED_FULL_ALIGNMENT_UNVERIFIED')
 roi=json.loads((root/'02_spatial_evidence/roi_contract.json').read_text())
 if roi.get('status')!='VALIDATED':reasons.append('BLOCKED_SPATIAL_EVIDENCE')
 return {'status':'BLOCKED' if reasons else 'PASS','downstream_authorized':not reasons,'reasons':reasons,'validated_footprint_numerator':k,'detected_target_denominator':n,'coverage':coverage,'threshold':contract['footprint_min_coverage'],'rules_pilot_authorized':not reasons,'vlm_authorized':not reasons,'zero_detection_images_must_not_be_ignored':True}
if __name__=='__main__':
 result=assess();(R/'06_audit/p0_gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['downstream_authorized'] else 2)
