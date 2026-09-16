import sys,json,hashlib,base64,io,time,threading,concurrent.futures
from pathlib import Path
from PIL import Image
OUT=Path(__file__).parent;ROOT=OUT.parents[1];PIPE=OUT/'pipeline_snapshot';sys.path.insert(0,str(PIPE))
from vehicle_not_in_bay.config import load_config,prompt_bytes
from vehicle_not_in_bay.select import select
from vehicle_not_in_bay.view_a import render
from vehicle_not_in_bay.rules import apply
from vehicle_not_in_bay.ollama_client import OllamaClient
cfg=load_config(); EXPECT={'q1':'12c64bbf69915ac181a91adda39a8bd95ec26528d44f978e1eca6ad475a1cc9e','q3':'5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc','gt':'413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56','yolo':'0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert cfg['endpoint']=='http://192.168.20.62:11434' and cfg['model']=='qwen3.5:4b' and cfg['concurrency']==2 and cfg['timeout_seconds']==240 and cfg['max_retries']==2 and cfg['temperature']==0 and cfg['num_predict']==32 and cfg['think'] is False
assert {'q1':sha(PIPE/'prompts/q1.txt'),'q3':sha(PIPE/'prompts/q3.txt'),'gt':sha(ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv'),'yolo':sha(PIPE/'assets/yolo11n.pt')}==EXPECT
q1=prompt_bytes('q1.txt').decode();q3=prompt_bytes('q3.txt').decode();ledger=OUT/'request_ledger.jsonl'; lock=threading.Lock()
def load_success():
 d={}
 for x in map(json.loads,ledger.read_text().splitlines()):
  if x['event']=='request_result' and x.get('schema_success'):d[(x['sample_token'],x['vehicle_rank'],x['question'])]=x
 return d
success=load_success();client=OllamaClient(cfg['endpoint'],cfg['model'],str(ledger),cfg)
source=list(map(json.loads,open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl')));assert len(source)==238
partial=OUT/'predictions.partial.jsonl';existing={}
if partial.exists():
 for x in map(json.loads,partial.read_text().splitlines()):existing[x['media_id']]=x

def ask_or_reuse(prompt,enc,token,rank,q):
 key=(token,rank,q)
 with lock: old=success.get(key)
 if old:return old['answer'],old.get('latency_seconds',0),False
 try:
  a,l=client.ask(prompt,enc,token,rank,q)
  with lock:success[key]={'answer':a,'latency_seconds':l,'schema_success':True}
  return a,l,True
 except Exception as e:return None,0,False

def one(r):
 token=r['sample_token'];new_success=0;failed=[]
 try:
  with Image.open(r['image_path']) as z: im=z.convert('RGB')
  ib=io.BytesIO();im.save(ib,'PNG');selected=select(r['detections'],*im.size,cfg);vehicles=[];total=0
  for rank,d in enumerate(selected,1):
   view=render(im,d['bbox'],cfg);b=io.BytesIO();view.save(b,'JPEG',quality=cfg['view_a']['jpeg_quality']);raw=b.getvalue();enc=base64.b64encode(raw).decode();vsha=hashlib.sha256(raw).hexdigest()
   a,l,isnew=ask_or_reuse(q1,enc,token,rank,'q1');new_success+=int(isnew);total+=l
   if a is None:failed.append((token,rank,'q1'));continue
   a3=None
   if a in ('B','C'):
    a3,l3,isnew3=ask_or_reuse(q3,enc,token,rank,'q3');new_success+=int(isnew3);total+=l3
    if a3 is None:failed.append((token,rank,'q3'))
   vehicles.append({'rank':rank,'bbox':d['bbox'],'q1':a,'q3':a3,'decision':None,'latency':l+(l3 if a in ('B','C') and a3 is not None else 0),'view_a_sha256':vsha})
  if failed:return {'ok':False,'token':token,'new_success':new_success,'failed':failed}
  frame,g=apply(vehicles);pred={'media_id':token,'frame_decision':frame,'vehicles':vehicles,'gate_queue_vehicles':g,'request_count':sum(1+(v['q1'] in ('B','C')) for v in vehicles),'total_latency_seconds':total,'detector_latency':0.0,'pipeline_version':'v2.2_marked_bay_required','q1_sha':EXPECT['q1'],'q3_sha':EXPECT['q3'],'input_sha256':hashlib.sha256(ib.getvalue()).hexdigest(),'input_width':im.width,'input_height':im.height,'view_a_sha256':vehicles[0]['view_a_sha256'] if vehicles else None,'status':'ok','error':'','image_path':r['image_path'],'image_sha256':r['image_sha256']}
  return {'ok':True,'token':token,'new_success':new_success,'failed':[],'prediction':pred}
 except Exception as e:return {'ok':False,'token':token,'new_success':new_success,'failed':[(token,0,'runner:'+repr(e))]}
remaining=[r for r in source if r['sample_token'] not in existing];consecutive_exhausted=0;stopped=False
for bi in range(0,len(remaining),2):
 batch=remaining[bi:bi+2]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:outs=list(ex.map(one,batch))
 for o in outs:
  if o['ok']:
   with partial.open('a') as f:f.write(json.dumps(o['prediction'],ensure_ascii=False,sort_keys=True)+'\n')
   existing[o['token']]=o['prediction']
  if o['new_success']>0:consecutive_exhausted=0
  for fail in o['failed']:
   if o['new_success']==0:consecutive_exhausted+=1
   else:consecutive_exhausted=1
   if consecutive_exhausted>=2:stopped=True
 print(f"coverage {len(existing)}/238 new_success={sum(x['new_success'] for x in outs)} failures={sum(len(x['failed']) for x in outs)} breaker={consecutive_exhausted}",flush=True)
 if stopped:break
status={'stage':'V2_2_R1_RECALL','ledger_aware_resume':True,'stopped_by_circuit_breaker':stopped,'prediction_coverage':len(existing),'unique_predictions':len(existing),'successful_logical_requests':len(load_success()),'consecutive_exhausted_failures':consecutive_exhausted,'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(OUT/'resume_status.json').write_text(json.dumps(status,indent=2)+'\n')
if len(existing)==238:
 order={r['sample_token']:i for i,r in enumerate(source)};rows=sorted(existing.values(),key=lambda x:order[x['media_id']]);
 with (OUT/'predictions.jsonl').open('w') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps(status,indent=2))
if stopped or len(existing)!=238:raise SystemExit(3)
