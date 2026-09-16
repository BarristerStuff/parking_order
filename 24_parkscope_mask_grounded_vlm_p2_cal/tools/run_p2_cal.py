#!/usr/bin/env python3
import base64,csv,hashlib,json,platform,sys,threading,time,urllib.error,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test_fusion import target_decision
ROOT=Path(__file__).resolve().parents[2]; P2=Path(__file__).resolve().parents[1]
PROTO=P2/'00_protocol'; INF=P2/'03_inference'; LEDGER=INF/'request_ledger.jsonl'
lock=threading.Lock()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def jdump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def validate_answer(x):
 keys={'one_marked_bay','separator_through_vehicle','clearly_outside_marked_bay'}
 if not isinstance(x,dict) or set(x)!=keys: raise ValueError('schema keys mismatch')
 if any(x[k] not in {'YES','NO','UNCERTAIN'} for k in keys): raise ValueError('schema enum mismatch')
 return x
def log(rec):
 with lock:
  with LEDGER.open('a') as f:f.write(json.dumps(rec,sort_keys=True,separators=(',',':'))+'\n');f.flush()
def prior_successes():
 out={}
 if not LEDGER.exists():return out
 for line in LEDGER.open():
  try:r=json.loads(line)
  except:continue
  if r.get('schema_success'):
   out[(r['media_id'],str(r['selected_rank']))]=r['parsed_response']
 return out
def ask(row,prompt,schema,cfg):
 key=(row['media_id'],str(row['selected_rank'])); rid=f"{key[0]}:target{key[1]}"
 image=Path(row['composite_path_local']).read_bytes()
 if hashlib.sha256(image).hexdigest()!=row['composite_sha256']:raise ValueError(f'composite SHA mismatch {rid}')
 payload={'model':cfg['model'],'prompt':prompt,'images':[base64.b64encode(image).decode()],'stream':False,'think':False,'format':schema,'options':cfg['options'],'keep_alive':cfg['keep_alive']}
 last=''
 for attempt in range(1,int(cfg['max_retries'])+2):
  st=now(); t=time.perf_counter(); status=None; raw=None; parsed=None; err=''; ok=False
  try:
   req=urllib.request.Request(cfg['endpoint']+cfg['api'],data=json.dumps(payload,separators=(',',':')).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=float(cfg['timeout_seconds'])) as resp:
    status=resp.status; raw=json.loads(resp.read())
   parsed=validate_answer(json.loads(raw['response']));ok=True
  except Exception as e:
   err=f'{type(e).__name__}: {e}';last=err
  rec={'request_id':rid,'media_id':key[0],'selected_rank':int(key[1]),'composite_sha256':row['composite_sha256'],'prompt_sha':sha(PROTO/'mask_grounded_prompt.txt'),'schema_sha':sha(PROTO/'response_schema.json'),'model':cfg['model'],'endpoint':cfg['endpoint']+cfg['api'],'attempt':attempt,'start_time':st,'end_time':now(),'elapsed':time.perf_counter()-t,'http_status':status,'raw_response':raw,'parsed_response':parsed,'schema_success':ok,'error':err}
  log(rec)
  if ok:return {'ok':True,'answer':parsed,'attempts':attempt}
 return {'ok':False,'error':last,'attempts':int(cfg['max_retries'])+1}
