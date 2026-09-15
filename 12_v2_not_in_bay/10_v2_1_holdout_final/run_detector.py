from pathlib import Path
import csv,json,hashlib,time
from ultralytics import YOLO
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent; m=YOLO('/home/yanbo/net_vlm_person_smoking_optimization/00_assets/person_detector/yolo11n.pt');out=[]
for r in csv.DictReader(open(O/'allowlist.csv')):
 z=m.predict(r['image_path'],conf=.2,imgsz=640,device='cpu',verbose=False)[0];ds=[]
 for b,c,cl in zip(z.boxes.xyxy.tolist(),z.boxes.conf.tolist(),z.boxes.cls.tolist()):
  if int(cl) in (2,5,7):ds.append({'bbox':b,'class_id':int(cl),'class_name':{2:'car',5:'bus',7:'truck'}[int(cl)],'confidence':float(c)})
 out.append({'media_id':r['media_id'],'sample_token':r['image_sha256'],'image_path':r['image_path'],'detections':ds})
(O/'holdout_detections.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in out)+'\n');print(len(out),sum(len(x['detections']) for x in out))
