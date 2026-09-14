"""Serialization/evaluation-only schema adapter, no change to frozen methods or thresholds.
Reads original R1 targets (never GT), enriches existing derived rows, and reports
exported-polygon representational limits separately from numeric validity.
"""
import json, math
from collections import Counter
from footprint import ROOT, METHODS, digest, area, normalize, polygon_quality, freeze_contract

def enrich_artifacts():
    contract=freeze_contract()
    metrics=json.loads((ROOT/'footprint_metrics.json').read_text())
    from pathlib import Path
    source=Path(metrics['source'])
    if digest(source)!=metrics['source_sha256']: raise ValueError('Target source changed')
    targets=[json.loads(l) for l in source.read_text().splitlines()]
    target_map={(t['image_id'],t['vehicle_id']):t for t in targets}
    rows=[json.loads(l) for l in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
    numeric=[];topology=[];details=[]
    topology_codes={'self_intersection_or_nonadjacent_touch','zero_length_edge'}
    for t in targets:
        raw=t.get('mask_polygon_image');size=t['source_size']
        issues=[];p=None
        try:
            p=normalize(raw)
            finite=bool(p) and all(math.isfinite(v) for xy in p for v in xy)
            in_bounds=finite and all(0<=x<=size[0] and 0<=y<=size[1] for x,y in p)
            positive=finite and len(p)>=3 and math.isfinite(area(p)) and area(p)>0
        except (TypeError,ValueError,OverflowError):finite=in_bounds=positive=False
        nv=bool(finite and in_bounds and positive)
        if p is not None and finite:
            _,issues=polygon_quality(p,*size)
        ti=[i for i in issues if i in topology_codes]
        contours=t.get('mask_contours_image',t.get('mask_contours'))
        if contours is not None and len(contours)!=1:ti.append('multiple_or_missing_contours')
        elif t.get('mask_contour_count',1)!=1:ti.append('reported_multicontour')
        item={'image_id':t['image_id'],'vehicle_id':t['vehicle_id'],
              'exported_mask_present':raw is not None,'finite':finite,'in_bounds':in_bounds,'positive_area':positive,'numeric_valid':nv,
              'exported_polygon_topology_pass':nv and not ti,'topology_issues':ti,
              'original_dense_mask_topology':'unknown_not_exported','component_provenance_available':contours is not None}
        details.append(item);numeric.append(item);topology+=ti
    dm={(d['image_id'],d['vehicle_id']):d for d in details}
    for r in rows:
        t=target_map[(r['image_id'],r['vehicle_id'])];d=dm[(r['image_id'],r['vehicle_id'])]
        r['bbox_xyxy']=t['bbox_xyxy']
        r['footprint_source']='mask_bottom_band' if r['method']==METHODS[0] else 'bbox_lower_proxy'
        r['ground_contact_status']=r['status']
        r['quality']={'algorithmic':{'source':'frozen geometry checks; NOT visual audit',
                          'status':r['status'],'reasons':r['reasons'],
                          'mask_numeric_validity':{k:d[k] for k in ('finite','in_bounds','positive_area','numeric_valid')},
                          'exported_polygon_topology_pass':d['exported_polygon_topology_pass'],
                          'original_dense_mask_topology':'unknown_not_exported',
                          'component_provenance_available':d['component_provenance_available']},
                       'visual':r['visual_review'], 'ground_validated':False}
        r['evidence']={'algorithmic_reasons':r['reasons'],'visual_review':r['visual_review'],
                       'source_target':{'path':str(source),'sha256':metrics['source_sha256'],'image_id':r['image_id'],'vehicle_id':r['vehicle_id']},
                       'bbox_origin':'original detector target; no GT', 'schema_note':'serialization aliases only; frozen method/parameters unchanged'}
    metrics['mask_numeric_validity']={
        'denominator_unique_targets':len(targets),'exported_polygon_present':sum(d['exported_mask_present'] for d in numeric),
        'finite_vertices':sum(d['finite'] for d in numeric),'in_image_bounds':sum(d['in_bounds'] for d in numeric),
        'positive_finite_area':sum(d['positive_area'] for d in numeric),'joint_numeric_valid':sum(d['numeric_valid'] for d in numeric),
        'numeric_invalid_or_missing':sum(not d['numeric_valid'] for d in numeric),
        'meaning':'checks serialized polygon numeric values only, not semantic mask accuracy or physical ground contact'}
    metrics['stricter_polygon_topology_validity']={
        'denominator_unique_targets':len(targets),'exported_polygon_pass':sum(d['exported_polygon_topology_pass'] for d in numeric),
        'exported_polygon_rejected':sum(not d['exported_polygon_topology_pass'] for d in numeric),
        'rejection_reason_counts':dict(Counter(topology)),
        'component_provenance_available':sum(d['component_provenance_available'] for d in numeric),
        'component_provenance_unavailable':sum(not d['component_provenance_available'] for d in numeric),
        'original_dense_mask_topology_unknown':len(targets),
        'meaning':'strict test on exported single polygon; self-touch may arise from flattening multiple original components. Rejection is NOT proof original dense mask failed.',
        'next_stage_requirement':'retain original dense masks and independent contours/component mapping; no detector rerun in this stage'}
    metrics['schema_serialization']={'version':2,'aliases':['bbox_xyxy','footprint_source','ground_contact_status','quality','evidence'],
                  'frozen_method_code_unchanged':True,'frozen_contract_sha256':contract['contract_sha256'],
                  'schema_adapter_sha256':digest(__file__),'detector_rerun':False}
    (ROOT/'footprint_outputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
    (ROOT/'footprint_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'mask_representation_diagnostics.jsonl').write_text(''.join(json.dumps(d)+'\n' for d in details))
    return metrics
if __name__=='__main__':
    m=enrich_artifacts(); print(json.dumps({k:m[k] for k in ('mask_numeric_validity','stricter_polygon_topology_validity','schema_serialization')},indent=2))
