#!/usr/bin/env python3
import csv,hashlib,json,platform,subprocess,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; P2=Path(__file__).resolve().parents[1]
SPLIT=ROOT/'22_parkscope_structured_geometry_p1/01_input_audit/cal_eval_split.csv'
PRED=ROOT/'21_parkscope_segmentation_feasibility_p0/03_inference/parkscope_predictions.jsonl'
BIND=ROOT/'21_parkscope_segmentation_feasibility_p0/02_input_audit/selected_vehicle_binding.csv'
EXPECTED_SPLIT='bf8d5ba02dc0a2c5a0f1384ca0dfacd9afe3dcdbd440c7775b9cdd943d68b332'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
 if sha(SPLIT)!=EXPECTED_SPLIT: raise SystemExit('P2_CAL_BLOCKED_SPLIT_INTEGRITY')
 split=list(csv.DictReader(SPLIT.open(newline=''))); counts=Counter(r['partition'] for r in split)
 if counts!={'CALIBRATION':30,'EVALUATION':30,'GATE_SECONDARY':10}: raise SystemExit('P2_CAL_BLOCKED_SPLIT_INTEGRITY')
 cal_order=[r['media_id'] for r in split if r['partition']=='CALIBRATION']; cal=set(cal_order)
 preds={}
 for line in PRED.open():
  x=json.loads(line)
  if x['media_id'] in cal: preds[x['media_id']]=x
 binds=[r for r in csv.DictReader(BIND.open(newline='')) if r['media_id'] in cal]
 if set(preds)!=cal or {r['media_id'] for r in binds}!=cal: raise SystemExit('P2_CAL_BLOCKED_INPUT_BINDING')
 fields=['media_id','selected_rank','frozen_bbox','matched_instance','match_status','source_path','source_sha256']
 rows=[]
 for r in sorted(binds,key=lambda x:(cal_order.index(x['media_id']),int(x['selected_rank']))):
  p=preds[r['media_id']]; rows.append({'media_id':r['media_id'],'selected_rank':r['selected_rank'],'frozen_bbox':r['frozen_bbox'],'matched_instance':r['matched_instance'],'match_status':r['match_status'],'source_path':p['image_path'],'source_sha256':p['image_sha256']})
 with (P2/'01_input_audit/cal_request_manifest.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
 dump(P2/'01_input_audit/split_reference.json',{'path':str(SPLIT.relative_to(ROOT)),'sha256':sha(SPLIT),'counts':dict(counts),'calibration_media_ids_sha256':hashlib.sha256(('\n'.join(cal_order)+'\n').encode()).hexdigest(),'evaluation_sealed':True})
 dump(P2/'01_input_audit/input_integrity.json',{'parkscope_predictions_path':str(PRED.relative_to(ROOT)),'parkscope_predictions_sha256':sha(PRED),'selected_vehicle_binding_path':str(BIND.relative_to(ROOT)),'selected_vehicle_binding_sha256':sha(BIND),'split_sha256':sha(SPLIT),'cal_images':len(cal),'cal_selected_targets':len(rows),'cal_valid_targets':sum(r['match_status']=='MATCHED' and r['matched_instance']!='' for r in rows),'cal_invalid_targets':sum(not(r['match_status']=='MATCHED' and r['matched_instance']!='') for r in rows),'parkscope_new_requests':0})
 print(json.dumps({'cal_images':len(cal),'targets':len(rows),'valid':sum(r['match_status']=='MATCHED' and r['matched_instance']!='' for r in rows),'partition_counts':dict(counts)},indent=2))
if __name__=='__main__':main()
