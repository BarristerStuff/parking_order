"""Frozen two-method diagnostic proxies. Geometry functions never read labels/images.
API: polygon_quality(points, width, height), bottom_contact_band(target, width,
height), bbox_lower_proxy(target, width, height), process_target(target,width,height).
No physical ground contact is inferred. No mask dilation or contour merging.
"""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
import argparse, csv, hashlib, json, math
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parent
os.environ['TMPDIR'] = str(ROOT/'runtime')
os.environ['XDG_CACHE_HOME'] = str(ROOT/'runtime/cache')
METHODS = ('mask_bottom_contact_band', 'bbox_lower_conservative_proxy')
PARAMETERS = {'bottom_fraction': .2, 'epsilon': 1e-9, 'bbox_mask_tolerance_pixels': 2.,
              'minimum_mask_bbox_extent_iou': .8, 'minimum_mask_fill_ratio': .1,
              'edge_truncation_pixels': 1., 'multiple_contours_policy': 'reject_candidate_never_merge',
              'disconnected_band_policy': 'reject_candidate_never_bridge',
              'missing_contour_provenance_policy': 'uncertain'}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def area(p):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1])))/2 if p else 0.

def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def intersects(a,b,c,d):
    e=PARAMETERS['epsilon']
    if max(a[0],b[0])+e < min(c[0],d[0]) or max(c[0],d[0])+e < min(a[0],b[0]) or max(a[1],b[1])+e < min(c[1],d[1]) or max(c[1],d[1])+e < min(a[1],b[1]): return False
    x,y,z,w=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    return ((x>e and y < -e) or (y>e and x < -e) or abs(x)<=e or abs(y)<=e) and ((z>e and w < -e) or (w>e and z < -e) or abs(z)<=e or abs(w)<=e)

def normalize(points):
    p=[[float(x),float(y)] for x,y in points]
    if len(p)>1 and p[0]==p[-1]: p.pop()
    return p

def polygon_quality(points, width, height):
    issues=[]
    try: p=normalize(points)
    except (ValueError,TypeError,OverflowError): return None,['invalid_polygon_format']
    if len(p)<3: return None,['insufficient_vertices']
    if not all(math.isfinite(v) for xy in p for v in xy): return None,['nonfinite_polygon']
    if area(p)<=PARAMETERS['epsilon']: issues.append('nonpositive_area')
    if any(x<0 or y<0 or x>width or y>height for x,y in p): issues.append('out_of_bounds')
    n=len(p)
    for i in range(n):
        if p[i]==p[(i+1)%n]: issues.append('zero_length_edge'); break
    found=False
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1): continue
            if intersects(p[i],p[(i+1)%n],p[j],p[(j+1)%n]):
                issues.append('self_intersection_or_nonadjacent_touch'); found=True; break
        if found: break
    return p,issues

def bbox_quality(b,width,height):
    try:
        x1,y1,x2,y2=map(float,b)
        if not all(math.isfinite(v) for v in (x1,y1,x2,y2)): return None,['nonfinite_bbox']
    except (ValueError,TypeError,OverflowError): return None,['invalid_bbox']
    if x2<=x1 or y2<=y1: return None,['nonpositive_bbox']
    issues=[]
    if x1<0 or y1<0 or x2>width or y2>height: issues.append('bbox_out_of_bounds')
    return [x1,y1,x2,y2],issues

def base(target, method):
    return dict(image_id=target['image_id'], vehicle_id=target['vehicle_id'],
                raw_detection_id=target.get('raw_detection_id'),method=method,
                status='failed', reasons=[], visible_mask_polygon=None,
                contact_band_polygon=None,ground_contact_candidate=None,
                ground_contact_polygon=None, bbox_proxy_polygon=None,
                footprintIoU=None,ground_validated=False, scope='DIAGNOSTIC_ONLY',
                visual_review={'status':'unreviewed','mask_visual_quality':'unreviewed',
                               'contact_band_quality':'unreviewed','proxy_visual_quality':'unreviewed'},
                coordinate_space='image')

def truncation(b,width,height):
    e=PARAMETERS['edge_truncation_pixels']
    return b[0]<=e or b[1]<=e or b[2]>=width-e or b[3]>=height-e

