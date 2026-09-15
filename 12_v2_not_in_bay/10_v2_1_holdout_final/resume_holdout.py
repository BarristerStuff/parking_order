import sys,json,csv,time,hashlib,base64,io,urllib.request,urllib.error,statistics,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent; R=O.parent; sys.path.insert(0,str(R/'08_v2_1_pipeline'))
from vehicle_not_in_bay.select import select
END='http://192.168.20.62:11434'; MODEL='qwen3.5:4b'; ledger=O/'request_ledger.jsonl'
q1=(R/'08_v2_1_pipeline/prompts/q1.txt').read_bytes();q3=(R/'08_v2_1_pipeline/prompts/q3.txt').read_bytes()
assert hashlib.sha256(q1).hexdigest().startswith('76151fc7') and hashlib.sha256(q3).hexdigest().startswith('5cc5e33a')
# robustly retain valid JSON records; final ENOSPC fragment is intentionally preserved in source ledger
raw=[]
for line in ledger.read_bytes().splitlines():
 try: raw.append(json.loads(line))
 except Exception: pass
# reconstruct historical question by per-key ordered request/result sequence
hist={}; pending={}
for r in raw:
 if r.get('event')=='request_start':
  k=(r.get('sample_token'),int(r.get('vehicle_rank'))); hist.setdefault(k,[]).append({'start':r})
 elif r.get('event')=='request_result':
  k=(r.get('sample_token'),int(r.get('vehicle_rank'))); arr=hist.setdefault(k,[])
  for e in arr:
   if 'result' not in e: e['result']=r; break
  else: arr.append({'result':r})
# assign Q1 first; Q3 only after Q1=C, and use result order
completed={}
for k,arr in hist.items():
 q='q1'
 for e in arr:
  if 'result' in e:
   completed[(k[0],k[1],q)]=e['result']
   if q=='q1' and e['result'].get('answer')=='C': q='q3'
  elif q=='q1': pass
# preflight
z=json.load(urllib.request.urlopen(END+'/api/tags',timeout=10)); names=[x.get('name') for x in z.get('models',[])]
if MODEL not in names: raise SystemExit('required model missing')
rows=list(csv.DictReader(open(O/'allowlist.csv'))); det={json.loads(x)['media_id']:json.loads(x) for x in open(O/'holdout_detections.jsonl')}
def view(path,bbox):
 im=Image.open(path).convert('RGB'); s=min(1,896/max(im.size)); z=im.resize((round(im.width*s),round(im.height*s)),getattr(Image,'Resampling',Image).LANCZOS); ImageDraw.Draw(z).rectangle([x*s for x in bbox],outline=(255,0,0),width=4); b=io.BytesIO(); z.save(b,'JPEG',quality=90); return base64.b64encode(b.getvalue()).decode()
def ask(prompt,b64,token,rank,qname):
 st={'event':'request_start','sample_token':token,'vehicle_rank':rank,'question':qname,'timestamp':time.time(),'attempt':2}
 with open(ledger,'a') as f:f.write(json.dumps(st)+'\n');f.flush()
 payload={'model':MODEL,'prompt':prompt.decode(),'images':[b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':['A','B','C','D']}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':32},'think':False}
 t=time.perf_counter(); req=urllib.request.Request(END+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=240) as rr: x=json.load(rr)
 a=json.loads(x['response'])['answer']; la=time.perf_counter()-t
 res={'event':'request_result','sample_token':token,'vehicle_rank':rank,'question':qname,'timestamp':time.time(),'answer':a,'latency_seconds':la,'attempt':2,'schema_success':True}
 with open(ledger,'a') as f:f.write(json.dumps(res)+'\n');f.flush()
 return a,la

