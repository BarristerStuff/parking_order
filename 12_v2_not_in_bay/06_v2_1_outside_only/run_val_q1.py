#!/usr/bin/env python3
from pathlib import Path
import base64,csv,hashlib,io,json,os,re,statistics,time,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image,ImageDraw
OUT=Path(__file__).resolve().parent; CFG=OUT/'v2_1_val_config.json'; CACHE=OUT/'val_vehicle_detections.jsonl'; PRED=OUT/'val_predictions.jsonl'; LOCK=OUT/'VAL_Q1_CONSUMED.lock'; PROMPT=OUT/'q1_prompt.txt'; VIEWS=OUT/'view_a_all'
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def atomic(p,s):
 t=Path(str(p)+'.tmp');t.write_text(s,encoding='utf-8',newline='\n');os.replace(t,p)
cfg=json.loads(CFG.read_text()); prompt=PROMPT.read_text(); rows=[json.loads(x) for x in CACHE.read_text().splitlines() if x]
if PRED.exists() or LOCK.exists(): raise SystemExit('ONE_SHOT_REFUSAL: predictions or Q1 lock exists')
assert len(rows)==80 and sha(PROMPT)==cfg['q1_prompt_sha256']
VIEWS.mkdir(exist_ok=True)
def select(ds,w,h):
 valid=[];rej=[]
 for d in ds:
  b=[float(x) for x in d['bbox']]; x1,y1,x2,y2=b
  if d.get('class_name') not in {'car','bus','truck'} or x2<=x1 or y2<=y1: rej.append({'detection':d,'reason':'invalid_or_class'});continue
  if x1<=1 or y1<=1 or x2>=w-1 or y2>=h-1: rej.append({'detection':d,'reason':'bbox_touches_image_edge'});continue
  valid.append(d)
 valid.sort(key=lambda d:(-((d['bbox'][2]-d['bbox'][0])*(d['bbox'][3]-d['bbox'][1])),-d['confidence'],d['class_id'],*d['bbox']))
 sel=valid[:1]
 if len(valid)>1 and (valid[1]['bbox'][3]-valid[1]['bbox'][1])>=.25*h: sel.append(valid[1])
 selected_ids={id(x) for x in sel}
 for d in valid:
  if id(d) not in selected_ids: rej.append({'detection':d,'reason':'not_selected_by_r1_rank_rule'})
 return sel,rej
def render(img,d):
 scale=min(1,896/max(img.size)); sz=(round(img.width*scale),round(img.height*scale)); z=img.resize(sz,Image.Resampling.LANCZOS) if scale<1 else img.copy(); dr=ImageDraw.Draw(z); b=[v*scale for v in d['bbox']];dr.rectangle(b,outline=(255,0,0),width=4);buf=io.BytesIO();z.save(buf,'JPEG',quality=90,optimize=True);return z,base64.b64encode(buf.getvalue()).decode(),{'crop_box':[0,0,img.width,img.height],'rendered_size':[z.width,z.height],'bbox_rendered':[round(v,3) for v in b]}
def parse(raw):
 s=raw.strip();
 try:
  x=json.loads(s); a=x.get('answer') if isinstance(x,dict) else None
 except Exception: a=None
 if a is None:
  m=re.fullmatch(r'(?:Answer\s*[:=]\s*)?([ABCD])(?:[\s.])?',s,re.I); a=m.group(1) if m else None
 a=str(a).upper() if a is not None else ''; 
 if a not in {'A','B','C','D'}: raise ValueError('invalid answer schema')
 return a
