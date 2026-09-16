import csv,json,hashlib,collections
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=Path(__file__).parent
split=list(csv.DictReader(open(root/'12_v2_not_in_bay/01_gt_and_split/v2_split.csv')))
legacy={r['media_id']:r for r in csv.DictReader(open(root/'12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv'))}
review={r['media_id']:r for r in csv.DictReader(open(out/'dev_required_review.csv'))}
pos={'p01-outside-legal-bay-clear','p03-span-two-bays'}
neg={'n01-standard-inside-bay','n02-close-to-line-but-inside','n03-diagonal-bay-correct','n04-parallel-bay-correct','n05-multiple-all-correct','n06-special-marked-space-geometry-correct','hn02-faded-lines-but-confirmably-inside','hn03-perspective-looks-like-crossing','hn04-large-vehicle-compliant','hn05-adjacent-vehicle-occludes-lines','hn06-shadows-cracks-curbs-mimic-lines'}
rows=[]
for s in split:
 if s['split']!='DEV':continue
 mid,g=s['media_id'],s['group_key']
 if mid in review: label,source=review[mid]['v2_2_gt'],'v2.2_visual_adjudication'
 elif g in pos: label,source='positive','mechanical_high_confidence_mapping'
 elif g in neg: label,source='negative','mechanical_high_confidence_mapping'
 elif g=='hn01-gate-queue': label,source='secondary_gate_queue','mechanical_high_confidence_mapping'
 elif g.startswith('u'): label,source='uncertain','frozen_uncertain'
 else: raise SystemExit(f'unmapped {mid} {g}')
 rows.append({'media_id':mid,'group_key':g,'split':'DEV','event_label':label,'gt_source':source,'not_human_gold':'true' if source=='v2.2_visual_adjudication' else ''})
path=out/'v2_2_dev_gt.csv'; fields=list(rows[0])
with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
sha=hashlib.sha256(path.read_bytes()).hexdigest();(out/'v2_2_dev_gt.csv.sha256').write_text(f'{sha}  v2_2_dev_gt.csv\n')
counts=collections.Counter(r['event_label'] for r in rows); groups=collections.Counter((r['group_key'],r['event_label']) for r in rows)
with (out/'v2_2_dev_gt_statistics.csv').open('w',newline='') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['group_key','event_label','count'])
 for (g,l),n in sorted(groups.items()):w.writerow([g,l,n])
freeze={'status':'FROZEN','date':'2026-09-16','scope':'shadow_development_gt_only','dev_total':len(rows),'counts':counts,'sha256':sha,'reviewer':'codex_visual_review','not_human_gold':True,'formal_shared_labels_modified':False}
(out/'v2_2_dev_gt_freeze.json').write_text(json.dumps(freeze,indent=2,ensure_ascii=False)+'\n')
# independent coverage validation
errors=[]; ids=[r['media_id'] for r in rows]
if len(rows)!=238:errors.append(f'dev_total={len(rows)} expected=238')
for mid,n in collections.Counter(ids).items():
 if n!=1:errors.append(f'duplicate:{mid}:{n}')
allowed={'positive','negative','uncertain','secondary_gate_queue'}
for r in rows:
 if r['event_label'] not in allowed:errors.append('bad_label:'+r['media_id'])
 if r['split']!='DEV':errors.append('non_dev:'+r['media_id'])
val={'error_count':len(errors),'errors':errors,'dev_total':len(rows),'unique_media_ids':len(set(ids)),'counts':dict(counts),'allowed_labels':sorted(allowed),'val_items':0,'holdout_items':0,'gt_sha256':sha}
(out/'dev_gt_validation.json').write_text(json.dumps(val,indent=2,ensure_ascii=False)+'\n')
if errors:raise SystemExit('\n'.join(errors))
print(json.dumps(freeze,ensure_ascii=False))
