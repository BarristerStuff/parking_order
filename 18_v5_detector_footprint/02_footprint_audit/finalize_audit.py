"""Reproducible final serialization + reference evaluation, no detector calls.
Requires already produced footprint rows and actual visual-review log.
R1 is the main-authorized latest diagnostic input, NOT a candidate winner.
"""
import json
from footprint import ROOT, digest, freeze_contract
from evaluation import apply_visual_reviews
from serialize_audit import enrich_artifacts

def finalize():
    freeze_contract()
    source=ROOT.parent/'01_detector_audit/r1_targets.jsonl'
    matching=ROOT.parent/'01_detector_audit/r1_matching.jsonl'
    targets=[json.loads(l) for l in source.read_text().splitlines()]
    lookup={(t['image_id'],t['vehicle_id']):t for t in targets}
    joined=set()
    for line in matching.read_text().splitlines():
        image=json.loads(line)
        for det in image['detections']:
            key=(image['image_id'],det['vehicle_id']);t=lookup[key]
            if det['bbox_xyxy']!=t['bbox_xyxy'] or det['raw_detection_id']!=t['raw_detection_id'] or det.get('mask_polygon_image')!=t.get('mask_polygon_image'):
                raise ValueError('matching detection geometry differs from target source')
            joined.add(key)
    if joined!=set(lookup): raise ValueError('matching and targets vehicle sets differ')
    m=apply_visual_reviews(ROOT/'visual_review_log.json',matching)
    if m['source_sha256']!=digest(source): raise ValueError('R1 source hash changed')
    m['reference_evaluation'].update(association_status='geometric_association_only',confirmed_matches=False,
        matching_review_policy='A final reviewed association compared separately by main 05; B does not change matching',
        input_targets_sha256=m['source_sha256'],matching_target_geometry_consistency='exactly checked bbox/raw_id/mask and full vehicle sets')
    m['input_role']='latest_completed_R1_diagnostic_input_NOT_winner'
    m['selection_authority']='Main explicitly authorized completed R1 for diagnostic; not candidate winner claim'
    m['detector_gate_status']='not_claimed_passed; all rows DIAGNOSTIC_ONLY regardless'
    m['allowlist_sha256']=digest(ROOT.parent/'contracts/allowlist.csv')
    m['image_access_verification']={'unique_allowlisted_images_verified_before_decode':60,'checks':['image_id','canonical absolute path','SHA256'],'outside_allowlist_images_read':0}
    (ROOT/'footprint_metrics.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    m=enrich_artifacts()
    rows=[json.loads(l) for l in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
    for r in rows:
        r['data_role']='latest_completed_R1_diagnostic_NOT_winner'
        r['reference_association_status']='geometric_association_only'
    (ROOT/'footprint_outputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
    m['data_role']='latest_completed_R1_diagnostic_NOT_winner'
    (ROOT/'footprint_metrics.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    return m
if __name__=='__main__': print(json.dumps(finalize(),ensure_ascii=False,indent=2))
