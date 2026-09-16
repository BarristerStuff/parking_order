import csv,json,hashlib,time,platform,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import cv2,torch,ultralytics
from ultralytics import YOLO
ROOT=Path(__file__).resolve().parents[2];P0=Path(__file__).resolve().parents[1]
UP=Path('/home/yanbo/net_vlm_parkscope_vendor/ParkScope');WEIGHT=UP/'yolov11/v11n/best.pt';MAN=ROOT/'20_v2_3_decomposed_relation/04_pilot/pilot_manifest.csv';ANCH=ROOT/'20_v2_3_decomposed_relation/04_pilot/predictions.jsonl'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(MAN)=='be44f0a84221fd54c018a80fe74f0fe8be9a5a50b5bd068bd3651b3db9a4b3c3';assert sha(WEIGHT)=='6d70bf088b7c324401afb97e09cf898afcc639d8ac837f4da7ef4afbc38d3d9b'
man=list(csv.DictReader(open(MAN,newline=''))); anchors={r['media_id']:r for r in map(json.loads,open(ANCH))};assert len(man)==70 and sum(len(anchors[r['media_id']]['vehicles']) for r in man)==89
model=YOLO(str(WEIGHT)); names={int(k):str(v) for k,v in model.names.items()};start=time.time();predout=[];instrows=[];errors=[];matchrows=[]
colors={0:(255,165,0),1:(255,0,255),2:(0,180,255),3:(0,255,0)}
def iou(a,b):
 x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3]);inter=max(0,x2-x1)*max(0,y2-y1);aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1]);return inter/(aa+bb-inter) if aa+bb-inter else 0
for n,m in enumerate(man,1):
 mid=m['media_id'];path=m['image_path']
 try:
  t=time.perf_counter();res=model.predict(source=path,device='cpu',save=False,verbose=False)[0];elapsed=time.perf_counter()-t
  im=np.asarray(Image.open(path).convert('RGB'));H,W=im.shape[:2];overlay=im.copy();instances=[]
  boxes=res.boxes; masks=res.masks
  polys=masks.xy if masks is not None else []
  for idx in range(len(boxes) if boxes is not None else 0):
   cid=int(boxes.cls[idx].item());conf=float(boxes.conf[idx].item());box=[float(x) for x in boxes.xyxy[idx].tolist()];poly=np.asarray(polys[idx],dtype=float) if idx<len(polys) else np.empty((0,2));area=float(cv2.contourArea(poly.astype(np.float32))) if len(poly)>=3 else 0.0
   rec={'media_id':mid,'instance_index':idx,'class_id':cid,'class_name':names.get(cid,str(cid)),'confidence':conf,'bbox_xyxy':box,'mask_polygon':poly.tolist(),'mask_area_pixels':area,'image_width':W,'image_height':H};instances.append(rec);instrows.append({k:(json.dumps(v,separators=(',',':')) if isinstance(v,list) else v) for k,v in rec.items()})
   if len(poly)>=3:
    pts=np.round(poly).astype(np.int32);layer=overlay.copy();cv2.fillPoly(layer,[pts],colors.get(cid,(255,255,255)));overlay=cv2.addWeighted(layer,.32,overlay,.68,0);cv2.polylines(overlay,[pts],True,colors.get(cid,(255,255,255)),2)
   cv2.rectangle(overlay,(round(box[0]),round(box[1])),(round(box[2]),round(box[3])),colors.get(cid,(255,255,255)),2);cv2.putText(overlay,f'{idx}:{cid} {names.get(cid,cid)} {conf:.2f}',(round(box[0]),max(18,round(box[1])-4)),cv2.FONT_HERSHEY_SIMPLEX,.5,colors.get(cid,(255,255,255)),2,cv2.LINE_AA)
  # frozen target boxes and deterministic class-name vehicle binding
  candidates=[x for x in instances if x['class_name'].strip().lower()=='vehicle']
  for v in anchors[mid]['vehicles']:
   rank=int(v['rank']);fb=[float(x) for x in v['bbox']];cx=(fb[0]+fb[2])/2;cy=(fb[1]+fb[3])/2
   scored=[]
   for c in candidates:
    b=c['bbox_xyxy'];scored.append((iou(fb,b),c['confidence'],(b[2]-b[0])*(b[3]-b[1]),-c['instance_index'],c,cx>=b[0] and cx<=b[2] and cy>=b[1] and cy<=b[3]))
   scored.sort(key=lambda z:(-z[0],-z[1],-z[2],-z[3]));best=scored[0] if scored else None
   ties=sum(abs(z[0]-best[0])<1e-12 and abs(z[1]-best[1])<1e-12 and abs(z[2]-best[2])<1e-9 for z in scored) if best else 0
   status='NO_VEHICLE_MASK' if not best else ('AMBIGUOUS_MATCH' if ties>1 else 'MATCHED')
   matchrows.append({'media_id':mid,'selected_rank':rank,'frozen_bbox':json.dumps(fb,separators=(',',':')),'matched_instance':'' if not best else best[4]['instance_index'],'matched_class':'' if not best else best[4]['class_name'],'matched_conf':'' if not best else best[4]['confidence'],'bbox_iou':'' if not best else best[0],'center_inside':'' if not best else best[5],'mask_area':'' if not best else best[4]['mask_area_pixels'],'match_status':status})
   cv2.rectangle(overlay,(round(fb[0]),round(fb[1])),(round(fb[2]),round(fb[3])),(255,0,0),4);cv2.putText(overlay,f'FROZEN TARGET {rank}',(round(fb[0]),min(H-5,round(fb[3])+20)),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,0,0),2,cv2.LINE_AA)
  Image.fromarray(overlay).save(P0/'_local_overlays'/f'{mid}_overlay.jpg',quality=90)
  predout.append({'media_id':mid,'image_path':path,'image_sha256':m['image_sha256'],'image_width':W,'image_height':H,'runtime_seconds':elapsed,'instances':instances})
 except Exception as e:errors.append({'media_id':mid,'image_path':path,'error':repr(e)})
 print(f'{n}/70',flush=True)
