"""Offline, GT-blind full-image segmentation. All writes confined to V5."""
import os,sys,pathlib,json,csv,time,hashlib,socket
R=pathlib.Path(__file__).resolve().parents[1]; S=pathlib.Path('/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/runtime_snapshot')
sys.dont_write_bytecode=True
for k,v in {'YOLO_AUTOINSTALL':'false','YOLO_CONFIG_DIR':str(R/'runtime/config'),'ULTRALYTICS_CONFIG_DIR':str(R/'runtime/config'),'MPLCONFIGDIR':str(R/'runtime/mpl'),'XDG_CACHE_HOME':str(R/'runtime/cache'),'TORCH_HOME':str(R/'runtime/torch')}.items():os.environ[k]=v
sys.path.insert(0,str(S/'ultralytics'))
def blocked(*a,**k):raise RuntimeError('NETWORK_FORBIDDEN')
socket.create_connection=blocked;socket.socket.connect=blocked
import torch,numpy as np,cv2
from PIL import Image,ImageDraw
from ultralytics import YOLOE
import ultralytics

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]));i=x*y;return i/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i)
if __name__=='__main__':
 out=R/'01_footprint';assert not (out/'segmentation_outputs.jsonl').exists(),'No overwrite'
 rows=list(csv.DictReader((R/'contracts/input_allowlist.csv').open())); forbidden={x['media_id'] for x in csv.DictReader((R/'contracts/forbidden_split_metadata.csv').open())};assert not forbidden.intersection(x['image_id'] for x in rows)
 contract=json.loads((R/'contracts/run_contract.json').read_text());torch.set_num_threads(4)
 weights=S/'models/yoloe/yoloe-26m-seg.pt';encoder=S/'models/mobileclip2_b.ts'
 dump(out/'runtime_preflight.json',{'torch':torch.__version__,'cuda_available':torch.cuda.is_available(),'ultralytics':ultralytics.__version__,'ultralytics_file':ultralytics.__file__,'python':sys.executable,'cv2':cv2.__version__,'numpy':np.__version__,'weights':str(weights),'weights_sha256':sha(weights),'encoder_sha256':sha(encoder),'network':'disabled','started_at':time.time()})
 # Encoder basename is resolved locally by upstream; an in-V5 symlink avoids changing upstream.
 (R/'runtime').mkdir(exist_ok=True); link=R/'runtime/mobileclip2_b.ts'
 if not link.exists():link.symlink_to(encoder)
 os.chdir(R/'runtime');model=YOLOE(str(weights));classes=contract['classes'];model.set_classes(classes,model.get_text_pe(classes))
 stats={'images':0,'raw_detection_count':0,'dedup_target_count':0,'duplicate_count':0,'detector_failure_count':0,'mask_failure_count':0,'validated_ground_contact_count':0,'latencies':[]}
 with (out/'segmentation_outputs.jsonl').open('x') as rawfile,(out/'footprint_outputs.jsonl').open('x') as fpfile,(out/'detector_manifest.jsonl').open('x') as logfile:
  for row in rows:
   p=pathlib.Path(row['absolute_path']);assert sha(p)==row['image_sha256']; im=Image.open(p).convert('RGB');w,h=im.size;t=time.time()
   try:
    result=model.predict(np.array(im)[:,:,::-1],conf=contract['conf'],imgsz=contract['imgsz'],iou=.7,max_det=contract['max_det'],verbose=False,retina_masks=True)[0]
    raw=[]
    for j,box in enumerate(result.boxes):
     poly=result.masks.xy[j].tolist() if result.masks is not None else []
     raw.append({'raw_detection_id':f'raw_{j+1:04d}','bbox_xyxy':box.xyxy[0].tolist(),'confidence':float(box.conf[0]),'class_name':classes[int(box.cls[0])],'mask_polygon_image':poly})
    kept=[];supp=[]
    for d in sorted(raw,key=lambda x:-x['confidence']):
     hit=next((x for x in kept if iou(x['bbox_xyxy'],d['bbox_xyxy'])>contract['dedup_iou']),None)
     if hit:supp.append({'raw_detection_id':d['raw_detection_id'],'suppressed_by':hit['raw_detection_id'],'dedup_reason':'class_agnostic_iou_gt_0.80'})
     else:kept.append(d)
    kept.sort(key=lambda x:x['raw_detection_id']);draw=ImageDraw.Draw(im,'RGBA')
    for j,d in enumerate(kept):
     poly=d['mask_polygon_image']; valid=len(poly)>=3 and all(0<=x<=w and 0<=y<=h for x,y in poly);area=float(cv2.contourArea(np.array(poly,dtype=np.float32))) if valid else 0;valid=valid and area>0
     x1,y1,x2,y2=d['bbox_xyxy'];lower=[[x1,y2-(y2-y1)*contract['mask_lower_fraction']],[x2,y2-(y2-y1)*contract['mask_lower_fraction']],[x2,y2],[x1,y2]]
     fp={'image_id':row['image_id'],'vehicle_id':f'S{j+1:03d}','raw_detection_id':d['raw_detection_id'],'suppressed_detection_ids':[x['raw_detection_id'] for x in supp if x['suppressed_by']==d['raw_detection_id']], 'dedup_reason':'fixed_class_agnostic_iou','bbox_xyxy':d['bbox_xyxy'],'mask_polygon_image':poly,'mask_area':area,'ground_contact_polygon_image':None,'bbox_lower_polygon_image':lower,'footprint_source':'segmentation_mask' if valid else 'bbox_lower','coordinate_space':'image','detector_confidence':d['confidence'],'mask_confidence':None,'mask_confidence_note':'not exposed separately by detector','mask_status':'ok' if valid else 'failed','ground_contact_status':'unvalidated','status':'uncertain','reason':'VISIBLE_BODY_MASK_IS_NOT_VALIDATED_GROUND_CONTACT'}
     fpfile.write(json.dumps(fp)+'\n');stats['mask_failure_count']+=not valid
     if valid:draw.polygon([tuple(x) for x in poly],fill=(0,255,0,65))
     draw.rectangle(d['bbox_xyxy'],outline=(255,0,0,255),width=3);draw.text((x1,y1),fp['vehicle_id'],fill=(255,0,0,255));draw.line([tuple(x) for x in lower+[lower[0]]],fill=(0,0,255,255),width=2)
    im.thumbnail((960,540));im.save(out/'footprint_visuals'/f"{row['image_id']}.jpg")
    rawfile.write(json.dumps({'image_id':row['image_id'],'source_sha256':row['image_sha256'],'source_size':[w,h],'detections':raw,'suppressed':supp})+'\n');stats['raw_detection_count']+=len(raw);stats['dedup_target_count']+=len(kept);stats['duplicate_count']+=len(supp)
    log={'image_id':row['image_id'],'input_sha256':row['image_sha256'],'status':'ok','raw_count':len(raw),'dedup_count':len(kept)}
   except Exception as e:
    stats['detector_failure_count']+=1;log={'image_id':row['image_id'],'status':'failed','error':repr(e)}
   log['latency_seconds']=time.time()-t;logfile.write(json.dumps(log)+'\n');logfile.flush();rawfile.flush();fpfile.flush();stats['latencies'].append(log['latency_seconds']);stats['images']+=1;dump(out/'progress.json',stats);print(row['image_id'],log['status'],log.get('dedup_count'),flush=True)
 dump(out/'footprint_metrics.json',stats)
