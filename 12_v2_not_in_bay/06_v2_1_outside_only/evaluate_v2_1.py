#!/usr/bin/env python3
from pathlib import Path
import csv,json,math,statistics,hashlib,shutil,os
OUT=Path(__file__).resolve().parent
ALLOW=OUT/'val_allowlist.csv'; PRED=OUT/'val_predictions.jsonl'; DEV=OUT.parent/'05_vlm_dev_r1/predictions.jsonl'
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def wilson(k,n,z=1.959963984540054):
 if n==0:return [None,None]
 p=k/n; den=1+z*z/n; ctr=(p+z*z/(2*n))/den; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [ctr-half,ctr+half]
def rate(k,n): return {'numerator':k,'denominator':n,'value':k/n if n else None,'wilson_95':wilson(k,n)}
def pct(values,q):
 if not values:return None
 v=sorted(values); return v[max(0,math.ceil(q*len(v))-1)]
def vscope(g):
 if g.startswith('p01-'):return 'positive'
 if g.startswith(('p03-','p05-')):return 'out_of_scope'
 if g.startswith('hn01-'):return 'secondary'
 if g[:3] in {'u01','u02','u03','u04','u05'}:return 'uncertain'
 return 'negative'
def eval_rows(rows,name):
 scopes={s:[x for x in rows if x['v2_1_scope']==s] for s in ['positive','negative','secondary','out_of_scope','uncertain']}
 alert=lambda x:x['model_label']=='positive'
 uncertain=lambda x:x['model_label']=='uncertain'
 m={'dataset':name,'images':len(rows),'recall':rate(sum(alert(x) for x in scopes['positive']),len(scopes['positive'])),'negative_fpr':rate(sum(alert(x) for x in scopes['negative']),len(scopes['negative'])),'hn01_fpr':rate(sum(alert(x) for x in scopes['secondary']),len(scopes['secondary'])),'out_of_scope_alert_rate':rate(sum(alert(x) for x in scopes['out_of_scope']),len(scopes['out_of_scope'])),'uncertain_rate_all':rate(sum(uncertain(x) for x in rows),len(rows))}
 for prefix in ['p03','p05']:
  a=[x for x in rows if x['group_key'].startswith(prefix+'-')];m[prefix+'_alert_rate']=rate(sum(alert(x) for x in a),len(a))
 m['uncertain_scope_prediction_rate']=rate(sum(uncertain(x) for x in scopes['uncertain']),len(scopes['uncertain']))
 m['prediction_counts']={k:sum(x['model_label']==k for x in rows) for k in ['positive','negative','uncertain']}
 m['fp_media_ids']=[x['media_id'] for x in scopes['negative'] if alert(x)]
 m['fn_media_ids']=[x['media_id'] for x in scopes['positive'] if not alert(x)]
 return m
allow={x['sample_token']:x for x in csv.DictReader(open(ALLOW,encoding='utf-8'))}; val=[]
for line in open(PRED,encoding='utf-8'):
 x=json.loads(line); a=allow[x['sample_token']];x.update({k:a[k] for k in ['group_key','v2_1_scope','v2_1_reference','v2_0_gt']});val.append(x)
assert len(val)==80 and len({x['media_id'] for x in val})==80
# DEV historical answers, apply Q1-only rule offline
dev=[]
for line in open(DEV,encoding='utf-8'):
 x=json.loads(line); answers=[]; failed=False
 for v in x.get('vehicle_results',[]):
  q=v.get('q1') or {}; answers.append(q.get('answer')); failed |= q.get('status')!='ok'
 label='positive' if 'C' in answers else ('uncertain' if ('D' in answers or failed or not x.get('vehicle_results')) else 'negative')
 dev.append({'media_id':x['media_id'],'group_key':x['group_key'],'v2_1_scope':vscope(x['group_key']),'model_label':label})
vm=eval_rows(val,'VAL');dm=eval_rows(dev,'DEV_a_offline_from_frozen_R1_Q1')
lat=[x['latency_seconds'] for x in val]; attempts=[a for x in val for v in x['vehicle_results'] for a in v['q1']['attempts']]
vm['latency_seconds']={'p50':statistics.median(lat),'p95_nearest_rank':pct(lat,.95),'min':min(lat),'max':max(lat)}
vm['requests']={'logical_q1':sum(len(x['vehicle_results']) for x in val),'physical_http':sum(x['request_count'] for x in val),'q2':0,'schema_successes':sum(a['schema_success'] for a in attempts),'physical_failures':sum(not a['schema_success'] for a in attempts)}
vm['detector']={'images':80,'raw_detection_count':sum(len(json.loads(l)['detections']) for l in open(OUT/'val_vehicle_detections.jsonl'))}
metrics={'definition':'v2.1_outside_only','source_type':'AIGC','human_gold':False,'val':vm,'dev_a':dm}
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2,sort_keys=True)+'\n',encoding='utf-8')
# enriched predictions
with open(OUT/'val_predictions_enriched.jsonl','w',encoding='utf-8') as f:
 for x in sorted(val,key=lambda x:x['media_id']):f.write(json.dumps(x,sort_keys=True)+'\n')
# errors and required view-A copies
errdir=OUT/'errors'; fpdir=errdir/'false_positives';fndir=errdir/'false_negatives';fpdir.mkdir(parents=True,exist_ok=True);fndir.mkdir(parents=True,exist_ok=True)
errs=[]
for x in val:
 typ='FP' if x['v2_1_scope']=='negative' and x['model_label']=='positive' else ('FN' if x['v2_1_scope']=='positive' and x['model_label']!='positive' else None)
 if not typ:continue
 d=fpdir if typ=='FP' else fndir
 views=[]
 for v in x['vehicle_results']:
  src=Path(v['view_a']['path']);dst=d/src.name;shutil.copy2(src,dst);views.append(str(dst))
 errs.append({'error_type':typ,'media_id':x['media_id'],'group_key':x['group_key'],'prediction':x['model_label'],'view_a_paths':'|'.join(views)})
with open(OUT/'errors.csv','w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['error_type','media_id','group_key','prediction','view_a_paths']);w.writeheader();w.writerows(errs)
for p in [OUT/'metrics.json',OUT/'val_predictions_enriched.jsonl',OUT/'errors.csv']:
 Path(str(p)+'.sha256').write_text(f'{sha(p)}  {p.name}\n')
print(json.dumps(metrics,sort_keys=True))
