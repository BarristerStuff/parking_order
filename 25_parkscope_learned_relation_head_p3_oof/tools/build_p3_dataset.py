#!/usr/bin/env python3
import csv, json, hashlib, platform, sys
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
GT=REPO/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv'
SPLIT=REPO/'22_parkscope_structured_geometry_p1/01_input_audit/cal_eval_split.csv'
R0=REPO/'19_v2_2_marked_bay_required/04_dev_r0/predictions.jsonl'
R1=REPO/'19_v2_2_marked_bay_required/05_dev_r1/predictions.jsonl'
DET_SHA='0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'
GT_SHA='413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56'
SPLIT_SHA='bf8d5ba02dc0a2c5a0f1384ca0dfacd9afe3dcdbd440c7775b9cdd943d68b332'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_csv(p, rows, fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)
def jdump(p,obj): p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')

assert sha(GT)==GT_SHA, (sha(GT),GT_SHA)
assert sha(SPLIT)==SPLIT_SHA, (sha(SPLIT),SPLIT_SHA)
# Seal construction: only partition and media_id are accessed.
sealed=set()
with SPLIT.open(newline='',encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row['partition']=='EVALUATION': sealed.add(row['media_id'])
assert len(sealed)==30
write_csv(ROOT/'01_dataset/sealed_eval_exclusion.csv', [{'media_id':x} for x in sorted(sealed)], ['media_id'])

# Historical input/bbox records; semantic answers and decisions are intentionally ignored.
def historical(path):
    out={}
    with path.open(encoding='utf-8') as f:
        for line in f:
            x=json.loads(line); mid=Path(x['image_path']).stem
            out[mid]={'image_path':x['image_path'],'image_sha256':x['image_sha256'],
                      'vehicles':[{'rank':int(v['rank']),'bbox':[float(z) for z in v['bbox']]} for v in x['vehicles']]}
    return out
h0,h1=historical(R0),historical(R1)
assert set(h0)==set(h1) and len(h0)==238
bbox_mismatches=[]
for mid in sorted(h0):
    if h0[mid]!=h1[mid]: bbox_mismatches.append(mid)
assert not bbox_mismatches

rows=[]; excluded=Counter()
with GT.open(newline='',encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        mid=row['media_id']
        # Hard seal: no GT/group fields are inspected for EVALUATION media.
        if mid in sealed:
            excluded['sealed_evaluation']+=1; continue
        label=row['event_label']
        if label=='uncertain': excluded['uncertain']+=1; continue
        if label=='secondary_gate_queue': excluded['gate_secondary']+=1; continue
        assert label in {'positive','negative'}
        h=h0[mid]
        rows.append({'media_id':mid,'label':label,'label_binary':1 if label=='positive' else 0,
                     'group_key':row['group_key'],'image_path':h['image_path'],'image_sha256':h['image_sha256'],
                     'cv_group_id':mid,'cv_group_field':'media_id'})
rows.sort(key=lambda r:r['media_id'])
assert len(rows)==166
assert Counter(r['label'] for r in rows)==Counter({'negative':119,'positive':47})
assert excluded==Counter({'sealed_evaluation':30,'uncertain':24,'gate_secondary':18})
write_csv(ROOT/'01_dataset/p3_primary_manifest.csv',rows,
          ['media_id','label','label_binary','group_key','image_path','image_sha256','cv_group_id','cv_group_field'])

targets=[]
for row in rows:
    for v in sorted(h0[row['media_id']]['vehicles'],key=lambda z:z['rank']):
        targets.append({'media_id':row['media_id'],'selected_rank':v['rank'],
                        'bbox_xyxy':json.dumps(v['bbox'],separators=(',',':')),
                        'source':'v2.2 R0/R1 exact-equality historical selection artifact',
                        'selector_version':'v2.2-frozen','detector_sha':DET_SHA})
write_csv(ROOT/'03_target_binding/frozen_target_manifest.csv',targets,
          ['media_id','selected_rank','bbox_xyxy','source','selector_version','detector_sha'])

# The only candidate generation/scenario metadata found maps to event subtype/group_key and is forbidden for CV.
# Source batch is constant for all frames and cannot support Group OOF. Therefore authorized media_id fallback is used.
summary={'gt_sha256':sha(GT),'cal_eval_split_sha256':sha(SPLIT),'total_frozen_dev':238,
         'sealed_evaluation_excluded':excluded['sealed_evaluation'],'uncertain_excluded':excluded['uncertain'],
         'gate_secondary_excluded':excluded['gate_secondary'],'actual_primary_pool':len(rows),
         'primary_positive':sum(r['label']=='positive' for r in rows),
         'primary_negative':sum(r['label']=='negative' for r in rows),
         'target_count':len(targets),'historical_r0_r1_bbox_mismatch_count':len(bbox_mismatches),
         'cv_group_audit':{'generation_group':'available only as event subtype/group_key; forbidden',
                           'scenario_group':'not available for frozen DEV',
                           'source_group':'single constant capture batch; infeasible',
                           'batch_group':'single constant capture batch; infeasible',
                           'selected_field':'media_id','reason':'authorized fallback and prevents shared-ID leakage'}}
jdump(ROOT/'01_dataset/dataset_summary.json',summary)
print(json.dumps(summary,indent=2))
