import csv,json,hashlib,base64,io,time,threading,concurrent.futures,sys,urllib.request
from pathlib import Path
from PIL import Image
OUT=Path(__file__).parent; V=OUT.parent; ROOT=V.parent; PIPE=V/'02_pipeline';sys.path.insert(0,str(PIPE))
from vehicle_not_in_bay.select import select
from vehicle_not_in_bay.view_a import render as view_a
from vehicle_not_in_bay.view_b import render as view_b
from vehicle_not_in_bay.rules import vehicle_decision,frame_decision
cfg=json.load(open(PIPE/'config.json'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
proto=json.load(open(OUT/'pilot_protocol.json'));H=proto['frozen_hashes']
assert H=={'q_outside_sha':sha(PIPE/'prompts/q_outside.txt'),'q_multibay_sha':sha(PIPE/'prompts/q_multibay.txt'),'q_gate_sha':sha(PIPE/'prompts/q_gate.txt'),'yolo_sha':sha(PIPE/'assets/yolo11n.pt'),'gt_sha':sha(ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv'),'pilot_manifest_sha':sha(OUT/'pilot_manifest.csv')}
qout=(PIPE/'prompts/q_outside.txt').read_text();qmulti=(PIPE/'prompts/q_multibay.txt').read_text();qgate=(PIPE/'prompts/q_gate.txt').read_text();ledger=OUT/'request_ledger.jsonl';lock=threading.Lock()
# tags preflight evidence
with urllib.request.urlopen(cfg['endpoint']+'/api/tags',timeout=10) as r:tags=r.read();(OUT/'ollama_tags.json').write_bytes(tags)
assert cfg['model'] in [m.get('name') for m in json.loads(tags).get('models',[])]
(OUT/'pilot_started.json').write_text(json.dumps({'PILOT_STARTED':True,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'frozen_hashes':H,'config':cfg},indent=2)+'\n')
class Client:
 def log(self,x):
  with lock:
   with ledger.open('a') as f:f.write(json.dumps(x,sort_keys=True)+'\n');f.flush()
 def ask(self,prompt,b64,token,rank,q,enum):
  last=None
  for attempt in range(1,cfg['max_retries']+2):
   self.log({'event':'request_start','sample_token':token,'vehicle_rank':rank,'question':q,'attempt':attempt,'timestamp':time.time()});t=time.perf_counter()
   payload={'model':cfg['model'],'prompt':prompt,'images':[b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':enum}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':cfg['num_predict']},'think':False}
   try:
    req=urllib.request.Request(cfg['endpoint']+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=cfg['timeout_seconds']) as r:z=json.load(r)
    a=json.loads(z['response'])['answer'];assert a in enum;l=time.perf_counter()-t;self.log({'event':'request_result','sample_token':token,'vehicle_rank':rank,'question':q,'attempt':attempt,'timestamp':time.time(),'answer':a,'latency_seconds':l,'schema_success':True});return a,l
   except Exception as e:
    last=e;self.log({'event':'request_result','sample_token':token,'vehicle_rank':rank,'question':q,'attempt':attempt,'timestamp':time.time(),'error':str(e),'schema_success':False})
  raise last
client=Client();source={x['sample_token']:x for x in map(json.loads,open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl'))};manifest=list(csv.DictReader(open(OUT/'pilot_manifest.csv',newline='')))
def enc(raw):return base64.b64encode(raw).decode()
def one(m):
 s=source[m['sample_token']];token=s['sample_token'];total=0
 with Image.open(s['image_path']) as z:im=z.convert('RGB')
 selected=select(s['detections'],*im.size,cfg);vs=[]
 for rank,d in enumerate(selected,1):
  va=view_a(im,d['bbox'],cfg);b=io.BytesIO();va.save(b,'JPEG',quality=cfg['view_a']['jpeg_quality']);araw=b.getvalue();braw,crop,bbox=view_b(im,d['bbox'])
  o,lo=client.ask(qout,enc(araw),token,rank,'q_outside',['YES','NO','UNCERTAIN']);m2,lm=client.ask(qmulti,enc(braw),token,rank,'q_multibay',['YES','NO','UNCERTAIN']);total+=lo+lm;gate=None;lg=0
  if o=='YES' or m2=='YES':gate,lg=client.ask(qgate,enc(araw),token,rank,'q_gate',['A','B','C','D']);total+=lg
  dec,gq=vehicle_decision(o,m2,gate);vs.append({'rank':rank,'bbox':d['bbox'],'outside':o,'multibay':m2,'gate':gate,'decision':dec,'gate_queue':gq,'view_a_sha256':hashlib.sha256(araw).hexdigest(),'view_b_sha256':hashlib.sha256(braw).hexdigest(),'latency_seconds':lo+lm+lg})
 return {'sample_token':token,'media_id':m['media_id'],'group_key':m['group_key'],'stratum':m['stratum'],'frame_decision':frame_decision(vs),'vehicles':vs,'total_latency_seconds':total,'status':'ok','error':'','hashes':H}
rows=[]
for i in range(0,len(manifest),2):
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:batch=list(ex.map(one,manifest[i:i+2]))
 rows.extend(batch)
 with open(OUT/'predictions.partial.jsonl','a') as f:
  for x in batch:f.write(json.dumps(x,sort_keys=True)+'\n')
 print(f'coverage {len(rows)}/{len(manifest)}',flush=True)
with open(OUT/'predictions.jsonl','w') as f:
 for x in rows:f.write(json.dumps(x,sort_keys=True)+'\n')
(OUT/'run_status.json').write_text(json.dumps({'coverage':len(rows),'unique':len({x['sample_token'] for x in rows}),'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2)+'\n')
