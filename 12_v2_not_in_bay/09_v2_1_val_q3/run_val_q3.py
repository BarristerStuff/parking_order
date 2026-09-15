from pathlib import Path
import json,sys,base64,hashlib,time,statistics,datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'08_v2_1_pipeline'))
from vehicle_not_in_bay.ollama_client import OllamaClient
R=Path(__file__).resolve().parents[1]; O=Path(__file__).resolve().parent; src=R/'06_v2_1_outside_only'; rows=[json.loads(x) for x in open(src/'val_predictions.jsonl')]
items=[]
for r in rows:
 for rank,v in enumerate(r['vehicle_results'],1):
  if v['q1']['answer']=='C':items.append((r,rank,v))
client=OllamaClient('http://192.168.20.62:11434','qwen3.5:4b',O/'q3_request_ledger.jsonl'); prompt=(R/'08_v2_1_pipeline/prompts/q3.txt').read_text();out=[]
for r,rank,v in items:
 path=src/'view_a_all'/Path(v['view_a']['path']).name
 b=base64.b64encode(path.read_bytes()).decode();a,lat=client.ask(prompt,b,r['sample_token'],rank);out.append({'media_id':r['media_id'],'group_key':r.get('group_key'),'scope':r.get('scope'),'q1':'C','q3':a,'latency_seconds':lat,'view_a':str(path),'vehicle_rank':rank})
(O/'q3_predictions.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in out)+'\n')
(O/'VAL_Q3_CONSUMED.lock').write_text(json.dumps({'status':'COMPLETED_DO_NOT_RERUN','request_count':len(out),'schema_successes':len(out),'completed_date':'2026-09-15','prompt_sha256':hashlib.sha256((R/'08_v2_1_pipeline/prompts/q3.txt').read_bytes()).hexdigest()})+'\n')
print(json.dumps({'requests':len(out),'successes':len(out)}))
