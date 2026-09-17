#!/usr/bin/env python3
import base64,csv,hashlib,json,statistics,threading,time,urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from common import ROOT,PIPE,Q1_SHA,Q3_SHA,rows,write_csv,write_json,sha256_file
ENDPOINT='http://192.168.20.62:11434';MODEL='qwen3.5:4b';CONCURRENCY=2;TIMEOUT=240;MAX_RETRIES=2;NUM_PREDICT=32
q1=(PIPE/'prompts/q1.txt').read_bytes();q3=(PIPE/'prompts/q3.txt').read_bytes();assert hashlib.sha256(q1).hexdigest()==Q1_SHA and hashlib.sha256(q3).hexdigest()==Q3_SHA
request_rows=rows(ROOT/'03_qwen/request_manifest.csv');assert len(request_rows)==213
assert set(request_rows[0])=={'media_id','selected_rank','image_path','bbox','view_a_sha'}
ledger=ROOT/'03_qwen/request_ledger.jsonl'; ledger.unlink(missing_ok=True);lock=threading.Lock()
def log(x):
 with lock:
  with ledger.open('a',encoding='utf-8') as f:f.write(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n');f.flush()
def ask(prompt,image_b64,mid,rank,question):
 last=None
 for attempt in range(1,MAX_RETRIES+2):
  started=time.perf_counter();log({'event':'request_start','media_id':mid,'selected_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time()})
  payload={'model':MODEL,'prompt':prompt.decode('utf-8'),'images':[image_b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':['A','B','C','D']}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':NUM_PREDICT},'think':False}
  try:
   req=urllib.request.Request(ENDPOINT+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=TIMEOUT) as resp:z=json.load(resp)
   parsed=json.loads(z['response']);ans=parsed['answer']
   if ans not in ('A','B','C','D') or set(parsed)!={'answer'}:raise ValueError('schema validation failed')
   latency=time.perf_counter()-started;log({'event':'request_result','media_id':mid,'selected_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time(),'answer':ans,'latency_seconds':latency,'schema_success':True});return ans,latency,attempt
  except Exception as exc:
   latency=time.perf_counter()-started;last=exc;log({'event':'request_result','media_id':mid,'selected_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time(),'error_type':type(exc).__name__,'error':str(exc),'latency_seconds':latency,'schema_success':False})
   if attempt>MAX_RETRIES:raise
 raise last
def one(r):
 p=Path(r['image_path']);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==r['view_a_sha']; enc=base64.b64encode(raw).decode();mid=r['media_id'];rank=int(r['selected_rank'])
 a1,l1,_=ask(q1,enc,mid,rank,'q1');a3=None;l3=None
 if a1 in ('B','C'):a3,l3,_=ask(q3,enc,mid,rank,'q3')
 if a1=='A':decision='in_bay'
 elif a1=='D':decision='uncertain'
 elif a3=='A':decision='gate_queue'
 elif a3 in ('B','C'):decision='violation'
 else:decision='uncertain'
 return {'media_id':mid,'selected_rank':rank,'q1':a1,'q3':a3,'decision':decision,'q1_latency_seconds':l1,'q3_latency_seconds':l3,'view_a_sha':r['view_a_sha']}
results=[]
with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
 futs=[ex.submit(one,r) for r in request_rows]
 for i,f in enumerate(as_completed(futs),1): results.append(f.result());print(f'qwen targets {i}/213',flush=True)
results.sort(key=lambda r:(r['media_id'],r['selected_rank']))
with (ROOT/'03_qwen/qwen_target_predictions.jsonl').open('w',encoding='utf-8') as f:
 for r in results:f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
by=defaultdict(list)
for r in results:by[r['media_id']].append(r)
features=[]
for mid in sorted(by):
 xs=by[mid];frame='positive' if any(x['decision']=='violation' for x in xs) else ('uncertain' if any(x['decision']=='uncertain' for x in xs) else 'negative');cand=sum(x['q1'] in ('B','C') for x in xs)
 features.append({'media_id':mid,'qwen_frame_positive':1.0 if frame=='positive' else 0.0,'qwen_candidate_fraction':cand/len(xs),'selected_target_count':len(xs),'candidate_count':cand,'qwen_frame_decision':frame})
assert len(features)==166
fp=ROOT/'03_qwen/qwen_features_frozen.csv';write_csv(fp,features,['media_id','qwen_frame_positive','qwen_candidate_fraction','selected_target_count','candidate_count','qwen_frame_decision']);fsha=sha256_file(fp);(ROOT/'03_qwen/qwen_features_frozen.sha256').write_text(fsha+'  qwen_features_frozen.csv\n')
logs=[json.loads(x) for x in ledger.read_text().splitlines()];starts=[x for x in logs if x['event']=='request_start'];oks=[x for x in logs if x['event']=='request_result' and x.get('schema_success')];errs=[x for x in logs if x['event']=='request_result' and not x.get('schema_success')];lat=sorted(float(x['latency_seconds']) for x in oks)
def pct(v,p):
 if not v:return None
 k=(len(v)-1)*p;lo=int(k);hi=min(lo+1,len(v)-1);return v[lo]+(v[hi]-v[lo])*(k-lo)
q1n=sum(r['q1'] is not None for r in results);q3n=sum(r['q3'] is not None for r in results)
write_json(ROOT/'03_qwen/latency.json',{'q1_logical_requests':q1n,'q3_logical_requests':q3n,'total_logical_requests':q1n+q3n,'physical_attempts':len(starts),'schema_successes':len(oks),'timeouts':sum(x.get('error_type') in ('TimeoutError','URLError') and 'timed out' in x.get('error','').lower() for x in errs),'latency_p50_seconds':pct(lat,.5),'latency_p95_seconds':pct(lat,.95),'latency_max_seconds':max(lat) if lat else None,'mean_requests_per_frame':(q1n+q3n)/166})
write_csv(ROOT/'03_qwen/technical_errors.csv',errs,['event','media_id','selected_rank','question','attempt','timestamp','error_type','error','latency_seconds','schema_success'])
assert q1n==213 and len(oks)==q1n+q3n and len(results)==213
print(json.dumps({'feature_sha':fsha,'q1':q1n,'q3':q3n,'attempts':len(starts),'schema_successes':len(oks)},sort_keys=True))