def post(payload):
 q=urllib.request.Request(cfg['endpoint'],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(q,timeout=cfg['timeout_seconds']) as r:return r.status,json.loads(r.read())
def call(b64):
 payload={'model':cfg['model'],'prompt':prompt,'images':[b64],**cfg['ollama_request']}; attempts=[]
 for n in range(1,cfg['max_retries']+2):
  t=time.perf_counter()
  try:
   hs,r=post(payload); raw=r.get('response','');a=parse(raw);attempts.append({'attempt':n,'http_status':hs,'schema_success':True,'latency_seconds':round(time.perf_counter()-t,6),'raw_response':raw,'answer':a,'error':'','total_duration_ns':r.get('total_duration'),'prompt_eval_count':r.get('prompt_eval_count'),'eval_count':r.get('eval_count')});return {'status':'ok','answer':a,'attempts':attempts}
  except Exception as e: attempts.append({'attempt':n,'http_status':None,'schema_success':False,'latency_seconds':round(time.perf_counter()-t,6),'raw_response':'','answer':None,'error':f'{type(e).__name__}: {e}'})
 return {'status':'failed','answer':'D','attempts':attempts}
def one(r):
 t=time.perf_counter(); p=Path(r['image_path']);
 with Image.open(p) as q: img=q.convert('RGB');img.load()
 w,h=img.size; sel,rej=select(r['detections'],w,h); vehicles=[]
 for rank,d in enumerate(sel,1):
  z,b64,meta=render(img,d); vp=VIEWS/f"{p.stem}__v{rank}.jpg";z.save(vp,'JPEG',quality=90,optimize=True);c=call(b64);vehicles.append({'candidate_rank':rank,'bbox':d['bbox'],'bbox_height_fraction':(d['bbox'][3]-d['bbox'][1])/h,'class_name':d['class_name'],'confidence':d['confidence'],'q1':c,'view_a':{**meta,'path':str(vp)}})
 answers=[v['q1']['answer'] for v in vehicles if v['q1']['status']=='ok']; failed=any(v['q1']['status']!='ok' for v in vehicles)
 if not vehicles: label,status='uncertain','no_eligible_detection'
 elif 'C' in answers: label,status='positive','ok'
 elif 'D' in answers or failed: label,status='uncertain','protocol_failure' if failed else 'ok'
 else: label,status='negative','ok'
 return {'sample_token':r['sample_token'],'image_sha256':r['image_sha256'],'media_id':p.stem,'width':w,'height':h,'status':status,'model_label':label,'frame_decision':label,'eligible_detection_count':len(sel),'rejected_detection_count':len(rej),'vehicle_results':vehicles,'request_count':sum(len(v['q1']['attempts']) for v in vehicles),'schema_success_count':sum(sum(a['schema_success'] for a in v['q1']['attempts']) for v in vehicles),'latency_seconds':round(time.perf_counter()-t,6),'error':''}
# lock immediately before first model submissions
atomic(LOCK,json.dumps({'status':'STARTED_DO_NOT_RERUN','config_sha256':sha(CFG),'cache_sha256':sha(CACHE),'started_date':'2026-09-15'},sort_keys=True)+'\n')
results=[]; tmp=Path(str(PRED)+'.tmp')
with open(tmp,'w',encoding='utf-8',newline='\n') as f, ThreadPoolExecutor(max_workers=2) as ex:
 fut={ex.submit(one,r):r for r in rows}
 for i,z in enumerate(as_completed(fut),1):
  x=z.result();results.append(x);f.write(json.dumps(x,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno());print(f"[{i}/80] {x['media_id']} {x['model_label']} req={x['request_count']} lat={x['latency_seconds']}",flush=True)
os.replace(tmp,PRED); atomic(Path(str(PRED)+'.sha256'),f'{sha(PRED)}  {PRED.name}\n')
atomic(LOCK,json.dumps({'status':'COMPLETED_DO_NOT_RERUN','config_sha256':sha(CFG),'cache_sha256':sha(CACHE),'predictions_sha256':sha(PRED),'completed_date':'2026-09-15'},sort_keys=True)+'\n')
print(json.dumps({'status':'completed','images':80,'physical_requests':sum(x['request_count'] for x in results),'predictions_sha256':sha(PRED)}))