def one(r):
 token=r['image_sha256']; im0=Image.open(r['image_path']); w,h=im0.size; im0.close(); ds=select(det[r['media_id']]['detections'],w,h); vs=[]; total=0
 for rank,d in enumerate(ds,1):
  b=view(r['image_path'],d['bbox']); k=(token,rank,'q1')
  if k in completed: q=completed[k]['answer']; la=completed[k].get('latency_seconds',0)
  else: q,la=ask(q1,b,token,rank,'q1'); completed[k]={'answer':q,'latency_seconds':la}
  total+=la;q3a=None
  if q=='C':
   k3=(token,rank,'q3')
   if k3 in completed:q3a=completed[k3]['answer']; l3=completed[k3].get('latency_seconds',0)
   else:q3a,l3=ask(q3,b,token,rank,'q3');completed[k3]={'answer':q3a,'latency_seconds':l3}
   total+=l3
  dec='outside' if q=='C' and q3a in ('B','C') else 'gate_queue' if q=='C' and q3a=='A' else 'uncertain' if q=='D' or (q=='C' and q3a in (None,'D')) else 'in_bay'
  vs.append({'rank':rank,'bbox':d['bbox'],'q1':q,'q3':q3a,'decision':dec,'latency':la})
 frame='positive' if any(v['decision']=='outside' for v in vs) else 'uncertain' if not vs or any(v['decision']=='uncertain' for v in vs) else 'negative'
 return {'media_id':r['media_id'],'group_key':r['group_key'],'v2_gt':r['v2_gt'],'scope':r['scope'],'frame_decision':frame,'vehicles':vs,'request_count':sum(1+(v['q1']=='C') for v in vs),'total_latency_seconds':total,'image_path':r['image_path']}
with ThreadPoolExecutor(max_workers=2) as ex: outs=list(ex.map(one,rows))
(O/'predictions.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in outs)+'\n')
def wil(n,d):
 if d==0:return [None,None]
 p=n/d; z=1.95996398454; den=1+z*z/d; c=(p+z*z/(2*d))/den; h=z*math.sqrt(p*(1-p)/d+z*z/(4*d*d))/den; return [c-h,c+h]
# recount attempt-2 successful result rows from the completed ledger
all_valid=[]
for line in ledger.read_bytes().splitlines():
 try: all_valid.append(json.loads(line))
 except Exception: pass
new_request_count=sum(1 for rr in all_valid if rr.get('attempt')==2 and rr.get('event')=='request_result' and rr.get('schema_success') is True)
groups={}
for x in outs:
 g=x['group_key']; groups.setdefault(g,[]).append(x)
def count(pred,gs):return sum(1 for x in outs if x['group_key'] in gs and x['frame_decision']==pred)
# labels: positive p01, negatives others excluding out_scope p03/p05 and uncertain u*
def metric(n,d):return {'n':n,'d':d,'rate':n/d if d else None,'wilson95':wil(n,d)}
p=[x for x in outs if x['group_key'].startswith('p01-')]; neg=[x for x in outs if not x['group_key'].startswith(('p01-','p03-','p05-','hn01-','u'))]
hn=[x for x in outs if x['group_key'].startswith('hn01-')]; p03=[x for x in outs if x['group_key'].startswith('p03-')];p05=[x for x in outs if x['group_key'].startswith('p05-')]; unc=[x for x in outs if x['group_key'].startswith('u')]
M={'p01_recall':metric(sum(x['frame_decision']=='positive' for x in p),len(p)),'negative_fpr':metric(sum(x['frame_decision']=='positive' for x in neg),len(neg)),'hn01_alert_rate':metric(sum(x['frame_decision']=='positive' for x in hn),len(hn)),'p03_alert_rate':metric(sum(x['frame_decision']=='positive' for x in p03),len(p03)),'p05_alert_rate':metric(sum(x['frame_decision']=='positive' for x in p05),len(p05)),'uncertain_rate':metric(sum(x['frame_decision']=='uncertain' for x in unc),len(unc)),'images':len(outs),'new_requests':new_request_count}
M['gates']={'p01_recall':M['p01_recall']['rate']>=.75,'negative_fpr':M['negative_fpr']['rate']<=.05,'hn01_alert_rate':M['hn01_alert_rate']['rate']<=2/6,'uncertain_rate':M['uncertain_rate']['rate']<=.10}
(O/'metrics.json').write_text(json.dumps(M,indent=2)+'\n')
lock={'status':'COMPLETED_DO_NOT_RERUN','attempt1_interrupted_reason':'ENOSPC','attempt1_ledger_rows':215,'attempt2_new_requests':M['new_requests'],'completed_date':'2026-09-15'};(O/'HOLDOUT_CONSUMED.lock').write_text(json.dumps(lock,indent=2)+'\n')
print(json.dumps(M,indent=2))
