#!/usr/bin/env python3
import csv,json,hashlib,math,random
from pathlib import Path
import numpy as np, cv2
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
P0=REPO/'21_parkscope_segmentation_feasibility_p0'; MAN=REPO/'20_v2_3_decomposed_relation/04_pilot/pilot_manifest.csv'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def poly_mask(poly,H,W):
 m=np.zeros((H,W),np.uint8)
 if len(poly)>=3: cv2.fillPoly(m,[np.round(np.array(poly)).astype(np.int32)],1)
 return m
def writecsv(path,rows,fields=None):
 fields=fields or (list(rows[0]) if rows else [])
 with open(path,'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
manifest=list(csv.DictReader(open(MAN,newline=''))); bymid={r['media_id']:r for r in manifest}
# Freeze split before feature/GT joint analysis: only predeclared stratum is used.
seed='20260916_PARKSCOPE_P1_CAL_EVAL'; rng=random.Random(seed); split=[]
for stratum in ['positive_p01','positive_p03','positive_other','negative_ordinary','negative_hard','negative_adjudicated']:
 xs=sorted([r['media_id'] for r in manifest if r['stratum']==stratum]); rng.shuffle(xs)
 assert len(xs)==10
 for i,mid in enumerate(xs): split.append({'media_id':mid,'stratum':stratum,'partition':'CALIBRATION' if i<5 else 'EVALUATION'})
for r in manifest:
 if r['stratum']=='gate_secondary': split.append({'media_id':r['media_id'],'stratum':r['stratum'],'partition':'GATE_SECONDARY'})
split.sort(key=lambda x:int(next(r['order'] for r in manifest if r['media_id']==x['media_id'])))
writecsv(ROOT/'01_input_audit/cal_eval_split.csv',split,['media_id','stratum','partition'])
(ROOT/'01_input_audit/cal_eval_split.csv.sha256').write_text(sha(ROOT/'01_input_audit/cal_eval_split.csv')+'  cal_eval_split.csv\n')
(ROOT/'01_input_audit/split_protocol.json').write_text(json.dumps({'seed':seed,'method':'sorted media_id within each frozen stratum, Python random.Random(seed).shuffle, first 5 CAL, remaining 5 EVAL','counts':{'CALIBRATION':30,'EVALUATION':30,'GATE_SECONDARY':10}},indent=2)+'\n')
preds={x['media_id']:x for x in map(json.loads,open(P0/'03_inference/parkscope_predictions.jsonl'))}
binds=list(csv.DictReader(open(P0/'02_input_audit/selected_vehicle_binding.csv',newline='')))
components=[]; targets=[]
for b in binds:
 mid=b['media_id']; pr=preds[mid]; W,H=pr['image_width'],pr['image_height']; fb=json.loads(b['frozen_bbox']); x0,y0,x1,y1=fb; w=x1-x0;h=y1-y0
 inst={int(x['instance_index']):x for x in pr['instances']}; mi=int(b['matched_instance']) if b['matched_instance']!='' else None
 valid=b['match_status']=='MATCHED' and mi in inst and inst[mi]['class_name'].lower()=='vehicle' and float(b['bbox_iou'] or 0)>=0.10 and b['center_inside'].lower()=='true'
 vm=poly_mask(inst[mi]['mask_polygon'],H,W) if valid else np.zeros((H,W),np.uint8)
 ground=vm.copy(); ground[:max(0,min(H,math.floor(y0+.70*h))),:]=0
 if ground.sum()==0: valid=False
 ys,xs=np.where(ground>0); gp_bbox=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else []
 gp_cent=[float(xs.mean()),float(ys.mean())] if len(xs) else []
 bc=[(x0+x1)/2,y1]; roi=[max(0,x0-w),max(0,y0+.25*h),min(W,x1+w),min(H,y1+.75*h)]
 compids=[]
 for c in pr['instances']:
  if c['class_id'] not in [1,2]: continue
  m=poly_mask(c['mask_polygon'],H,W); rx0,ry0,rx1,ry1=map(lambda z:int(round(z)),roi); inter=m[ry0:ry1,rx0:rx1].sum()
  if inter<=0: continue
  pts=np.column_stack(np.where(m>0)[::-1]).astype(np.float32)
  if len(pts)<3: continue
  mean,evec,evals=cv2.PCACompute2(pts,mean=None); vals=evals.ravel(); order=np.argsort(vals)[::-1]; vals=vals[order]; vec=evec[order][0]; proj=(pts-mean[0])@vec; perp=(pts-mean[0])@np.array([-vec[1],vec[0]])
  length=float(proj.max()-proj.min()); thick=float(perp.max()-perp.min()); elong=length/max(thick,1e-6); tr=thick/w
  area=float(m.sum()); overlap_gp=float((m&ground).sum()/max(ground.sum(),1)); overlap_roi=float(inter/max(area,1)); cx,cy=pts.mean(axis=0)
  dist=abs((np.array(bc)-mean[0])@np.array([-vec[1],vec[0]]))/w
  # support and line/ground bbox relationships
  gx0,gy0,gx1,gy1=gp_bbox if gp_bbox else [0,0,0,0]; center_span=[x0+.25*w,x1-.25*w]
  # signed positions along normal relative to bottom center
  normal=np.array([-vec[1],vec[0]]); signed=float((np.array(bc)-mean[0])@normal)
  intersects_bbox=bool(gp_bbox and dist<=.5*math.hypot(gx1-gx0,gy1-gy0)/w)
  # infinite line x at representative ground centroid y; central if geometrically within central horizontal span
  if abs(vec[1])>1e-6 and gp_cent: x_at=mean[0][0]+(gp_cent[1]-mean[0][1])*vec[0]/vec[1]
  else: x_at=float('inf')
  central=bool(gp_cent and center_span[0]<=x_at<=center_span[1])
  row={'media_id':mid,'selected_rank':b['selected_rank'],'instance_index':c['instance_index'],'original_class_id':c['class_id'],'area':area,'bbox':json.dumps(c['bbox_xyxy'],separators=(',',':')),'centroid_x':float(cx),'centroid_y':float(cy),'pca_axis_x':float(vec[0]),'pca_axis_y':float(vec[1]),'pca_eigenvalue_ratio':float(vals[0]/max(vals[1],1e-9)),'elongation':elong,'estimated_thickness':thick,'thickness_ratio':tr,'orientation_deg':float(math.degrees(math.atan2(vec[1],vec[0]))%180),'support_length':length,'distance_to_bottom_center_normalized':float(dist),'overlap_with_ground_proxy':overlap_gp,'overlap_with_local_roi':overlap_roi,'centroid_vertical_position':float((cy-y0)/h),'line_intersects_ground_proxy_bbox':intersects_bbox,'line_crosses_central_ground_span':central,'visible_support_left_of_vehicle':bool((pts[:,0]<x0).any()),'visible_support_right_of_vehicle':bool((pts[:,0]>x1).any()),'visible_support_above_vehicle_bottom':bool((pts[:,1]<y1).any()),'visible_support_below_vehicle_bottom':bool((pts[:,1]>y1).any()),'bottom_center_inside_area':bool(m[min(H-1,max(0,round(bc[1]-1))),min(W-1,max(0,round(bc[0])))]),'area_near_vehicle':bool(dist<=1.5),'line_point_x':float(mean[0][0]),'line_point_y':float(mean[0][1]),'signed_normal_offset':signed/w}
  components.append(row);compids.append(len(components)-1)
 targets.append({'media_id':mid,'group_key':bymid[mid]['group_key'],'event_label':bymid[mid]['event_label'],'stratum':bymid[mid]['stratum'],'selected_rank':b['selected_rank'],'anchor_status':'ANCHOR_VALID' if valid else 'ANCHOR_INVALID','frozen_bbox':json.dumps(fb,separators=(',',':')),'local_roi':json.dumps(roi,separators=(',',':')),'ground_proxy_area':int(ground.sum()),'ground_proxy_centroid':json.dumps(gp_cent,separators=(',',':')),'ground_proxy_bbox':json.dumps(gp_bbox,separators=(',',':')),'bottom_center':json.dumps(bc,separators=(',',':')),'component_count':len(compids)})
writecsv(ROOT/'02_feature_extraction/geometry_components.csv',components)
writecsv(ROOT/'02_feature_extraction/target_features.csv',targets)
(ROOT/'02_feature_extraction/feature_schema.json').write_text(json.dumps({'geometry_pool':[1,2],'ground_proxy':'bottom 30 percent of matched vehicle mask within frozen bbox y threshold','local_roi_formula':{'left':'x0-1.0w','right':'x1+1.0w','top':'y0+0.25h','bottom':'y1+0.75h'},'anchor_validity':'MATCHED vehicle, bbox IoU>=0.10, frozen center inside candidate bbox, nonempty ground proxy','notes':'Raw components are threshold-independent; classification occurs only in frozen calibration grid.'},indent=2)+'\n')
(ROOT/'00_protocol/frozen_feature_definition.json').write_text(json.dumps({'line_elongation_min':[2.5,3.5,5.0],'line_max_thickness_ratio':[.15,.25,.35],'parallel_angle_max_deg':[15,25,35],'separator_center_margin':[.15,.25,.35],'bracket_max_distance_ratio':[.75,1,1.25],'area_support_min':[.3,.5,.7],'outside_rule':'requires nearby component evidence and no separator, bracket, or area support; zero geometry => uncertain','frame_aggregation':'any positive, else any uncertain, else negative'},indent=2)+'\n')
(ROOT/'01_input_audit/input_integrity.json').write_text(json.dumps({'p0_head':'6da122a5894aab0525a24931a8e677f86cc806e7','p0_predictions_sha256':sha(P0/'03_inference/parkscope_predictions.jsonl'),'p0_binding_sha256':sha(P0/'02_input_audit/selected_vehicle_binding.csv'),'pilot_manifest_sha256':sha(MAN),'images':len(manifest),'targets':len(targets),'parkscope_inference_reused':True,'parkscope_new_requests':0,'ollama_requests':0},indent=2)+'\n')
print({'targets':len(targets),'components':len(components),'invalid':sum(x['anchor_status']=='ANCHOR_INVALID' for x in targets)})
