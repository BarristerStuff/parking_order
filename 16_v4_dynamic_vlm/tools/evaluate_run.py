#!/usr/bin/env python3
"""Join frozen visual references to one immutable V4 run and emit audit-ready metrics."""
from __future__ import annotations
import argparse,csv,json,pathlib,sys
from PIL import Image,ImageDraw,ImageFont
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm'); sys.path.insert(0,str(V4))
from evaluator.metrics import evaluate_dataset

def load_jsonl(p): return [json.loads(x) for x in open(p,encoding='utf-8') if x.strip()]
def write_json(p,x): pathlib.Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def percentile(vals,p):
 if not vals:return None
 vals=sorted(vals); k=(len(vals)-1)*p; lo=int(k); hi=min(lo+1,len(vals)-1); return vals[lo]+(vals[hi]-vals[lo])*(k-lo)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',required=True); ap.add_argument('--inputs',required=True); ap.add_argument('--outdir',required=True); args=ap.parse_args()
 run=pathlib.Path(args.run); inputs=pathlib.Path(args.inputs); out=pathlib.Path(args.outdir); out.mkdir(parents=True,exist_ok=True)
 refs=load_jsonl(V4/'reference/reference_images.jsonl'); pred=load_jsonl(run/'image_predictions.jsonl'); adapted={x['media_id']:x for x in load_jsonl(inputs/'adapted_inputs.jsonl')}
 pred_by={x['media_id']:x for x in pred}; prediction_images=[]
 for ref in refs:
  mid=ref['media_id']; p=dict(pred_by.get(mid,{'media_id':mid,'image_decision':'uncertain','protocol_status':'protocol_failure','protocol_issues':[{'code':'MISSING_PREDICTION'}],'targets':[]}))
  a=adapted[mid]; det=dict(ref.get('detector',{}));
  # Detector diagnostics are frozen visual/reference facts for this run; model output never changes them.
  det.update({'cache_source':'V2_DEV_NEW_LOCAL_YOLO11N','detector_cache_sha256':ref['detector_cache_sha256'],'raw_detection_rows':len(a['raw_detections']),'unique_candidate_targets':len(a['kept_targets']),'duplicate_raw_detection_count':len(a['suppressed_detections']),'false_detection_count':len(ref['detector'].get('false_detection_target_ids',[])),'false_detection_target_ids':ref['detector'].get('false_detection_target_ids',[]),'matched_target_ids':ref['detector'].get('matched_target_ids',[]),'missed_target_ids':ref['detector'].get('missed_target_ids',[])})
  if p.get('protocol_status')!='ok': det['unprocessed_target_ids']=[v['target_id'] for v in ref['vehicles'] if v.get('target_id') not in {t.get('target_id') for t in p.get('targets',[]) if isinstance(t,dict)}]
  else: det['unprocessed_target_ids']=[]
  p['detector']=det; p['detector_cache_sha256']=ref['detector_cache_sha256']; p['group']=ref['group']; p['image_sha256']=ref['image_sha256']; p['image_decision']='positive' if p.get('derived_label')=='positive' else 'negative' if p.get('derived_label')=='negative' else 'uncertain'; p['protocol_status']='ok' if p.get('required_target_schema_complete') is True else 'protocol_failure'; prediction_images.append(p)
 metrics=evaluate_dataset(refs,prediction_images); write_json(out/'metrics.json',metrics)
 # Save exact evaluator inputs used for independent replay.
 write_json(out/'evaluation_inputs.json',{'reference_images':refs,'prediction_images':prediction_images})
 with open(out/'errors.jsonl','w',encoding='utf-8') as f:
  for x in metrics['errors']: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
 fields=['media_id','group','target_id','category','reference_label','prediction_decision','detail']
 with open(out/'errors.csv','w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(metrics['errors'])
 # Flatten subgroup metrics.
 rows=[]
 for level,groups in metrics['subgroups'].items():
  for group,vals in groups.items():
   rows.append({'level':level,'group':group,'reviewed_count':vals.get('reviewed_image_count',vals.get('reviewed_vehicle_count')),'binary_count':vals.get('binary_gt_image_count',vals.get('binary_gt_vehicle_count')),'tp':vals['alert_confusion']['tp'],'fp':vals['alert_confusion']['fp'],'tn':vals['alert_confusion']['tn'],'fn':vals['alert_confusion']['fn'],'recall':vals['alert_confusion']['recall']['value'],'fpr':vals['alert_confusion']['fpr']['value'],'decisive_coverage':vals['decisive_coverage']['value']})
 with open(out/'subgroup_metrics.csv','w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 # Latency, including queue, local VLM elapsed, Ollama's load/eval timings, and preprocessing.
 logs=load_jsonl(run/'request_log.jsonl')
 prep=load_jsonl(inputs/'adapted_inputs.jsonl')
 lat={'requests':len(logs),'per_request_seconds':{'client_elapsed':{'p50':percentile([x['elapsed_seconds'] for x in logs],.5),'p95':percentile([x['elapsed_seconds'] for x in logs],.95)},'queue_wait':{'p50':percentile([x['queue_wait_seconds'] for x in logs],.5),'p95':percentile([x['queue_wait_seconds'] for x in logs],.95)},'ollama_load':{'p50':percentile([x['ollama_load_duration_seconds'] for x in logs if x.get('ollama_load_duration_seconds') is not None],.5),'p95':percentile([x['ollama_load_duration_seconds'] for x in logs if x.get('ollama_load_duration_seconds') is not None],.95)},'ollama_total':{'p50':percentile([x['ollama_total_duration_seconds'] for x in logs if x.get('ollama_total_duration_seconds') is not None],.5),'p95':percentile([x['ollama_total_duration_seconds'] for x in logs if x.get('ollama_total_duration_seconds') is not None],.95)}},'per_image_requests':{'p50':percentile([x['request_count'] for x in pred],.5),'p95':percentile([x['request_count'] for x in pred],.95)},'preprocess_seconds_per_image':{'p50':percentile([x['preprocess_seconds'] for x in prep],.5),'p95':percentile([x['preprocess_seconds'] for x in prep],.95)},'cold_load_note':'Ollama load_duration is reported by API; no separate warm-up request was subtracted; smoke request is excluded from pilot metrics.'}
 write_json(out/'latency.json',lat)
 # Representative error locators: original scene with reviewed target boxes; no label is drawn into model input.
 errdir=out/'error_images'; errdir.mkdir(exist_ok=True)
 font=ImageFont.load_default()
 seen=set()
 for e in metrics['errors']:
  mid=e.get('media_id');
  if not mid or mid in seen: continue
  if mid not in adapted: continue
  seen.add(mid); a=adapted[mid]; im=Image.open(a['source_path']).convert('RGB'); d=ImageDraw.Draw(im)
  for t in a['kept_targets']:
   color=(220,30,30) if t['target_id']==e.get('target_id') else (40,120,255)
   b=t['bbox']; d.rectangle(b,outline=color,width=5); d.text((b[0],max(0,b[1]-16)),t['target_id'],fill=color,font=font)
  path=errdir/f"{mid}_{e.get('category','error')}.jpg"; im.save(path,quality=90); e['locator_path']=str(path)
 # Re-write with locator paths if any.
 if metrics['errors']:
  with open(out/'errors_with_locators.jsonl','w',encoding='utf-8') as f:
   for e in metrics['errors']:
    f.write(json.dumps(e,ensure_ascii=False,sort_keys=True)+'\n')
 print(json.dumps({'images':len(refs),'predictions':len(prediction_images),'errors':len(metrics['errors']),'primary_image_confusion':metrics['image']['alert_confusion'],'vehicle_confusion':metrics['vehicle']['alert_confusion'],'schema_coverage':metrics['image']['reviewed_image_count'] and 1-sum(x['protocol_status']!='ok' for x in prediction_images)/len(prediction_images)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
