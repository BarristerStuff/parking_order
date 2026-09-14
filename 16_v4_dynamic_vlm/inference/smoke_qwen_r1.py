#!/usr/bin/env python3
import base64,hashlib,json,pathlib,time,uuid,requests
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm'); URL='http://192.168.20.62:11434/api/generate'; MODEL='qwen3.5:4b'
SCHEMA={'type':'object','additionalProperties':False,'required':['targets'],'properties':{'targets':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['target_id','vehicle_valid','evidence_sufficient','road_or_drive_aisle','occupies_two_bays','in_one_bay_or_designated_area','minor_line_or_nose_tail_only','normal_gate_queue','evidence'],'properties':{'target_id':{'type':'string'},'vehicle_valid':{'type':'string','enum':['yes','no','unclear']},'evidence_sufficient':{'type':'string','enum':['yes','no','unclear']},'road_or_drive_aisle':{'type':'string','enum':['yes','no','unclear']},'occupies_two_bays':{'type':'string','enum':['yes','no','unclear']},'in_one_bay_or_designated_area':{'type':'string','enum':['yes','no','unclear']},'minor_line_or_nose_tail_only':{'type':'string','enum':['yes','no','unclear']},'normal_gate_queue':{'type':'string','enum':['yes','no','unclear']},'evidence':{'type':'string'}}}}}}
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 b=next(json.loads(x) for x in open(V4/'inputs/pilot_r1/request_batches.jsonl') if len(json.loads(x)['target_ids'])==3)
 prompt=(V4/'contracts/prompt_v4_r1.txt').read_text()+'\nRequested target IDs: '+', '.join(b['target_ids'])+'\nReturn exactly one object in targets for each requested ID.'
 body={'model':MODEL,'prompt':prompt,'images':[base64.b64encode(open(b['composite_path'],'rb').read()).decode()],'stream':False,'think':False,'format':SCHEMA,'options':{'temperature':0,'num_ctx':8192,'num_predict':768},'keep_alive':'30m'}
 rid='smoke-r1-'+uuid.uuid4().hex; t=time.time(); status=None; error=None; raw=''
 try:
  r=requests.post(URL,json=body,timeout=(10,240)); status=r.status_code; raw=r.text; r.raise_for_status()
 except Exception as e: error=repr(e)
 rec={'request_id':rid,'candidate_id':'V4_R1_GLOBAL_TARGET_CONTEXT_COMPOSITE','target_ids':b['target_ids'],'image_count':1,'input_sha256s':[sha(b['composite_path'])],'started_unix':t,'ended_unix':time.time(),'http_status':status,'error':error,'raw_response':raw}
 (V4/'logs'/(rid+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:rec[k] for k in ['request_id','target_ids','image_count','http_status','error']},ensure_ascii=False,indent=2)); print(raw[:2500]); raise SystemExit(1 if error else 0)
if __name__=='__main__':main()
