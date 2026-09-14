"""Evaluation only: joins A final matching labels; never called by footprint methods.
Counts are reference-instance denominators, not method rows or all detections.
qualitatively_valid means reviewed proxy plausibility ONLY, never ground truth.
"""
import json
from footprint import ROOT, METHODS, digest

def evaluate_references(rows, matching_path):
    lookup={(r['image_id'],r['vehicle_id'],r['method']):r for r in rows}
    result={'matching_source':str(matching_path),'matching_sha256':digest(matching_path),
            'meaning':'qualitatively_valid = visually plausible proxy only, never groundvalidated; available includes uncertain geometry candidates',
            'reference_type':'AI_VISUAL_REVIEWED_PROVISIONAL; not human gold', 'groups':{}}
    matches=[json.loads(s) for s in matching_path.read_text().splitlines() if s.strip()]
    for group,label in [('road','positive_road'),('two_bay','positive_two_bays')]:
        result['groups'][group]={}
        for method in METHODS:
            counts=dict(denominator=0,available=0,qualitatively_valid=0,unavailable=0,
                        available_unreviewed=0,available_reviewed_not_qualitatively_valid=0,unmatched_reference=0)
            for image in matches:
                join={m['reference_index']:m['detection_index'] for m in image['matches']}
                if len(join)!=len(image['matches']) or len(set(join.values()))!=len(join):raise ValueError('matching not one-to-one')
                for ri,ref in enumerate(image['references']):
                    if ref.get('label')!=label: continue
                    counts['denominator']+=1
                    di=join.get(ri)
                    if di is None:
                        counts['unavailable']+=1;counts['unmatched_reference']+=1;continue
                    det=image['detections'][di]
                    vehicle=det.get('vehicle_id',det.get('target_id'))
                    r=lookup.get((image['image_id'],vehicle,method))
                    if r is None: raise ValueError(f'Final matching target absent: {image["image_id"]}/{vehicle}/{method}')
                    available=r['status']!='failed' and bool(r['contact_band_polygon'] if method==METHODS[0] else r['bbox_proxy_polygon'])
                    if not available: counts['unavailable']+=1;continue
                    counts['available']+=1
                    review=r['visual_review']
                    if review['status']=='unreviewed': counts['available_unreviewed']+=1
                    elif review.get('proxy_visual_quality')=='qualitatively_valid_proxy': counts['qualitatively_valid']+=1
                    else: counts['available_reviewed_not_qualitatively_valid']+=1
            result['groups'][group][method]=counts
    return result

def apply_visual_reviews(review_path, matching_path=None):
    """Apply manually authored review evidence. Cannot upgrade geometric status to validated."""
    rows=[json.loads(s) for s in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
    manual=json.loads(review_path.read_text()); source_hash=rows[0]['input_sha256'] if rows else None
    if manual['source_sha256']!=source_hash: raise ValueError('Review source hash differs from final targets')
    reviewed={ (r['image_id'],r['vehicle_id']):r for r in manual['reviews'] }
    if len(reviewed)!=len(manual['reviews']):raise ValueError('Duplicate review')
    validkeys={(r['image_id'],r['vehicle_id']) for r in rows}
    if not set(reviewed).issubset(validkeys): raise ValueError('Review target not in final outputs')
    for r in rows:
        rev=reviewed.get((r['image_id'],r['vehicle_id']))
        if rev:
            q=rev['mask_method_proxy_quality'] if r['method']==METHODS[0] else rev['bbox_method_proxy_quality']
            # Failed/unavailable geometry never becomes a valid proxy through visual review.
            poly=r['contact_band_polygon'] if r['method']==METHODS[0] else r['bbox_proxy_polygon']
            if q=='qualitatively_valid_proxy' and (r['status']=='failed' or not poly): raise ValueError('Cannot visually validate unavailable proxy')
            r['visual_review']={'status':'reviewed_pixels_via_view_image','reviewer':'AI_visual_review_not_human_gold',
                 'mask_visual_quality':rev['mask_visual_quality'], 'contact_band_quality':rev['contact_band_quality'] if r['method']==METHODS[0] else 'not_applicable_bbox_only',
                 'proxy_visual_quality':q,'evidence':rev['evidence'],'observations':rev['observations']}
    (ROOT/'footprint_outputs.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    metrics=json.loads((ROOT/'footprint_metrics.json').read_text())
    metrics['visual_review']={'reviewed_unique_vehicles':len(reviewed),'unreviewed_unique_vehicles':len(validkeys)-len(reviewed),
                             'reviewed_method_rows':len(reviewed)*2,'review_log_sha256':digest(review_path),
                             'note':'Actual view_image review, not geometric heuristics; limited stratified sample, no population extrapolation'}
    for method in METHODS:
        mr=[r for r in rows if r['method']==method]
        metrics['methods'][method]['available']=sum(bool(r['contact_band_polygon'] if method==METHODS[0] else r['bbox_proxy_polygon']) and r['status']!='failed' for r in mr)
        metrics['methods'][method]['visually_qualitatively_valid_proxy']=sum(r['visual_review']['proxy_visual_quality']=='qualitatively_valid_proxy' for r in mr)
        metrics['methods'][method]['unreviewed']=sum(r['visual_review']['status']=='unreviewed' for r in mr)
    if matching_path: metrics['reference_evaluation']=evaluate_references(rows,matching_path)
    (ROOT/'footprint_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return metrics
