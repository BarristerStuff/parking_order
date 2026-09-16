#!/usr/bin/env python3
import csv,json,hashlib,time,platform,sys,re,random
from pathlib import Path
from collections import Counter
import numpy as np
import cv2, torch, ultralytics
from PIL import Image
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
P0=REPO/'21_parkscope_segmentation_feasibility_p0'
P0_PREDS=P0/'03_inference/parkscope_predictions.jsonl'
WEIGHT=Path('/home/yanbo/net_vlm_parkscope_vendor/ParkScope/yolov11/v11n/best.pt')
WEIGHT_SHA='6d70bf088b7c324401afb97e09cf898afcc639d8ac837f4da7ef4afbc38d3d9b'
RASTER_DIR=ROOT/'_local_rasters'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jdump(p,obj): p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def write_csv(p,rows,fields):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def iou(a,b):
 x1=max(a[0],b[0]); y1=max(a[1],b[1]); x2=min(a[2],b[2]); y2=min(a[3],b[3]); inter=max(0,x2-x1)*max(0,y2-y1)
 aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]); bb=max(0,b[2]-b[0])*max(0,b[3]-b[1]); d=aa+bb-inter
 return inter/d if d else 0.0
def poly_mask(poly,H,W):
 m=np.zeros((H,W),np.uint8)
 if len(poly)>=3: cv2.fillPoly(m,[np.rint(np.asarray(poly)).astype(np.int32)],1)
 return m
def pred_from_result(mid,row,res,elapsed):
 im=Image.open(row['image_path']); W,H=im.size; boxes=res.boxes; masks=res.masks; polys=masks.xy if masks is not None else []
 names={int(k):str(v) for k,v in res.names.items()}; inst=[]
 for idx in range(len(boxes) if boxes is not None else 0):
  cid=int(boxes.cls[idx].item()); poly=np.asarray(polys[idx],dtype=float) if idx<len(polys) else np.empty((0,2))
  inst.append({'media_id':mid,'instance_index':idx,'class_id':cid,'class_name':names.get(cid,str(cid)),
               'confidence':float(boxes.conf[idx].item()),'bbox_xyxy':[float(z) for z in boxes.xyxy[idx].tolist()],
               'mask_polygon':poly.tolist(),'mask_area_pixels':float(cv2.contourArea(poly.astype(np.float32))) if len(poly)>=3 else 0.0,
               'image_width':W,'image_height':H})
 return {'media_id':mid,'image_path':row['image_path'],'image_sha256':row['image_sha256'],'image_width':W,'image_height':H,'runtime_seconds':elapsed,'instances':inst}

def make_raster(pred,target,matched_idx):
 H,W=int(pred['image_height']),int(pred['image_width']); fb=json.loads(target['bbox_xyxy']); x0,y0,x1,y1=fb; w=x1-x0;h=y1-y0
 crop=[max(0.0,x0-w),max(0.0,y0-.75*h),min(float(W),x1+w),min(float(H),y1+.75*h)]
 ix0,iy0,ix1,iy1=int(np.floor(crop[0])),int(np.floor(crop[1])),int(np.ceil(crop[2])),int(np.ceil(crop[3]))
 inst={int(x['instance_index']):x for x in pred['instances']}; tm=poly_mask(inst[matched_idx]['mask_polygon'],H,W)
 geom=np.zeros((H,W),np.uint8); other=np.zeros((H,W),np.uint8)
 for x in pred['instances']:
  cid=int(x['class_id']); idx=int(x['instance_index'])
  if cid in (1,2): geom |= poly_mask(x['mask_polygon'],H,W)
  elif cid==3 and idx!=matched_idx: other |= poly_mask(x['mask_polygon'],H,W)
 def rz(m): return cv2.resize(m[iy0:iy1,ix0:ix1],(96,96),interpolation=cv2.INTER_NEAREST).astype(np.float32)
 c0,c1,c3=rz(tm),rz(geom),rz(other)
 if c1.max()==0: c2=np.ones((96,96),np.float32)
 else:
  c2=cv2.distanceTransform((1-c1).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE).astype(np.float32)
  c2=np.clip(c2,0,24)/24.0
 arr=np.stack([c0,c1,c2,c3]).astype(np.float32)
 return arr,crop