def clip_bottom(p, cutoff):
    # Sutherland-Hodgman is only used when at most one entering interval exists;
    # otherwise it can spuriously bridge disconnected components of a concavity.
    transitions=sum(a[1]<cutoff and b[1]>=cutoff for a,b in zip(p,p[1:]+p[:1]))
    if transitions>1: return None,['band_may_be_disconnected']
    out=[]
    for a,b in zip(p,p[1:]+p[:1]):
        ai,bi=a[1]>=cutoff,b[1]>=cutoff
        if ai != bi:
            t=(cutoff-a[1])/(b[1]-a[1]); out.append([a[0]+t*(b[0]-a[0]),cutoff])
        if bi: out.append(b[:])
    clean=[]
    for pt in out:
        if not clean or pt!=clean[-1]: clean.append(pt)
    if len(clean)>1 and clean[0]==clean[-1]: clean.pop()
    return clean,[]

def bottom_contact_band(target,width,height):
    r=base(target,METHODS[0]); b,bi=bbox_quality(target.get('bbox_xyxy'),width,height)
    if b is None or bi: r['reasons']=bi; return r
    contours=target.get('mask_contours_image',target.get('mask_contours'))
    provenance_known=contours is not None
    if contours is not None:
        if len(contours)!=1:
            r.update(status='uncertain' if len(contours)>1 else 'failed',reasons=['multiple_contours' if len(contours)>1 else 'missing_mask']);return r
        raw=contours[0]
    else: raw=target.get('mask_polygon_image', target.get('visible_mask_polygon'))
    if not raw: r['reasons']=['missing_mask'];return r
    p,issues=polygon_quality(raw,width,height)
    if issues: r['reasons']=issues;return r
    r['visible_mask_polygon']=p
    reasons=[]
    if not provenance_known: reasons.append('contour_provenance_unknown')
    if target.get('mask_contour_count',1)!=1: reasons.append('reported_fragmentation')
    if any(target.get(k) for k in ('truncated','is_truncated','fragmented','mask_fragmented')): reasons.append('source_quality_flag')
    mb=[min(v[0] for v in p),min(v[1] for v in p),max(v[0] for v in p),max(v[1] for v in p)]
    tol=PARAMETERS['bbox_mask_tolerance_pixels']
    if mb[0]<b[0]-tol or mb[1]<b[1]-tol or mb[2]>b[2]+tol or mb[3]>b[3]+tol: reasons.append('mask_outside_bbox')
    inter=max(0,min(b[2],mb[2])-max(b[0],mb[0]))*max(0,min(b[3],mb[3])-max(b[1],mb[1]))
    ba=(b[2]-b[0])*(b[3]-b[1]); ma=(mb[2]-mb[0])*(mb[3]-mb[1])
    if inter/(ba+ma-inter)<PARAMETERS['minimum_mask_bbox_extent_iou']: reasons.append('mask_bbox_extent_inconsistent')
    if area(p)/ba < PARAMETERS['minimum_mask_fill_ratio']: reasons.append('small_fragment_or_thin_mask')
    if truncation(b,width,height) or truncation(mb,width,height): reasons.append('edge_truncation_risk')
    cutoff=mb[3]-PARAMETERS['bottom_fraction']*(mb[3]-mb[1])
    band,ci=clip_bottom(p,cutoff)
    if band is not None:
        band,ci=polygon_quality(band,width,height)
    reasons+=ci
    if ci or 'reported_fragmentation' in reasons:
        r.update(status='uncertain',reasons=reasons);return r
    r.update(contact_band_polygon=band,ground_contact_candidate=band,
             status='uncertain' if reasons else 'proxy', reasons=reasons or ['visible_bottom_band_is_only_proxy'])
    return r

def bbox_lower_proxy(target,width,height):
    r=base(target,METHODS[1]);b,issues=bbox_quality(target.get('bbox_xyxy'),width,height)
    if b is None or issues: r['reasons']=issues;return r
    x1,y1,x2,y2=b; cut=y2-PARAMETERS['bottom_fraction']*(y2-y1)
    p=[[x1,cut],[x2,cut],[x2,y2],[x1,y2]]
    issues=[]
    if truncation(b,width,height): issues.append('edge_truncation_risk')
    if target.get('truncated') or target.get('is_truncated'): issues.append('source_truncation_flag')
    r.update(bbox_proxy_polygon=p,status='uncertain' if issues else 'proxy',reasons=issues or ['bbox_lower_region_not_a_footprint'])
    return r