with open(P0/'03_inference/parkscope_predictions.jsonl','w') as f:
 for x in predout:f.write(json.dumps(x,separators=(',',':'))+'\n')
fields=['media_id','instance_index','class_id','class_name','confidence','bbox_xyxy','mask_polygon','mask_area_pixels','image_width','image_height']
with open(P0/'03_inference/parkscope_instance_summary.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(instrows)
with open(P0/'02_input_audit/selected_vehicle_binding.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=matchrows[0],lineterminator='\n');w.writeheader();w.writerows(matchrows)
with open(P0/'03_inference/technical_errors.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=['media_id','image_path','error'],lineterminator='\n');w.writeheader();w.writerows(errors)
counts={str(i):sum(x['class_id']==i for x in instrows) for i in range(4)};imgs={str(i):len({x['media_id'] for x in instrows if x['class_id']==i}) for i in range(4)}
(P0/'03_inference/parkscope_class_summary.json').write_text(json.dumps({'runtime_model_names':names,'instance_counts':counts,'image_counts':imgs},indent=2)+'\n')
args={k:getattr(model.predictor.args,k,None) for k in ['conf','iou','imgsz','classes','agnostic_nms','augment','device','save','verbose']}
(P0/'03_inference/parkscope_runtime.json').write_text(json.dumps({'python_version':platform.python_version(),'torch_version':torch.__version__,'ultralytics_version':ultralytics.__version__,'opencv_version':cv2.__version__,'pillow_version':Image.__version__ if hasattr(Image,'__version__') else None,'device':'cpu','effective_predictor_args':args,'started_epoch':start,'finished_epoch':time.time(),'total_seconds':time.time()-start,'success_images':len(predout),'technical_error_count':len(errors)},indent=2)+'\n')
print(json.dumps({'success':len(predout),'errors':len(errors),'instances':counts,'images':imgs,'names':names,'args':args},indent=2))