assert sha(WEIGHT)==WEIGHT_SHA
primary=list(csv.DictReader(open(ROOT/'01_dataset/p3_primary_manifest.csv',newline=''))); allowed={r['media_id'] for r in primary}
sealed={r['media_id'] for r in csv.DictReader(open(ROOT/'01_dataset/sealed_eval_exclusion.csv',newline=''))}
assert not allowed & sealed
# Parse P0 records only after checking the leading media_id token; sealed records are never json-decoded or indexed.
reused={}; skipped_sealed=0
pat=re.compile(r'^\{"media_id":"([^"]+)"')
with P0_PREDS.open(encoding='utf-8') as f:
 for line in f:
  m=pat.match(line); assert m
  mid=m.group(1)
  if mid in sealed: skipped_sealed+=1; continue
  if mid in allowed: reused[mid]=json.loads(line)
assert not (set(reused)&sealed)
missing=[r for r in primary if r['media_id'] not in reused]
model=YOLO(str(WEIGHT)); new=[]; errors=[]; t0=time.time()
for n,row in enumerate(missing,1):
 mid=row['media_id']; assert mid not in sealed
 try:
  t=time.perf_counter(); res=model.predict(source=row['image_path'],device='cpu',save=False,verbose=False)[0]
  new.append(pred_from_result(mid,row,res,time.perf_counter()-t))
 except Exception as e: errors.append({'media_id':mid,'error':repr(e)})
 print(f'ParkScope new {n}/{len(missing)}',flush=True)
with open(ROOT/'02_parkscope/parkscope_new_predictions.jsonl','w') as f:
 for x in new:f.write(json.dumps(x,separators=(',',':'))+'\n')
allp=dict(reused); allp.update({x['media_id']:x for x in new})
assert not set(allp)&sealed
reuse_rows=[{'media_id':mid,'source_file':str(P0_PREDS.relative_to(REPO)),'source_sha256':sha(P0_PREDS),'record_status':'REUSED_P0_NONSEALED'} for mid in sorted(reused)]
write_csv(ROOT/'02_parkscope/parkscope_reuse_manifest.csv',reuse_rows,['media_id','source_file','source_sha256','record_status'])
with open(ROOT/'02_parkscope/parkscope_predictions_index.jsonl','w') as f:
 for mid in sorted(allp):
  src='P0_REFERENCE' if mid in reused else 'P3_NEW_JSONL'
  f.write(json.dumps({'media_id':mid,'source':src,'source_path':str(P0_PREDS.relative_to(REPO)) if src=='P0_REFERENCE' else '02_parkscope/parkscope_new_predictions.jsonl','prediction_record_sha256':hashlib.sha256(json.dumps(allp[mid],sort_keys=True,separators=(',',':')).encode()).hexdigest()},separators=(',',':'))+'\n')

trgs=list(csv.DictReader(open(ROOT/'03_target_binding/frozen_target_manifest.csv',newline=''))); binds=[]; manifests=[]; invalid=Counter(); RASTER_DIR.mkdir(exist_ok=True)
for t in trgs:
 mid=t['media_id']; pred=allp.get(mid); fb=json.loads(t['bbox_xyxy']); status='INVALID_TARGET'; reason='NO_PREDICTION'; best=None; center=False
 if pred:
  cands=[x for x in pred['instances'] if int(x['class_id'])==3]
  cx=(fb[0]+fb[2])/2;cy=(fb[1]+fb[3])/2; scored=[]
  for c in cands:
   b=c['bbox_xyxy']; ci=b[0]<=cx<=b[2] and b[1]<=cy<=b[3]
   scored.append((iou(fb,b),float(c['confidence']),(b[2]-b[0])*(b[3]-b[1]),-int(c['instance_index']),c,ci))
  scored.sort(key=lambda z:(-z[0],-z[1],-z[2],-z[3])); best=scored[0] if scored else None
  if best:
   center=best[5]
   if best[0]>=0.10 and center and len(best[4].get('mask_polygon',[]))>=3 and best[4].get('mask_area_pixels',0)>0:
    status='VALID_TARGET';reason='P0_MATCH_RULE_PLUS_FROZEN_RELIABILITY_CHECK'
   else: reason='LOW_IOU_OR_CENTER_OUTSIDE_OR_EMPTY_MASK'
  else: reason='NO_CLASS3_CANDIDATE'
 bind={'media_id':mid,'selected_rank':t['selected_rank'],'frozen_bbox':t['bbox_xyxy'],'matched_instance':'' if not best else best[4]['instance_index'],
       'matched_confidence':'' if not best else best[4]['confidence'],'bbox_iou':'' if not best else best[0],
       'center_inside':'' if not best else center,'match_status':status,'invalid_reason':'' if status=='VALID_TARGET' else reason}
 binds.append(bind)
 if status!='VALID_TARGET':
  invalid[reason]+=1; manifests.append({'media_id':mid,'selected_rank':t['selected_rank'],'target_bbox':t['bbox_xyxy'],'crop_bbox':'','target_instance':'','raster_sha256':'','shape':'','status':'INVALID_TARGET','raster_relpath':''}); continue
 arr,crop=make_raster(pred,t,int(best[4]['instance_index'])); out=RASTER_DIR/f"{mid}__r{int(t['selected_rank']):02d}.npy"; np.save(out,arr,allow_pickle=False)
 manifests.append({'media_id':mid,'selected_rank':t['selected_rank'],'target_bbox':t['bbox_xyxy'],'crop_bbox':json.dumps(crop,separators=(',',':')),
                   'target_instance':best[4]['instance_index'],'raster_sha256':sha(out),'shape':'4x96x96','status':'VALID_TARGET','raster_relpath':str(out.relative_to(ROOT))})
