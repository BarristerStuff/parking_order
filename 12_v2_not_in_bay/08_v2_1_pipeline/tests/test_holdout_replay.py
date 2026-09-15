"""Offline replay of frozen HOLDOUT answers through new rules."""
import json
from pathlib import Path
from vehicle_not_in_bay.rules import apply
B=Path(__file__).resolve().parents[1]; rows=[json.loads(x) for x in open(B.parent/'10_v2_1_holdout_final/predictions.jsonl')]
for r in rows:
 vs=[{'q1':v['q1'],'q3':v['q3']} for v in r['vehicles']]; frame,_=apply(vs)
 assert frame==r['frame_decision'],r['media_id']
print('PASS holdout replay',len(rows))