def main():
 prereg=json.load(open(PROTO/'preregistration.json'));cfg=json.load(open(PROTO/'frozen_request_config.json'));schema=json.load(open(PROTO/'response_schema.json'));prompt=(PROTO/'mask_grounded_prompt.txt').read_text()
 checks={'prompt_sha':sha(PROTO/'mask_grounded_prompt.txt'),'schema_sha':sha(PROTO/'response_schema.json'),'overlay_config_sha':sha(PROTO/'overlay_config.json'),'renderer_sha':sha(P2/'tools/render_mask_grounded_composite.py'),'fusion_rule_sha':sha(PROTO/'fusion_rule.json'),'request_config_sha':sha(PROTO/'frozen_request_config.json')}
 for k,v in checks.items():
  if prereg[k]!=v:raise SystemExit(f'FROZEN HASH MISMATCH {k}')
 manifest=list(csv.DictReader(open(P2/'01_input_audit/cal_request_manifest.csv',newline=''))); comps={(r['media_id'],r['selected_rank']):r for r in csv.DictReader(open(P2/'02_composites/composite_manifest.csv',newline=''))}
 forbidden={'event_label','group_key','stratum','gt','prediction'}
 if forbidden & {x.lower() for x in manifest[0]}:raise SystemExit('GT leakage in request manifest')
 valid=[]; invalid=[]
 for r in manifest:
  key=(r['media_id'],r['selected_rank'])
  if r['match_status']=='MATCHED' and r['matched_instance'] and key in comps:valid.append(comps[key])
  else:invalid.append(r)
 # preflight only at execution time, after protocol freeze
 req=urllib.request.Request(cfg['endpoint']+'/api/tags')
 try:
  with urllib.request.urlopen(req,timeout=10) as resp: tags_raw=resp.read()
  tags=json.loads(tags_raw); visible=cfg['model'] in [m.get('name') for m in tags.get('models',[])]
 except Exception as e:
  tags={'error':f'{type(e).__name__}: {e}'};visible=False
 jdump(INF/'tags_preflight.json',{'timestamp_utc':now(),'model':cfg['model'],'visible':visible,'response':tags})
 if not visible:raise SystemExit('P2_CAL_BLOCKED_OLLAMA_UNAVAILABLE')
 try:
  import PIL
  pillow=PIL.__version__
 except Exception:pillow=None
 jdump(INF/'environment.json',{'python_version':platform.python_version(),'python_executable':sys.executable,'pillow_version':pillow,'platform':platform.platform(),'endpoint':cfg['endpoint'],'model':cfg['model'],'concurrency':cfg['concurrency']})
 successes=prior_successes(); pending=[r for r in valid if (r['media_id'],r['selected_rank']) not in successes]
 consecutive_exhausted=0; blocked=False; errors=[]
 for i in range(0,len(pending),int(cfg['concurrency'])):
  batch=pending[i:i+int(cfg['concurrency'])]
  with ThreadPoolExecutor(max_workers=int(cfg['concurrency'])) as ex:results=list(ex.map(lambda r:ask(r,prompt,schema,cfg),batch))
  for r,res in zip(batch,results):
   key=(r['media_id'],r['selected_rank'])
   if res['ok']:
    successes[key]=res['answer'];consecutive_exhausted=0
   else:
    consecutive_exhausted+=1;errors.append({'media_id':r['media_id'],'selected_rank':r['selected_rank'],'error':res['error'],'attempts':res['attempts']})
    if consecutive_exhausted>=2:blocked=True;break
  print(f"logical successes {len(successes)}/{len(valid)}",flush=True)
  if blocked:break
 with (INF/'technical_errors.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['media_id','selected_rank','error','attempts'],lineterminator='\n');w.writeheader();w.writerows(errors)
 if blocked or len(successes)!=len(valid):raise SystemExit('P2_CAL_BLOCKED_OLLAMA_TIMEOUT_RECURRENCE' if blocked else 'P2_CAL_BLOCKED_INCOMPLETE_PROTOCOL')
 # Freeze all target predictions only after complete success.
 out=[]
 for r in manifest:
  key=(r['media_id'],r['selected_rank'])
  if r['match_status']!='MATCHED' or not r['matched_instance']:
   out.append({'media_id':r['media_id'],'selected_rank':int(r['selected_rank']),'anchor_valid':False,'target_decision':'UNCERTAIN_ANCHOR','one_marked_bay':None,'separator_through_vehicle':None,'clearly_outside_marked_bay':None})
  else:
   a=successes[key];out.append({'media_id':r['media_id'],'selected_rank':int(r['selected_rank']),'anchor_valid':True,**a,'target_decision':target_decision(a['one_marked_bay'],a['separator_through_vehicle'],a['clearly_outside_marked_bay'],True)})
 pred=INF/'target_predictions_frozen.jsonl'
 with pred.open('w') as f:
  for x in out:f.write(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n')
 (INF/'target_predictions_frozen.sha256').write_text(sha(pred)+'  target_predictions_frozen.jsonl\n')
 print(json.dumps({'complete':True,'valid_targets':len(valid),'schema_successes':len(successes),'target_predictions_sha256':sha(pred)},indent=2))
if __name__=='__main__':main()
