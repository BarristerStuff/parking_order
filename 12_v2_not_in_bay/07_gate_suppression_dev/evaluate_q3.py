from pathlib import Path
import json,statistics,math,csv,hashlib
D=Path('/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/07_gate_suppression_dev'); SRC=D.parent/'05_vlm_dev_r1'
def wilson(x,n):
 if n==0:return [None,None]
 z=1.959963984540054; p=x/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den; return [max(0,c-h),min(1,c+h)]
q=[json.loads(x) for x in open(D/'q3_predictions.jsonl')]; qmap={(x['media_id'],x['vehicle_rank']):x for x in q}
rows=[json.loads(x) for x in open(SRC/'predictions.jsonl')]; enriched=[]
for r in rows:
 decs=[]
 for rank,v in enumerate(r['vehicle_results'],1):
  a=v['q1']['answer']; q3=qmap.get((r['media_id'],rank),{}).get('q3',{}).get('answer')
  if a=='C': dec='negative_gate_queue' if q3=='A' else 'uncertain' if q3=='D' else 'positive'
  elif a=='D': dec='uncertain'
  else: dec='negative'
  decs.append((dec,q3))
 label='positive' if any(d=='positive' for d,q in decs) else 'uncertain' if any(d=='uncertain' for d,q in decs) or not decs else 'negative'
 x=dict(r);x['q3_frame_label']=label;x['q3_vehicle_decisions']=[{'rank':i+1,'q1':v['q1']['answer'],'q3':qmap.get((r['media_id'],i+1),{}).get('q3',{}).get('answer'),'decision':d} for i,(d,q) in enumerate(decs)]; enriched.append(x)
def count(scope, pred):
 xs=[r for r in enriched if r['scope']==scope]; return sum(pred(r) for r in xs),len(xs)
def rate(x,n): return {'numerator':x,'denominator':n,'value':x/n if n else None,'wilson_95':wilson(x,n)}
p=[r for r in enriched if r['group_key'].startswith('p01')]; neg=[r for r in enriched if r['v2_gt']=='negative' and r['scope']=='primary_binary' and not r['group_key'].startswith(('p03','p05'))]; hn=[r for r in enriched if r['scope']=='gate_queue_secondary']; unc=[r for r in enriched if r['v2_gt']=='uncertain']
metrics={'images':len(enriched),'recall':rate(sum(r['q3_frame_label']=='positive' for r in p),len(p)),'negative_fpr':rate(sum(r['q3_frame_label']=='positive' for r in neg),len(neg)),'hn01_fpr':rate(sum(r['q3_frame_label']=='positive' for r in hn),len(hn)),'uncertain_rate_all':rate(sum(r['q3_frame_label']=='uncertain' for r in enriched),len(enriched)),'p01_retention':rate(sum(r['q3_frame_label']=='positive' for r in p if r['group_key'].startswith('p01')),len([r for r in p if r['group_key'].startswith('p01')])), 'prediction_counts':{k:sum(r['q3_frame_label']==k for r in enriched) for k in ['positive','negative','uncertain']}}
(D/'q3_metrics.json').write_text(json.dumps(metrics,indent=2,sort_keys=True)+'\n'); (D/'q3_predictions_enriched.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in enriched)+'\n')
print(json.dumps(metrics,indent=2)); print('suppressed hn', [r['media_id'] for r in hn if r['q3_frame_label']!='positive']); print('suppressed p01', [r['media_id'] for r in p if r['group_key'].startswith('p01') and r['q3_frame_label']!='positive'])
