from pathlib import Path
import hashlib,json
CFG={'classes':{2:'car',5:'bus',7:'truck'},'conf':.2,'imgsz':640,'device':'cpu','checkpoint':'/home/yanbo/net_vlm_person_smoking_optimization/00_assets/person_detector/yolo11n.pt','checkpoint_sha256':'0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'}
def detect(path):
 from ultralytics import YOLO
 m=YOLO(CFG['checkpoint']);r=m.predict(str(path),conf=CFG['conf'],imgsz=CFG['imgsz'],device=CFG['device'],verbose=False)[0];out=[]
 for b,c,cl in zip(r.boxes.xyxy.tolist(),r.boxes.conf.tolist(),r.boxes.cls.tolist()):
  if int(cl) in CFG['classes']:out.append({'bbox':b,'class_id':int(cl),'class_name':CFG['classes'][int(cl)],'confidence':float(c)})
 return out
