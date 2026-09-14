#!/usr/bin/env python3
import hashlib,json,pathlib,time
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
files=['reference_instances.jsonl','reference_images.jsonl','detector_review_diagnostics.jsonl','reference_instances.csv','reference_images.csv','review_log.csv','recheck_log.csv','reference_summary.json']
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
# Freeze only after the final reference files are written.
manifest={'status':'FROZEN_BEFORE_FORMAL_MODEL_REQUESTS','frozen_at_unix':time.time(),'files':{f:sha(V4/'reference'/f) for f in files}}
(V4/'reference/REFERENCE_FREEZE.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps(manifest,indent=2))
