from pathlib import Path
import json,hashlib,base64,io,time,re,urllib.request,datetime,os
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image,ImageDraw
ROOT=Path('/home/yanbo/net_vlm_parking_optimization'); SRC=ROOT/'12_v2_not_in_bay/05_vlm_dev_r1'; OUT=ROOT/'12_v2_not_in_bay/07_gate_suppression_dev'
if (OUT/'Q3_ATTEMPT2_COMPLETED.lock').exists(): raise SystemExit('Q3_ALREADY_COMPLETED')
prompt=(OUT/'q3_prompt.txt').read_text(); cfg=json.loads((OUT/'q3_config.json').read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[json.loads(x) for x in open(SRC/'predictions.jsonl')]; det={json.loads(x)['sample_token']:json.loads(x) for x in open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl')}
items=[]
for r in rows:
 for rank,v in enumerate(r['vehicle_results'],1):
  if v['q1']['answer']=='C': items.append((r,rank,v,det[r['sample_token']]))
items.sort(key=lambda x:(x[0]['media_id'],x[1]))
ledger=OUT/'q3_request_ledger.jsonl'; ledger.touch()
def log(x):
 with open(ledger,'a',encoding='utf-8') as f: f.write(json.dumps(x,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
def render(path,bbox):
 im=Image.open(path).convert('RGB'); im.load(); scale=min(1,896/max(im.size)); z=im.resize((round(im.width*scale),round(im.height*scale)),getattr(Image,'Resampling',Image).LANCZOS); ImageDraw.Draw(z).rectangle([x*scale for x in bbox],outline=(255,0,0),width=4); b=io.BytesIO(); z.save(b,'JPEG',quality=90); return base64.b64encode(b.getvalue()).decode(),z
def parse(raw):
 try: a=json.loads(raw).get('answer')
 except Exception: a=None
 if not a:
  m=re.search(r'\b([ABCD])\b',raw,re.I); a=m.group(1) if m else None
 a=str(a).upper()
 if a not in 'ABCD': raise ValueError('invalid_answer')
 return a
def call(r,rank,v,b64):
 token=r['sample_token']; ts=datetime.datetime.now(datetime.timezone.utc).isoformat(); log({'event':'request_start','sample_token':token,'vehicle_rank':rank,'timestamp':ts})
 payload={'model':cfg['model'],'prompt':prompt,'images':[b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':['A','B','C','D']}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':16},'think':False}
 t=time.perf_counter(); req=urllib.request.Request(cfg['endpoint'],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=240) as x: z=json.loads(x.read()); raw=z.get('response',''); a=parse(raw); result={'status':'ok','answer':a,'latency_seconds':round(time.perf_counter()-t,6),'raw_response':raw}
 except Exception as e: result={'status':'failed','answer':'D','latency_seconds':round(time.perf_counter()-t,6),'error':repr(e)}
 log({'event':'request_result','sample_token':token,'vehicle_rank':rank,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':result['status'],'answer':result['answer'],'latency_seconds':result['latency_seconds']})
 return result
def one(item):
 r,rank,v,c=item; b64,z=render(c['image_path'],v['bbox']); vp=OUT/'view_a_all'/f"{r['media_id']}__v{rank}.jpg"; z.save(vp,'JPEG',quality=90); q=call(r,rank,v,b64); return {'media_id':r['media_id'],'sample_token':r['sample_token'],'group_key':r['group_key'],'scope':r['scope'],'v2_gt':r['v2_gt'],'vehicle_rank':rank,'q1':'C','q3':q,'view_a':str(vp),'bbox':v['bbox'],'detection_count':r['eligible_detection_count']}
# trial is formal first result, serial
first=next(x for x in items if x[0]['group_key']=='hn01-gate-queue'); results=[one(first)]; rest=[x for x in items if x is not first]
with ThreadPoolExecutor(max_workers=2) as ex: results.extend(ex.map(one,rest))
results.sort(key=lambda x:(x['media_id'],x['vehicle_rank']))
(OUT/'q3_predictions.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in results)+'\n')
lock={'status':'COMPLETED_DO_NOT_RERUN','prompt_sha256':sha(OUT/'q3_prompt.txt'),'config_sha256':sha(OUT/'q3_config.json'),'source_predictions_sha256':sha(SRC/'predictions.jsonl'),'request_count':len(results),'schema_successes':sum(x['q3']['status']=='ok' for x in results),'completed_date':'2026-09-15'}
(OUT/'Q3_ATTEMPT2_COMPLETED.lock').write_text(json.dumps(lock,indent=2,sort_keys=True)+'\n')
print(json.dumps(lock,sort_keys=True))
