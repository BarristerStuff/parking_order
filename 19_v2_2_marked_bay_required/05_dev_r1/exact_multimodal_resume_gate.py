import sys,json,hashlib,base64,io,time
from pathlib import Path
from PIL import Image
OUT=Path(__file__).parent; ROOT=OUT.parents[1]; PIPE=OUT/'pipeline_snapshot';sys.path.insert(0,str(PIPE))
from vehicle_not_in_bay.config import load_config,prompt_bytes
from vehicle_not_in_bay.select import select
from vehicle_not_in_bay.view_a import render
from vehicle_not_in_bay.ollama_client import OllamaClient
cfg=load_config();assert cfg['endpoint']=='http://192.168.20.62:11434' and cfg['model']=='qwen3.5:4b' and cfg['concurrency']==2 and cfg['timeout_seconds']==240 and cfg['max_retries']==2 and cfg['temperature']==0 and cfg['num_predict']==32 and cfg['think'] is False
q1=prompt_bytes('q1.txt'); assert hashlib.sha256(q1).hexdigest()=='12c64bbf69915ac181a91adda39a8bd95ec26528d44f978e1eca6ad475a1cc9e'
ledger_rows=[json.loads(x) for x in open(OUT/'request_ledger.jsonl')]
# earliest logical request lacking schema_success
starts=[x for x in ledger_rows if x['event']=='request_start']
success={(x['sample_token'],x['vehicle_rank'],x['question']) for x in ledger_rows if x['event']=='request_result' and x.get('schema_success')}
key=next((x['sample_token'],x['vehicle_rank'],x['question']) for x in starts if (x['sample_token'],x['vehicle_rank'],x['question']) not in success)
assert key[2]=='q1'
source={x['sample_token']:x for x in map(json.loads,open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl'))}; r=source[key[0]]
assert hashlib.sha256(Path(r['image_path']).read_bytes()).hexdigest()==r['image_sha256']
with Image.open(r['image_path']) as im:
 im=im.convert('RGB'); selected=select(r['detections'],*im.size,cfg); d=selected[key[1]-1]; view=render(im,d['bbox'],cfg)
b=io.BytesIO();view.save(b,'JPEG',quality=cfg['view_a']['jpeg_quality']);raw=b.getvalue();vsha=hashlib.sha256(raw).hexdigest();enc=base64.b64encode(raw).decode()
client=OllamaClient(cfg['endpoint'],cfg['model'],str(OUT/'request_ledger.jsonl'),cfg)
t=time.monotonic();result={'sample_token':key[0],'vehicle_rank':key[1],'question':key[2],'view_a_sha256':vsha,'image_sha256':r['image_sha256'],'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
try:
 answer,latency=client.ask(q1.decode(),enc,key[0],key[1],'q1'); result.update(schema_success=True,answer=answer,latency_seconds=latency,error=None)
 with (OUT/'recovered_logical_results.jsonl').open('a') as f:f.write(json.dumps(result,sort_keys=True)+'\n')
except Exception as e:
 result.update(schema_success=False,answer=None,latency_seconds=time.monotonic()-t,error=repr(e))
(OUT/'ollama_health/exact_multimodal_resume_gate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if not result['schema_success']:raise SystemExit(2)
