import sys,json,csv,hashlib,shutil,time,concurrent.futures,threading
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).parent; PIPE=ROOT/'19_v2_2_marked_bay_required/02_pipeline'
sys.path.insert(0,str(PIPE))
from vehicle_not_in_bay.pipeline import infer_image
from vehicle_not_in_bay.ollama_client import OllamaClient
cfg=json.loads((PIPE/'config.json').read_text())
if cfg['endpoint']!='http://192.168.20.62:11434' or cfg['model']!='qwen3.5:4b' or cfg['concurrency']!=2:raise SystemExit('frozen endpoint/model/concurrency mismatch')
source=[json.loads(x) for x in open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl')]
if len(source)!=238:raise SystemExit(f'input count {len(source)}')
# freeze config + input manifest with no GT/group/prediction fields
frozen={'stage':'V2_2_R0_MINIMAL_SEMANTIC_CHANGE','pipeline_config':cfg,'q1_sha256':hashlib.sha256((PIPE/'prompts/q1.txt').read_bytes()).hexdigest(),'q3_sha256':hashlib.sha256((PIPE/'prompts/q3.txt').read_bytes()).hexdigest(),'pipeline_tree':'19_v2_2_marked_bay_required/02_pipeline','cached_detector_source':'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl','cached_detector_allowed_fields':['sample_token','image_path','image_sha256','detections'],'input_count':len(source),'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(OUT/'frozen_config.json').write_text(json.dumps(frozen,indent=2)+'\n')
with (OUT/'manifest.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['sample_token','image_path','image_sha256'],lineterminator='\n');w.writeheader()
 for r in source:w.writerow({k:r[k] for k in w.fieldnames})
# validate hashes before requests
for r in source:
 if hashlib.sha256(Path(r['image_path']).read_bytes()).hexdigest()!=r['image_sha256']:raise SystemExit('image hash mismatch '+r['sample_token'])
ledger=OUT/'request_ledger.jsonl'; ledger.unlink(missing_ok=True)
client=OllamaClient(cfg['endpoint'],cfg['model'],str(ledger),cfg)
lock=threading.Lock(); done=0

def one(r):
 def cached_detector(im,c):return r['detections'],0.0
 try:
  with Image.open(r['image_path']) as im: pred=infer_image(im,r['sample_token'],client,cached_detector)
  pred['status']='ok';pred['error']='';pred['image_path']=r['image_path'];pred['image_sha256']=r['image_sha256']
 except Exception as e:
  pred={'media_id':r['sample_token'],'status':'error','error':repr(e),'image_path':r['image_path'],'image_sha256':r['image_sha256'],'frame_decision':'uncertain','vehicles':[],'request_count':0,'total_latency_seconds':0}
 return pred
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 for pred in ex.map(one,source):
  results.append(pred);done+=1
  if done%10==0:print(f'completed {done}/238',flush=True)
with (OUT/'predictions.jsonl').open('w') as f:
 for r in results:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
print('R0 inference complete',len(results))
