"""CPU detector/select regression against frozen HOLDOUT selected bboxes."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1].parent))
from vehicle_not_in_bay.detector import detect
from vehicle_not_in_bay.select import select
from PIL import Image
B=Path(__file__).resolve().parents[1]; mism=[]; total=0; matched=0
for r in map(json.loads,open(B.parent/'10_v2_1_holdout_final/predictions.jsonl')):
 with Image.open(r['image_path']) as im: ds,_=detect(r['image_path']); got=select(ds,*im.size); exp=[v['bbox'] for v in r['vehicles']]
 total+=len(exp)
 for a,b in zip(got,exp):
  if max(abs(x-y) for x,y in zip(a['bbox'],b))<=1: matched+=1
  else:mism.append(r['media_id'])
print('select_consistency',matched,'/',total,'mismatched_media_ids',sorted(set(mism)))
