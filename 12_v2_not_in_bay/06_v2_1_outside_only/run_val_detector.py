#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,time,os,sys
OUT=Path(__file__).resolve().parent; CONFIG=OUT/'v2_1_val_config.json'; INPUT=OUT/'val_detector_input.jsonl'; CACHE=OUT/'val_vehicle_detections.jsonl'; LOCK=OUT/'VAL_DETECTOR_CONSUMED.lock'
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def atomic(p,s):
 t=Path(str(p)+'.tmp');t.write_text(s,encoding='utf-8',newline='\n');os.replace(t,p)
cfg=json.loads(CONFIG.read_text()); rows=[json.loads(x) for x in INPUT.read_text().splitlines() if x]
if CACHE.exists() or LOCK.exists(): raise SystemExit('ONE_SHOT_REFUSAL: detector cache or consumption lock already exists')
assert len(rows)==80 and len({x['sample_token'] for x in rows})==80
for r in rows:
 assert set(r)=={'sample_token','image_path','image_sha256'} and r['sample_token']==r['image_sha256']
 p=Path(r['image_path']).resolve(); assert Path('/home/yanbo/net_vlm_xunjian_dataset').resolve() in p.parents and p.is_file() and sha(p)==r['image_sha256']
d=cfg['detector']; cp=Path(d['checkpoint']); assert sha(cp)==d['checkpoint_sha256']
os.environ['YOLO_CONFIG_DIR']=str(OUT/'.ultralytics')
from ultralytics import YOLO
m=YOLO(str(cp)); assert all(m.names[int(k)]==v for k,v in d['classes'].items())
# lock before first detector inference, durable evidence that this one-shot was consumed
atomic(LOCK,json.dumps({'stage':'VAL_DETECTOR','started_at':'2026-09-15','config_sha256':sha(CONFIG),'input_sha256':sha(INPUT),'status':'STARTED_DO_NOT_RERUN'},sort_keys=True)+'\n')
with open(str(CACHE)+'.tmp','w',encoding='utf-8',newline='\n') as f:
 for i,r in enumerate(rows,1):
  t=time.perf_counter(); z=m.predict(source=r['image_path'],classes=[2,5,7],conf=.2,imgsz=640,device='cpu',verbose=False,save=False)[0]; det=[]
  if z.boxes is not None:
   for b,c,k in zip(z.boxes.xyxy.cpu().tolist(),z.boxes.conf.cpu().tolist(),z.boxes.cls.cpu().tolist()):
    k=int(k);det.append({'bbox':[round(float(v),3) for v in b],'class_id':k,'class_name':d['classes'][str(k)],'confidence':round(float(c),6)})
  rec={**r,'cache_source':'V2_1_VAL_NEW_LOCAL_YOLO11N','detections':det,'detector_latency_seconds':round(time.perf_counter()-t,6)}
  f.write(json.dumps(rec,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
  print(f'[{i}/80] detections={len(det)}',flush=True)
os.replace(str(CACHE)+'.tmp',CACHE); atomic(Path(str(CACHE)+'.sha256'),f'{sha(CACHE)}  {CACHE.name}\n')
atomic(LOCK,json.dumps({'stage':'VAL_DETECTOR','started_at':'2026-09-15','config_sha256':sha(CONFIG),'input_sha256':sha(INPUT),'cache_sha256':sha(CACHE),'status':'COMPLETED_DO_NOT_RERUN'},sort_keys=True)+'\n')
print(json.dumps({'status':'completed','rows':80,'cache_sha256':sha(CACHE)}))
