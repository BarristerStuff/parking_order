from pathlib import Path
import csv,json,sys,base64,io,time,hashlib,datetime
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'08_v2_1_pipeline'))
from vehicle_not_in_bay.select import select
from vehicle_not_in_bay.ollama_client import OllamaClient
O=Path(__file__).resolve().parent;R=O.parent
if (O/'HOLDOUT_CONSUMED.lock').exists():raise SystemExit('HOLDOUT_ALREADY_LOCKED')
q1=(R/'08_v2_1_pipeline/prompts/q1.txt').read_text();q3=(R/'08_v2_1_pipeline/prompts/q3.txt').read_text();det={json.loads(x)['media_id']:json.loads(x) for x in open(O/'holdout_detections.jsonl')};rows=list(csv.DictReader(open(O/'allowlist.csv')));ledger=O/'request_ledger.jsonl';ledger.touch();client=__import__('vehicle_not_in_bay.ollama_client',fromlist=['OllamaClient']).OllamaClient('http://192.168.20.62:11434','qwen3.5:4b',ledger)
def view(path,bbox):
 im=Image.open(path).convert('RGB');im.load();s=min(1,896/max(im.size));z=im.resize((round(im.width*s),round(im.height*s)),getattr(Image,'Resampling',Image).LANCZOS);ImageDraw.Draw(z).rectangle([x*s for x in bbox],outline=(255,0,0),width=4);b=io.BytesIO();z.save(b,'JPEG',quality=90);return base64.b64encode(b.getvalue()).decode()
def one(r):
 im=Image.open(r['image_path']);w,h=im.size;ss=select(det[r['media_id']]['detections'],w,h);vs=[];tot=0
 for rank,d in enumerate(ss,1):
  b=view(r['image_path'],d['bbox']);q,la=client.ask(q1,b,r['image_sha256'],rank);tot+=la;q3a=None
  if q=='C':q3a,l=client.ask(q3,b,r['image_sha256'],rank);tot+=l
  dec='outside' if q=='C' and q3a in ('B','C') else 'gate_queue' if q=='C' and q3a=='A' else 'uncertain' if q=='D' or q3a=='D' or q3a is None and q=='C' else 'in_bay';vs.append({'rank':rank,'bbox':d['bbox'],'q1':q,'q3':q3a,'decision':dec,'latency':la})
 frame='positive' if any(v['decision']=='outside' for v in vs) else 'uncertain' if any(v['decision']=='uncertain' for v in vs) or not vs else 'negative'
 return {'media_id':r['media_id'],'group_key':r['group_key'],'v2_gt':r['v2_gt'],'scope':r['scope'],'frame_decision':frame,'vehicles':vs,'request_count':sum(1+(v['q1']=='C') for v in vs),'total_latency_seconds':tot,'image_path':r['image_path']}
# client itself preflights every request; process concurrency 2
with ThreadPoolExecutor(max_workers=2) as ex:
 out=list(ex.map(one,rows))
(O/'predictions.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in out)+'\n');req=sum(x['request_count'] for x in out);(O/'HOLDOUT_CONSUMED.lock').write_text(json.dumps({'status':'COMPLETED_DO_NOT_RERUN','images':len(out),'requests':req,'completed_date':'2026-09-15','q1_sha256':hashlib.sha256((R/'08_v2_1_pipeline/prompts/q1.txt').read_bytes()).hexdigest(),'q3_sha256':hashlib.sha256((R/'08_v2_1_pipeline/prompts/q3.txt').read_bytes()).hexdigest()},indent=2)+'\n');print(json.dumps({'images':len(out),'requests':req}))
