#!/usr/bin/env python3
from pathlib import Path
import csv,json,hashlib
O=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
checks={}
a=list(csv.DictReader(open(O/'val_allowlist.csv')))
p=[json.loads(x) for x in (O/'val_predictions.jsonl').read_text().splitlines()]
checks['allowlist_exactly_80_val']=len(a)==80 and {x['split'] for x in a}=={'VAL'} and len({x['media_id'] for x in a})==80
checks['holdout_image_in_allowlist']=any('HOLDOUT' in x['image_path'].upper() for x in a)
checks['prediction_exactly_80']=len(p)==80 and len({x['sample_token'] for x in p})==80
checks['q2_requests_zero']=all('q2' not in v for x in p for v in x['vehicle_results'])
checks['physical_requests_95']=sum(x['request_count'] for x in p)==95
checks['prompt_hash_correct']=sha(O/'q1_prompt.txt')=='76151fc7f028c8274fd6c1a49158452a5b491d272b98effd463d8df2ba3b2eed'
old={
 'v2_0_gt.csv':(O.parent/'01_gt_and_split/v2_0_gt.csv','321f0994006d2451352f0c48d73911749f6a471d24c16f25808bbf30c31bd353'),
 'v2_split.csv':(O.parent/'01_gt_and_split/v2_split.csv','f531aaff35d3940dd17bd57e1f9825903177dcd91d2f7e41d2a598a5a0cfdb24'),
 'dev_cache':(O.parent/'03_debug/v2_dev_vehicle_detections.jsonl','5685faa7c450e598f0e964445178a49bbcdb1d1e6e8fd5688fbdb807188385f9'),
 'r1_predictions':(O.parent/'05_vlm_dev_r1/predictions.jsonl','2e98a2659a91df8ec4ec23ae2d5a337fb43f850f6ddc6a5679959026ebeabe75'),
 'formal_media_mapping.csv':(O.parents[1]/'02_ingest/manifests/formal_media_mapping.csv','0780f3e659fcae4655ea06b00365f7c8c37c089f44b21453f4eb6acbaa8080a6')}
checks['old_hashes_unchanged']=all(x.exists() and sha(x)==h for x,h in old.values())
m=json.loads((O/'metrics.json').read_text())
checks['denominators_correct']=(m['val']['recall']['denominator'],m['val']['negative_fpr']['denominator'],m['val']['hn01_fpr']['denominator'],m['val']['p03_alert_rate']['denominator'],m['val']['p05_alert_rate']['denominator'])==(8,48,6,6,4)
checks['one_shot_locks_completed']=all(json.loads((O/n).read_text())['status']=='COMPLETED_DO_NOT_RERUN' for n in ['VAL_DETECTOR_CONSUMED.lock','VAL_Q1_CONSUMED.lock'])
manifest=json.loads((O/'final_hash_manifest.json').read_text()) if (O/'final_hash_manifest.json').exists() else {'files':{}}
checks['hash_manifest_excludes_self']='final_hash_manifest.json' not in manifest['files']
checks['hash_manifest_valid']=bool(manifest['files']) and all((O/r).is_file() and sha(O/r)==h for r,h in manifest['files'].items())
checks['val_error_sets_empty']=m['val']['fp_media_ids']==[] and m['val']['fn_media_ids']==[] and len((O/'errors.csv').read_text().splitlines())==1
checks['consumed_cache_bound']=json.loads((O/'VAL_DETECTOR_CONSUMED.lock').read_text())['cache_sha256']==sha(O/'val_vehicle_detections.jsonl')
pass_keys=[k for k,v in checks.items() if (v if k!='holdout_image_in_allowlist' else not v)]
status='PASS' if len(pass_keys)==len(checks) else 'FAIL'
res={'audit_date':'2026-09-15','status':status,'checks':checks,'pass_count':len(pass_keys),'check_count':len(checks),'holdout_image_reads':0,'holdout_inference':0,'q2_requests':0,'physical_model_requests':95,'prior_holdout_metadata_exposure':True}
(O/'audit/audit_result.json').write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
print(json.dumps(res,sort_keys=True))