def process_target(target,width,height):
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (width,height)): raise ValueError('invalid image dimensions')
    return [bottom_contact_band(target,width,height),bbox_lower_proxy(target,width,height)]

def freeze_contract():
    path=ROOT/'footprint_contract.json'
    payload={'schema_version':1,'methods':list(METHODS),'parameters':PARAMETERS,
             'labels_in_method':False,'ground_contact_polygon':'always null','footprintIoU':'always null; no geometry GT',
             'scope':'DIAGNOSTIC_ONLY; no spatial classification',
             'final_source_policy':'A selected r0/r1_targets.jsonl only; no fallback to 17',
             'code_sha256':digest(__file__),'run_contract_sha256':digest(ROOT.parent/'contracts/run_contract.json')}
    payload['contract_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if path.exists():
        old=json.loads(path.read_text())
        if old!=payload: raise RuntimeError('Frozen contract mismatch; do not overwrite')
    else: path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    return payload

def verified_image(image_id, allowlist=None):
    """Verify ID, canonical absolute path, SHA256 before decoding any allowlisted image."""
    from PIL import Image
    allowlist=Path(allowlist or ROOT.parent/'contracts/allowlist.csv')
    records=list(csv.DictReader(allowlist.open()))
    hits=[r for r in records if r['image_id']==image_id]
    if len(hits)!=1: raise ValueError('image ID absent or duplicated in allowlist')
    r=hits[0];p=Path(r['absolute_path'])
    if not p.is_absolute() or p.resolve()!=p or p.stem!=image_id: raise ValueError('ID/path mismatch')
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=r['image_sha256']: raise ValueError('image hash mismatch')
    import io
    im=Image.open(io.BytesIO(data)); im.load()
    return im.convert('RGB')

def run(source, development=False):
    contract=freeze_contract();source=Path(source).resolve()
    if not development and (source.parent!=ROOT.parent/'01_detector_audit' or source.name not in ('r0_targets.jsonl','r1_targets.jsonl')):
        raise ValueError('Final targets must be A r0/r1 targets; selection evidence required by orchestrator')
    targets=[json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    keys=[(t['image_id'],t['vehicle_id']) for t in targets]
    if len(set(keys))!=len(keys): raise ValueError('duplicate vehicle IDs')
    sizes={};rows=[]
    for t in targets:
        if t['image_id'] not in sizes: sizes[t['image_id']]=verified_image(t['image_id']).size
        for r in process_target(t,*sizes[t['image_id']]):
            r.update(input_source=str(source),input_sha256=digest(source),contract_sha256=contract['contract_sha256'],
                     data_role='development_sanity_NOT_final' if development else 'final_selected_detector_diagnostic')
            rows.append(r)
    prefix='development_' if development else ''
    (ROOT/(prefix+'footprint_outputs.jsonl')).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    metrics={'data_role':'development_sanity_NOT_final' if development else 'final_selected_detector_diagnostic',
             'source':str(source),'source_sha256':digest(source),'unique_vehicles':len(targets),'method_rows':len(rows),
             'image_count':len(sizes),'footprintIoU':None,'ground_validated':0,'scope':'DIAGNOSTIC_ONLY',
             'methods':{m:{'denominator':len(targets),'status_counts':{s:sum(r['method']==m and r['status']==s for r in rows) for s in ('validated','proxy','uncertain','failed')},
                           'reason_counts':dict(Counter(s for r in rows if r['method']==m for s in r['reasons']))} for m in METHODS},
             'visual_review':{'reviewed_unique_vehicles':0,'unreviewed_unique_vehicles':len(targets)},
             'reference_evaluation':{'status':'pending_A_final_matches; no labels read by methods'}}
    (ROOT/(prefix+'footprint_metrics.json')).write_text(json.dumps(metrics,indent=2)+'\n')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--development',action='store_true');p.add_argument('--freeze',action='store_true');a=p.parse_args()
    if a.freeze: print(json.dumps(freeze_contract(),indent=2))
    if a.source: print(json.dumps(run(a.source,a.development),indent=2))