write_csv(ROOT/'03_target_binding/parkscope_target_binding.csv',binds,['media_id','selected_rank','frozen_bbox','matched_instance','matched_confidence','bbox_iou','center_inside','match_status','invalid_reason'])
write_csv(ROOT/'04_relation_rasters/raster_manifest.csv',manifests,['media_id','selected_rank','target_bbox','crop_bbox','target_instance','raster_sha256','shape','status','raster_relpath'])
# Fixed deterministic repeat sample.
valid=[x for x in manifests if x['status']=='VALID_TARGET']; rng=random.Random(20260916); sample=rng.sample(valid,min(20,len(valid))); checks=[]
trgmap={(x['media_id'],x['selected_rank']):x for x in trgs}
for m in sample:
 arr,_=make_raster(allp[m['media_id']],trgmap[(m['media_id'],m['selected_rank'])],int(m['target_instance']))
 tmp=ROOT/'_local_rasters'/'.determinism_tmp.npy';np.save(tmp,arr,allow_pickle=False); got=sha(tmp);tmp.unlink()
 checks.append({'media_id':m['media_id'],'selected_rank':int(m['selected_rank']),'expected_sha256':m['raster_sha256'],'repeat_sha256':got,'match':got==m['raster_sha256']})
det={'seed':20260916,'sample_count':len(checks),'matching_count':sum(x['match'] for x in checks),'pass':len(checks)==20 and all(x['match'] for x in checks),'samples':checks}; jdump(ROOT/'04_relation_rasters/raster_determinism.json',det)
assert det['pass']
tech={'reused_image_count':len(reused),'new_image_count':len(new),'technical_errors':len(errors),'skipped_sealed_p0_records_without_json_parse':skipped_sealed,'unified_success_images':len(allp),'primary_images':len(primary),
      'checkpoint_sha256':sha(WEIGHT),'python_version':platform.python_version(),'torch_version':torch.__version__,'ultralytics_version':ultralytics.__version__,'opencv_version':cv2.__version__,'numpy_version':np.__version__,'device':'cpu','elapsed_seconds':time.time()-t0,
      'effective_predict_args':{k:getattr(model.predictor.args,k,None) for k in ['conf','iou','imgsz','classes','agnostic_nms','augment','device','save','verbose']} if missing and model.predictor else {}}
jdump(ROOT/'02_parkscope/parkscope_integrity.json',tech)
write_csv(ROOT/'02_parkscope/technical_errors.csv',errors,['media_id','error'])
jdump(ROOT/'03_target_binding/binding_summary.json',{'total_targets':len(trgs),'valid_targets':len(valid),'invalid_targets':len(trgs)-len(valid),'invalid_reasons':invalid})
frame_valid=Counter(x['media_id'] for x in valid)
jdump(ROOT/'04_relation_rasters/raster_summary.json',{'raster_shape':'4x96x96','raster_count':len(valid),'valid_target_count':len(valid),'invalid_target_count':len(trgs)-len(valid),'scorable_frames':sum(frame_valid[r['media_id']]>0 for r in primary),'unscorable_frames':sum(frame_valid[r['media_id']]==0 for r in primary)})
print(json.dumps({'parkscope':tech,'targets':{'total':len(trgs),'valid':len(valid),'invalid':len(trgs)-len(valid)},'determinism':det['pass']},indent=2,default=str))
