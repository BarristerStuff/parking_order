#!/usr/bin/env python3
"""Run the frozen V4 candidate directly against Ollama on a frozen DEV manifest.

The request body deliberately contains only a prompt and base64 image bytes; dataset
identifiers and labels remain in the local audit log and never reach the model.
"""
from __future__ import annotations
import argparse, base64, concurrent.futures, csv, hashlib, importlib.util, json, pathlib, threading, time, uuid, sys
from datetime import datetime, timezone
import requests

V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
sys.path.insert(0,str(V4))
try:
 from evaluator.decision import decide_target as frozen_decide_target
except Exception:
 frozen_decide_target = None
URL='http://192.168.20.62:11434/api/generate'; MODEL='qwen3.5:4b'
FIELDS=['target_id','vehicle_valid','evidence_sufficient','road_or_drive_aisle','occupies_two_bays','in_one_bay_or_designated_area','minor_line_or_nose_tail_only','normal_gate_queue','evidence']
ENUMS={x:{'yes','no','unclear'} for x in FIELDS[1:-1]}
SCHEMA={'type':'object','additionalProperties':False,'required':['targets'],'properties':{'targets':{'type':'array','items':{'type':'object','additionalProperties':False,'required':FIELDS,'properties':{'target_id':{'type':'string'},'vehicle_valid':{'type':'string','enum':['yes','no','unclear']},'evidence_sufficient':{'type':'string','enum':['yes','no','unclear']},'road_or_drive_aisle':{'type':'string','enum':['yes','no','unclear']},'occupies_two_bays':{'type':'string','enum':['yes','no','unclear']},'in_one_bay_or_designated_area':{'type':'string','enum':['yes','no','unclear']},'minor_line_or_nose_tail_only':{'type':'string','enum':['yes','no','unclear']},'normal_gate_queue':{'type':'string','enum':['yes','no','unclear']},'evidence':{'type':'string'}}}}}}
_tls=threading.local()

