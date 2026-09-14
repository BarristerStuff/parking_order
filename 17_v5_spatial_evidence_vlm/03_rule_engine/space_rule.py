"""Image-raster diagnostic geometry, never infer missing ROI or ground contact.
BEV intentionally unsupported; arbitrary image polygons supported after validation.
"""
import json, math
from pathlib import Path
import cv2
import numpy as np
CONFIG=json.loads(Path(__file__).with_name('rule_config.json').read_text())
POS={'positive_road','positive_two_bays'}
NEG={'negative_in_bay','negative_line_touch_or_minor_overrun','negative_nose_tail_overhang','negative_gate_queue'}

def polygon_mask(poly,size):
 w,h=size
 if not isinstance(w,int) or not isinstance(h,int) or not 0<w<=8192 or not 0<h<=8192:raise ValueError('IMAGE_SIZE_INVALID')
 a=np.array(poly,dtype=float)
 if a.ndim!=2 or a.shape[0]<3 or a.shape[1]!=2 or not np.isfinite(a).all():raise ValueError('POLYGON_INVALID')
 if (a<0).any() or (a[:,0]>w).any() or (a[:,1]>h).any():raise ValueError('OUT_OF_BOUNDS')
 # Reject proper crossing of non-neighbouring edges; repeated vertices also invalid.
 if len(set(map(tuple,a)))!=len(a):raise ValueError('REPEATED_VERTEX')
 def cross(a,b,c):return float((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
 for i in range(len(a)):
  for j in range(i+1,len(a)):
   if j==i+1 or (i==0 and j==len(a)-1):continue
   p,q=a[i],a[(i+1)%len(a)];r,s=a[j],a[(j+1)%len(a)]
   if cross(p,q,r)*cross(p,q,s)<=0 and cross(r,s,p)*cross(r,s,q)<=0:
    if np.all(np.maximum(np.minimum(p,q),np.minimum(r,s))<=np.minimum(np.maximum(p,q),np.maximum(r,s))):raise ValueError('SELF_INTERSECTION')
 if abs(cv2.contourArea(a.astype(np.float32)))<=CONFIG['epsilon']:raise ValueError('ZERO_AREA')
 out=np.zeros((h,w),np.uint8);cv2.fillPoly(out,[np.rint(a).astype(np.int32)],1);return out.astype(bool)

def build_spatial_evidence(vehicle,roi_config):
 e={'image_id':vehicle.get('image_id'),'vehicle_id':vehicle.get('vehicle_id'),'coordinate_space':vehicle.get('coordinate_space'),'footprint_source':vehicle.get('footprint_source','none'),'road_overlap_ratio':None,'parking_area_overlap_ratio':None,'bay_overlaps':[],'best_bay_ratio':None,'second_bay_ratio':None,'two_bay_total_ratio':None,'gate_queue_overlap_ratio':None,'geometry_quality':'unavailable','evidence_status':'uncertain','evidence_reason':'ROI_MISSING','ground_contact_validated':vehicle.get('ground_contact_status')=='validated' and vehicle.get('footprint_source')=='ground_contact' and bool(vehicle.get('ground_contact_polygon_image')),'best_pair_adjacent':False}
 if not roi_config:return e
 try:
  if vehicle.get('coordinate_space')!='image' or roi_config.get('coordinate_space')!='image':raise ValueError('COORDINATE_SPACE_UNSUPPORTED_OR_MISMATCH')
  if roi_config.get('validation_status') not in {'VALIDATED','SYNTHETIC_UNIT_TEST_ONLY'}:raise ValueError('ROI_NOT_VALIDATED')
  if not vehicle.get('image_id') or vehicle.get('image_id')!=roi_config.get('image_id') or not vehicle.get('source_sha256') or vehicle.get('source_sha256')!=roi_config.get('source_sha256'):raise ValueError('ROI_IMAGE_BINDING_MISMATCH')
  if vehicle.get('image_size')!=roi_config.get('image_size'):raise ValueError('ROI_IMAGE_SIZE_MISMATCH')
  size=roi_config['image_size'];fp=vehicle.get('ground_contact_polygon_image') or vehicle.get('mask_polygon_image') or vehicle.get('bbox_lower_polygon_image');m=polygon_mask(fp,size);den=int(m.sum())
  if den==0:raise ValueError('ZERO_AREA')
  def overlap(polys):
   u=np.zeros_like(m)
   for p in polys:u|=polygon_mask(p,size)
   return float((m & u).sum()/den)
  areas=roi_config.get('areas',{})
  # None = missing, [] = explicitly calibrated absence.
  for name,key in [('road','road_overlap_ratio'),('parking_area','parking_area_overlap_ratio'),('gate_queue','gate_queue_overlap_ratio')]:
   e[key]=overlap(areas[name]) if name in areas else None
  bays=roi_config.get('bays',[]);ids=[b['bay_id'] for b in bays]
  if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_BAY_ID')
  edges={frozenset(x) for x in roi_config.get('adjacent_pairs',[])}
  if any(len(x)!=2 or not x.issubset(ids) for x in edges):raise ValueError('ADJACENCY_INVALID')
  ranked=sorted([{'bay_id':b['bay_id'],'overlap_ratio':overlap([b['polygon']])} for b in bays],key=lambda b:(-b['overlap_ratio'],b['bay_id']))
  best=ranked[0]['bay_id'] if ranked else None
  for b in ranked:b['is_adjacent_to_vehicle_best_bay']=frozenset([best,b['bay_id']]) in edges
  e['bay_overlaps']=ranked;e['best_bay_ratio']=ranked[0]['overlap_ratio'] if ranked else 0;e['second_bay_ratio']=ranked[1]['overlap_ratio'] if len(ranked)>1 else 0
  e['best_pair_adjacent']=len(ranked)>1 and ranked[1]['is_adjacent_to_vehicle_best_bay']
  selected={x['bay_id'] for x in ranked[:2]};e['two_bay_total_ratio']=overlap([b['polygon'] for b in bays if b['bay_id'] in selected])
  # Raster shared boundary may overlap <= 1 pixel; never use sum as union.
  e.update(geometry_quality='clear',evidence_status='clear',evidence_reason='IMAGE_RASTER_DIAGNOSTIC_ONLY')
 except (ValueError,KeyError,TypeError,IndexError) as ex:e.update(geometry_quality='invalid',evidence_status='failed',evidence_reason=str(ex))
 return e

def decide_from_spatial_evidence(e,context):
 def d(label,reason):return {'image_id':e.get('image_id'),'vehicle_id':e.get('vehicle_id'),'label':label,'alert':label in POS,'reason_code':reason}
 if e.get('evidence_status')!='clear':return d('uncertain',e.get('evidence_reason','INSUFFICIENT_EVIDENCE'))
 if e.get('footprint_source')!='ground_contact' or not e.get('ground_contact_validated'):return d('uncertain','UNVALIDATED_FOOTPRINT')
 keys=['road_overlap_ratio','best_bay_ratio','second_bay_ratio','two_bay_total_ratio','gate_queue_overlap_ratio']
 if any(not isinstance(e.get(k),(int,float)) or not math.isfinite(e[k]) or not 0<=e[k]<=1 for k in keys):return d('uncertain','MISSING_OR_INVALID_OVERLAP')
 r,b,s,total,g=[e[k] for k in keys];q=context.get('normal_gate_queue','unclear')
 if q=='yes' and g>=CONFIG['gate_queue_overlap_ratio']:return d('negative_gate_queue','CONFIRMED_GATE_QUEUE_PRIORITY')
 if q!='no' or g>=CONFIG['gate_queue_overlap_ratio']:return d('uncertain','GATE_QUEUE_UNCLEAR_OR_CONFLICT')
 road=r>=CONFIG['road_overlap_ratio'];two=e.get('best_pair_adjacent') and min(b,s)>=CONFIG['two_bay_each_overlap_ratio'] and total>=CONFIG['two_bay_total_overlap_ratio']
 inside=b>=CONFIG['in_bay_overlap_ratio']
 if road and (inside or two):return d('uncertain','RULE_CONFLICT')
 if road:return d('positive_road','ROAD_CLEAR')
 if two:return d('positive_two_bays','ADJACENT_TWO_BAYS_CLEAR')
 if inside and r<=CONFIG['max_road_for_negative']:
  side=context.get('boundary_relation','unclear')
  if side=='minor_side' and s<=CONFIG['minor_overrun_second_bay_max_ratio']:return d('negative_line_touch_or_minor_overrun','MINOR_SIDE_CONFIRMED')
  if side=='nose_tail' and 1-b<=CONFIG['nose_tail_overhang_max_outside_ratio']:return d('negative_nose_tail_overhang','NOSE_TAIL_CONFIRMED')
  if side=='inside':return d('negative_in_bay','IN_BAY_CLEAR')
 return d('uncertain','RELATION_INSUFFICIENT')

def aggregate_image_decision(decisions, *, detector_complete=False):
 if not decisions and not detector_complete:return {'label':'uncertain','alert':False,'reason_code':'DETECTION_COMPLETENESS_UNVERIFIED'}
 labels=[d['label'] for d in decisions if d['label']!='ignore']
 if any(x in POS for x in labels):label='positive'
 elif any(x not in NEG for x in labels):label='uncertain'
 elif labels:label='negative'
 else:label='ignore'
 return {'label':label,'alert':label=='positive'}
