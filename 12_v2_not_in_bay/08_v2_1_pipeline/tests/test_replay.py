import json,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B.parent))
from vehicle_not_in_bay.rules import apply
D=B.parent
q={(x['media_id'],x['vehicle_rank']):x['q3']['answer'] for x in map(json.loads,open(D/'07_gate_suppression_dev/q3_predictions.jsonl'))}
counts={}
for r in map(json.loads,open(D/'05_vlm_dev_r1/predictions.jsonl')):
 vs=[]
 for rank,v in enumerate(r['vehicle_results'],1):vs.append({'q1':v['q1']['answer'],'q3':q.get((r['media_id'],rank))})
 frame,_=apply(vs);counts[frame]=counts.get(frame,0)+1
assert counts=={'positive':38,'negative':199,'uncertain':1},counts
val=[]
for r in map(json.loads,open(D/'06_v2_1_outside_only/val_predictions.jsonl')):
 frame,_=apply([{'q1':v['q1']['answer'],'q3':None} for v in r['vehicle_results']],legacy=True);val.append(frame)
vc={x:val.count(x) for x in ('positive','negative','uncertain')};assert vc=={'positive':19,'negative':61,'uncertain':0},vc
print('PASS replay DEV Q3 and VAL legacy')
