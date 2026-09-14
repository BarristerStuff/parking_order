#!/usr/bin/env python3
from __future__ import annotations
import base64, json, pathlib, sys, time, uuid
import requests
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
URL='http://192.168.20.62:11434/api/generate'; MODEL='qwen3.5:4b'
SCHEMA={'type':'object','additionalProperties':False,'required':['targets'],'properties':{'targets':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['target_id','vehicle_valid','evidence_sufficient','road_or_drive_aisle','occupies_two_bays','in_one_bay_or_designated_area','minor_line_or_nose_tail_only','normal_gate_queue','evidence'],'properties':{'target_id':{'type':'string'},'vehicle_valid':{'type':'string','enum':['yes','no','unclear']},'evidence_sufficient':{'type':'string','enum':['yes','no','unclear']},'road_or_drive_aisle':{'type':'string','enum':['yes','no','unclear']},'occupies_two_bays':{'type':'string','enum':['yes','no','unclear']},'in_one_bay_or_designated_area':{'type':'string','enum':['yes','no','unclear']},'minor_line_or_nose_tail_only':{'type':'string','enum':['yes','no','unclear']},'normal_gate_queue':{'type':'string','enum':['yes','no','unclear']},'evidence':{'type':'string'}}}}}}

def enc(p): return base64.b64encode(pathlib.Path(p).read_bytes()).decode('ascii')
def main():
 batch=next(json.loads(x) for x in open(V4/'inputs/pilot/request_batches.jsonl') if len(json.loads(x)['target_ids'])==3)
 prompt=(V4/'contracts/prompt_v4_r0.txt').read_text()+'\nRequested target IDs: '+', '.join(batch['target_ids'])+'\nReturn exactly one object in targets for each requested ID.'
 images=[enc(batch['panorama_path'])]+[enc(p) for p in batch['crop_paths']]
 body={'model':MODEL,'prompt':prompt,'images':images,'stream':False,'think':False,'format':SCHEMA,'options':{'temperature':0,'num_ctx':8192,'num_predict':768},'keep_alive':'30m'}
 rid='smoke-'+uuid.uuid4().hex
 started=time.time(); status=None; err=None; text=''
 try:
  r=requests.post(URL,json=body,timeout=(10,240)); status=r.status_code; text=r.text; r.raise_for_status()
 except Exception as e: err=repr(e)
 ended=time.time()
 out={'request_id':rid,'candidate_id':'V4_R0_GLOBAL_TARGET_CONTEXT','endpoint':URL,'model':MODEL,'target_ids':batch['target_ids'],'image_count':len(images),'input_sha256s':[__import__('hashlib').sha256(base64.b64decode(x)).hexdigest() for x in images],'started_unix':started,'ended_unix':ended,'elapsed_seconds':ended-started,'http_status':status,'error':err,'raw_response':text}
 p=V4/'logs'/(rid+'.json'); p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['request_id','target_ids','image_count','elapsed_seconds','http_status','error']},ensure_ascii=False,indent=2))
 print('raw_response_prefix=',text[:2000])
 if err: raise SystemExit(1)
main()