def enc(p): return base64.b64encode(pathlib.Path(p).read_bytes()).decode('ascii')
def sha_file(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def local_decide(x):
 # Kept in the runner as a fail-safe; evaluator/decisioner is independently tested.
 missing=[k for k in FIELDS if k not in x]
 if missing: return {'derived_label':'protocol_failure','reason':'MISSING_FIELD:'+','.join(missing)}
 if any(k != 'evidence' and not isinstance(x[k],str) for k in FIELDS): return {'derived_label':'protocol_failure','reason':'BAD_FIELD_TYPE'}
 if any(x[k] not in ENUMS[k] for k in ENUMS): return {'derived_label':'protocol_failure','reason':'BAD_ENUM'}
 if x['vehicle_valid']=='no': return {'derived_label':'ignore','reason':'VEHICLE_INVALID'}
 if x['vehicle_valid']=='unclear': return {'derived_label':'uncertain','reason':'VEHICLE_IDENTITY_UNCLEAR'}
 if x['evidence_sufficient']!='yes': return {'derived_label':'uncertain','reason':'INSUFFICIENT_EVIDENCE'}
 if x['normal_gate_queue']=='yes': return {'derived_label':'negative_gate_queue','reason':'NORMAL_GATE_QUEUE'}
 if x['normal_gate_queue']=='unclear': return {'derived_label':'uncertain','reason':'GATE_QUEUE_UNCLEAR'}
 road=x['road_or_drive_aisle']; two=x['occupies_two_bays']; one=x['in_one_bay_or_designated_area']; minor=x['minor_line_or_nose_tail_only']
 if minor=='yes' and two=='yes': return {'derived_label':'uncertain','reason':'SEMANTIC_CONFLICT'}
 if one=='yes' and (road=='yes' or two=='yes'): return {'derived_label':'uncertain','reason':'SEMANTIC_CONFLICT'}
 if minor=='yes' and road=='yes': return {'derived_label':'uncertain','reason':'SEMANTIC_CONFLICT'}
 if road=='yes': return {'derived_label':'positive_road','reason':'ROAD_RELATION'}
 if two=='yes': return {'derived_label':'positive_two_bays','reason':'TWO_BAY_RELATION'}
 if road=='no' and two=='no' and (one=='yes' or minor=='yes'): return {'derived_label':'negative','reason':'EXPLICIT_IN_BAY_OR_MINOR_ONLY'}
 return {'derived_label':'uncertain','reason':'PARKING_RELATION_UNCLEAR'}

def parse_payload(raw, expected):
 try: payload=json.loads(raw)
 except Exception as e: return {'status':'protocol_failure','reason':'JSON_PARSE_ERROR:'+type(e).__name__,'targets':[],'payload':None}
 if not isinstance(payload,dict) or set(payload)!={'targets'} or not isinstance(payload['targets'],list): return {'status':'protocol_failure','reason':'TOP_LEVEL_SCHEMA_ERROR','targets':[],'payload':payload}
 ts=payload['targets']; ids=[x.get('target_id') if isinstance(x,dict) else None for x in ts]
 if len(ts)!=len(expected) or any(not isinstance(x,dict) for x in ts) or len(set(ids))!=len(ids) or set(ids)!=set(expected):
  return {'status':'protocol_failure','reason':'TARGET_SET_MISMATCH','targets':ts,'payload':payload}
 for x in ts:
  if set(x)!=set(FIELDS): return {'status':'protocol_failure','reason':'TARGET_FIELD_SCHEMA_ERROR','targets':ts,'payload':payload}
  if any(not isinstance(x[k],str) for k in FIELDS): return {'status':'protocol_failure','reason':'TARGET_FIELD_TYPE_ERROR','targets':ts,'payload':payload}
  if any(x[k] not in ENUMS[k] for k in ENUMS): return {'status':'protocol_failure','reason':'TARGET_ENUM_ERROR','targets':ts,'payload':payload}
  if not x['target_id'] or not isinstance(x['evidence'],str): return {'status':'protocol_failure','reason':'TARGET_VALUE_ERROR','targets':ts,'payload':payload}
 return {'status':'ok','reason':'','targets':ts,'payload':payload}

def run_one(batch, prompt, request_no, timeout, submitted_epoch):
 rid=f'r{request_no:04d}-{uuid.uuid4().hex[:12]}'
 image_paths=[batch['composite_path']] if batch.get('composite_path') else [batch['panorama_path']]+batch['crop_paths']; input_shas=[sha_file(p) for p in image_paths]
 body={'model':MODEL,'prompt':prompt+'\nRequested target IDs: '+', '.join(batch['target_ids'])+'\nReturn exactly one object in targets for each requested ID.', 'images':[enc(p) for p in image_paths], 'stream':False,'think':False,'format':SCHEMA,'options':{'temperature':0,'num_ctx':8192,'num_predict':768},'keep_alive':'30m'}
 started=time.time(); started_iso=utc(); queue_wait=started-submitted_epoch; status=None; err=None; raw=''; envelope=None; retry_count=0; retry_reason=None
 for attempt in range(2):
  try:
   resp=requests.post(URL,json=body,timeout=(10,timeout)); status=resp.status_code; raw=resp.text
   if status >= 500 and attempt==0:
    # Server-side processing may already be in flight; do not retry response errors.
    err=f'HTTP_{status}'; break
   resp.raise_for_status(); envelope=resp.json(); raw_model=envelope.get('response','') if isinstance(envelope,dict) else ''
   parsed=parse_payload(raw_model,batch['target_ids'])
   break
  except requests.exceptions.ConnectionError as e:
   if attempt==0:
    retry_count=1; retry_reason='CONNECTION_ERROR'; continue
   err=repr(e); parsed={'status':'protocol_failure','reason':'TRANSPORT_CONNECTION_ERROR','targets':[],'payload':None}
  except requests.exceptions.ReadTimeout as e:
   # Do not retry: server execution state is unknown and retry could exceed the physical budget.
   err=repr(e); parsed={'status':'protocol_failure','reason':'TIMEOUT_SERVER_STATE_UNKNOWN','targets':[],'payload':None}; break
  except Exception as e:
   err=repr(e); parsed={'status':'protocol_failure','reason':'HTTP_OR_RESPONSE_ERROR','targets':[],'payload':None}; break
 else:
  parsed={'status':'protocol_failure','reason':'TRANSPORT_RETRY_EXHAUSTED','targets':[],'payload':None}
 ended=time.time(); ended_iso=utc()
 if 'parsed' not in locals(): parsed={'status':'protocol_failure','reason':err or 'NO_PARSE','targets':[],'payload':None}
 rec={'request_id':rid,'request_no':request_no,'candidate_id':'V4_R0_GLOBAL_TARGET_CONTEXT','batch_id':batch['batch_id'],'media_id':batch['media_id'],'group_key':batch['group_key'],'image_sha256':batch['image_sha256'],'target_ids':batch['target_ids'],'input_paths_local':image_paths,'input_sha256s':input_shas,'submitted_unix':submitted_epoch,'queue_wait_seconds':queue_wait,'started_at_utc':started_iso,'ended_at_utc':ended_iso,'elapsed_seconds':ended-started,'http_status':status,'error':err,'retry_count':retry_count,'retry_reason':retry_reason,'actual_model':(envelope or {}).get('model') if isinstance(envelope,dict) else None,'ollama_total_duration_seconds':((envelope or {}).get('total_duration') or 0)/1e9 if isinstance(envelope,dict) else None,'ollama_load_duration_seconds':((envelope or {}).get('load_duration') or 0)/1e9 if isinstance(envelope,dict) else None,'ollama_prompt_eval_duration_seconds':((envelope or {}).get('prompt_eval_duration') or 0)/1e9 if isinstance(envelope,dict) else None,'ollama_eval_duration_seconds':((envelope or {}).get('eval_duration') or 0)/1e9 if isinstance(envelope,dict) else None,'parse_status':parsed['status'],'parse_reason':parsed['reason'],'raw_response':raw,'model_payload':parsed.get('payload')}
 return rec, parsed

def aggregate(image_recs, expected_ids):
 targets=[]; incomplete=[]; protocol=[]
 for rec, parsed in image_recs:
  if parsed['status']!='ok': protocol.append(rec['request_id']); incomplete.extend([x for x in rec['target_ids'] if x not in {t.get('target_id') for t in parsed.get('targets',[]) if isinstance(t,dict)}]); continue
  for x in parsed['targets']:
   d=frozen_decide_target(x) if frozen_decide_target else local_decide(x); targets.append({'media_id':rec['media_id'],'image_sha256':rec['image_sha256'],'batch_id':rec['batch_id'],'request_id':rec['request_id'],'target_id':x['target_id'],'raw_model_fields':x,'raw_fields':x,'decision':d.get('decision',d.get('derived_label')),'reason':d.get('reason'),'derived_label':d.get('decision',d.get('derived_label')),'derived_reason':d.get('reason'),'protocol_status':d.get('protocol_status','ok'),'protocol_issues':d.get('protocol_issues',[])})
 got={x['target_id'] for x in targets}
 missing=sorted(set(expected_ids)-got)
 if missing: incomplete.extend(missing)
 labels=[x['derived_label'] for x in targets if x['target_id'] in expected_ids]
 if any(x.startswith('positive_') for x in labels): label='positive'; reason='ANY_RELIABLE_POSITIVE'
 elif missing or protocol or any(x=='uncertain' for x in labels): label='uncertain'; reason='INCOMPLETE_OR_UNCERTAIN_TARGET'
 elif any(x not in {'negative','negative_gate_queue','ignore'} for x in labels): label='uncertain'; reason='UNEXPECTED_TARGET_STATE'
 elif any(x in {'negative','negative_gate_queue'} for x in labels): label='negative'; reason='ALL_JUDGEABLE_NEGATIVE'
 else: label='uncertain'; reason='NO_VALID_TARGETS_OR_DETECTOR_GAP'
 return targets, {'media_id':image_recs[0][0]['media_id'],'image_sha256':image_recs[0][0]['image_sha256'],'group_key':image_recs[0][0]['group_key'],'expected_target_ids':expected_ids,'observed_target_ids':sorted(got),'required_target_schema_complete':not missing and not protocol,'protocol_failure_requests':protocol,'missing_target_ids':missing,'derived_label':label,'derived_reason':reason,'request_count':len(image_recs),'targets':targets}

def classify_image(batch: dict, *, prompt: str | None = None, request_no: int = 1, timeout: float = 240.0) -> tuple[dict, dict]:
    """Reusable single-image/batch classifier using the frozen direct Ollama path."""
    if prompt is None:
        prompt = (V4 / "contracts" / "prompt_v4_r0.txt").read_text(encoding="utf-8")
    return run_one(batch, prompt, request_no, timeout, time.time())

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--batches',required=True); ap.add_argument('--prompt',default=str(V4/'contracts/prompt_v4_r0.txt')); ap.add_argument('--outdir',required=True); ap.add_argument('--max-workers',type=int,default=2); ap.add_argument('--timeout',type=float,default=240); args=ap.parse_args()
 assert 1<=args.max_workers<=2
 out=pathlib.Path(args.outdir); out.mkdir(parents=True,exist_ok=True)
 batches=[json.loads(x) for x in open(args.batches) if x.strip()]
 prompt=pathlib.Path(args.prompt).read_text(encoding='utf-8')
 start=time.time(); results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
  futs=[]
  for i,b in enumerate(batches):
   submitted=time.time(); futs.append(ex.submit(run_one,b,prompt,i+1,args.timeout,submitted))
  for f in concurrent.futures.as_completed(futs): results.append(f.result())
 results.sort(key=lambda x:x[0]['request_no'])
 (out/'request_log.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r,_ in results),encoding='utf-8')
 all_targets=[]; images=[]
 by_media={}
 for r,p in results: by_media.setdefault(r['media_id'],[]).append((r,p))
 for mid,rs in by_media.items():
  rs.sort(key=lambda x:x[0]['request_no']); expected=[]
  # expected IDs are the union of all batch-local targets for this image.
  for r,_ in rs: expected.extend(r['target_ids'])
  expected=list(dict.fromkeys(expected))
  ts,img=aggregate(rs,expected); all_targets.extend(ts); images.append(img)
 (out/'target_predictions.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in all_targets),encoding='utf-8')
 (out/'image_predictions.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in sorted(images,key=lambda x:x['media_id'])),encoding='utf-8')
 summary={'candidate_id':'V4_R0_GLOBAL_TARGET_CONTEXT','batches_expected':len(batches),'physical_model_requests':len(results),'successful_http_requests':sum(r['http_status']==200 for r,_ in results),'parse_ok_requests':sum(r['parse_status']=='ok' for r,_ in results),'protocol_failure_requests':sum(r['parse_status']!='ok' for r,_ in results),'transport_retries':sum(r['retry_count'] for r,_ in results),'images':len(images),'target_predictions':len(all_targets),'required_target_schema_coverage':sum(x['required_target_schema_complete'] for x in images)/len(images) if images else None,'max_client_concurrency':args.max_workers,'elapsed_wall_seconds':time.time()-start,'endpoint':URL,'model':MODEL,'batches_sha256':sha_file(args.batches),'prompt_sha256':sha_file(args.prompt)}
 (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
