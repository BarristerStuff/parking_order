#!/usr/bin/env python3
import csv,hashlib,json,pathlib
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm'); DATA=pathlib.Path('/home/yanbo/net_vlm_xunjian_dataset')
def sha(p):
 h=hashlib.sha256();
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
allow=list(csv.DictReader(open(V4/'contracts/dev_image_allowlist.csv'))); pilot=list(csv.DictReader(open(V4/'contracts/pilot_manifest.csv'))); forbidden=list(csv.DictReader(open(V4/'contracts/forbidden_split_metadata.csv')))
adapted=[json.loads(x) for x in open(V4/'inputs/pilot/adapted_inputs.jsonl')]
errors=[]
if len(allow)!=238: errors.append('ALLOWLIST_COUNT')
if len(pilot)!=60 or len({x['media_id'] for x in pilot})!=60: errors.append('PILOT_COUNT_OR_DUP')
if set(x['media_id'] for x in pilot)-set(x['media_id'] for x in allow): errors.append('PILOT_NOT_DEV_ALLOWLIST')
if set(x['media_id'] for x in pilot)&set(x['media_id'] for x in forbidden): errors.append('PILOT_FORBIDDEN_INTERSECTION')
if len(adapted)!=60: errors.append('ADAPTED_COUNT')
for x in adapted:
 if x['media_id'] not in {r['media_id'] for r in pilot}: errors.append('ADAPTED_OUTSIDE_PILOT:'+x['media_id'])
 if sha(x['source_path']) != x['image_sha256']: errors.append('SOURCE_SHA:'+x['media_id'])
 if len(x['batches']) != (len(x['kept_targets'])+2)//3: errors.append('BATCHING:'+x['media_id'])
 for b in x['batches']:
  if len(b['target_ids'])>3: errors.append('BATCH_GT3:'+x['media_id'])
summary={'status':'valid' if not errors else 'invalid','errors':errors,'dev_allowlist_rows':len(allow),'forbidden_metadata_rows':len(forbidden),'pilot_rows':len(pilot),'prepared_rows':len(adapted),'val_holdout_decode_performed_by_this_check':False,'source_sha_rechecked_for_dev_pilot':len(adapted),'cache_key_sha_present':sum(bool(x['cache_key_sha256']) for x in pilot)}
(V4/'contracts/formal_preflight.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2)); raise SystemExit(0 if not errors else 1)
