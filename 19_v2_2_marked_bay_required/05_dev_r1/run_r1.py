import sys,json,csv,hashlib,time,concurrent.futures
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).parent; PIPE=OUT/'pipeline_snapshot'
sys.path.insert(0,str(PIPE))
from vehicle_not_in_bay.pipeline import infer_image
from vehicle_not_in_bay.ollama_client import OllamaClient
cfg=json.loads((PIPE/'config.json').read_text())
R1Q='12c64bbf69915ac181a91adda39a8bd95ec26528d44f978e1eca6ad475a1cc9e'; Q3='5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc'; YOLO='0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'; GT='413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if cfg['endpoint']!='http://192.168.20.62:11434' or cfg['model']!='qwen3.5:4b' or cfg['concurrency']!=2:raise SystemExit('frozen endpoint/model/concurrency mismatch')
checks={'q1':sha(PIPE/'prompts/q1.txt'),'q3':sha(PIPE/'prompts/q3.txt'),'yolo':sha(PIPE/'assets/yolo11n.pt'),'gt':sha(ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv')}
if checks!={'q1':R1Q,'q3':Q3,'yolo':YOLO,'gt':GT}:raise SystemExit('frozen hash mismatch '+repr(checks))
source=[json.loads(x) for x in open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl')]
if len(source)!=238 or len({x['sample_token'] for x in source})!=238:raise SystemExit('input coverage mismatch')
for r in source:
 if set(r)-{'sample_token','image_path','image_sha256','detections'}:raise SystemExit('forbidden input fields')
 if sha(r['image_path'])!=r['image_sha256']:raise SystemExit('image hash mismatch '+r['sample_token'])
start=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
frozen={'stage':'V2_2_R1_RECALL','R1_STARTED':True,'pipeline_config':cfg,'q1_sha256':R1Q,'q3_sha256':Q3,'yolo_sha256':YOLO,'gt_sha256':GT,'pipeline_tree':'19_v2_2_marked_bay_required/05_dev_r1/pipeline_snapshot','cached_detector_source':'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl','cached_detector_allowed_fields':['sample_token','image_path','image_sha256','detections'],'input_count':238,'start_utc':start}
(OUT/'frozen_config.json').write_text(json.dumps(frozen,indent=2)+'\n')
started={'R1_STARTED':True,'timestamp_utc':start,'GT_SHA':GT,'R1_Q1_SHA':R1Q,'Q3_SHA':Q3,'YOLO_SHA':YOLO,'pipeline_revision':'V2_2_R1_RECALL','runtime':sys.executable}
(OUT/'r1_started.json').write_text(json.dumps(started,indent=2)+'\n')
with (OUT/'manifest.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['sample_token','image_path','image_sha256'],lineterminator='\n');w.writeheader();[w.writerow({k:r[k] for k in w.fieldnames}) for r in source]
ledger=OUT/'request_ledger.jsonl';ledger.unlink(missing_ok=True);client=OllamaClient(cfg['endpoint'],cfg['model'],str(ledger),cfg)
def one(r):
 def cached_detector(im,c):return r['detections'],0.0
 try:
  with Image.open(r['image_path']) as im: pred=infer_image(im,r['sample_token'],client,cached_detector)
  pred.update(status='ok',error='',image_path=r['image_path'],image_sha256=r['image_sha256'])
 except Exception as e:
  pred={'media_id':r['sample_token'],'status':'error','error':repr(e),'image_path':r['image_path'],'image_sha256':r['image_sha256'],'frame_decision':'uncertain','vehicles':[],'request_count':0,'total_latency_seconds':0}
 return pred
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 for i,pred in enumerate(ex.map(one,source),1):
  results.append(pred)
  if i%10==0:print(f'completed {i}/238',flush=True)
with (OUT/'predictions.jsonl').open('w') as f:
 for r in results:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
frozen['end_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());frozen['prediction_count']=len(results);(OUT/'frozen_config.json').write_text(json.dumps(frozen,indent=2)+'\n')
print('R1 inference complete',len(results))
