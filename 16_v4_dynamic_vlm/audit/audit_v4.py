#!/usr/bin/env python3
"""Independent audit of a V4 pilot; integrity is separated from model result findings."""
from __future__ import annotations
import argparse,csv,hashlib,json,pathlib
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
def sha(p):
 h=hashlib.sha256();
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def jl(p): return [json.loads(x) for x in open(p,encoding='utf-8') if x.strip()]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',required=True); ap.add_argument('--inputs',required=True); ap.add_argument('--metrics',required=True); args=ap.parse_args()
 run=pathlib.Path(args.run); inputs=pathlib.Path(args.inputs); metricdir=pathlib.Path(args.metrics); errors=[]; warnings=[]; checks={}; findings={}
 def need(p):
  ok=pathlib.Path(p).exists()
  if not ok: errors.append('MISSING:'+str(p))
  return ok
 required=[V4/'contracts/dev_image_allowlist.csv',V4/'contracts/pilot_manifest.csv',V4/'contracts/forbidden_split_metadata.csv',V4/'contracts/run_contract.json',V4/'reference/REFERENCE_FREEZE.json',V4/'reference/reference_images.jsonl',V4/'reference/reference_instances.jsonl',inputs/'adapted_inputs.jsonl',inputs/'request_batches.jsonl',run/'request_log.jsonl',run/'image_predictions.jsonl',run/'target_predictions.jsonl',run/'run_summary.json',metricdir/'metrics.json',metricdir/'evaluation_inputs.json']
 if not all(need(p) for p in required):
  result={'status':'FAIL_INTEGRITY','checks':checks,'errors':errors,'warnings':warnings,'findings':findings}; (V4/'audit/audit_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); return 1
 allow=list(csv.DictReader(open(V4/'contracts/dev_image_allowlist.csv'))); pilot=list(csv.DictReader(open(V4/'contracts/pilot_manifest.csv'))); forbidden=list(csv.DictReader(open(V4/'contracts/forbidden_split_metadata.csv'))); contract=json.load(open(V4/'contracts/run_contract.json')); freeze=json.load(open(V4/'reference/REFERENCE_FREEZE.json')); refs=jl(V4/'reference/reference_images.jsonl'); inst=jl(V4/'reference/reference_instances.jsonl'); adapted=jl(inputs/'adapted_inputs.jsonl'); batches=jl(inputs/'request_batches.jsonl'); logs=jl(run/'request_log.jsonl'); raw_preds=jl(run/'image_predictions.jsonl'); raw_tpreds=jl(run/'target_predictions.jsonl'); summary=json.load(open(run/'run_summary.json')); metrics=json.load(open(metricdir/'metrics.json')); eval_inputs=json.load(open(metricdir/'evaluation_inputs.json')); preds=eval_inputs['prediction_images'];
 allow_ids={x['media_id'] for x in allow}; pilot_ids={x['media_id'] for x in pilot}; forbidden_ids={x['media_id'] for x in forbidden}; ref_ids={x['media_id'] for x in refs}; pred_ids={x['media_id'] for x in preds}
 checks.update({'pilot_exactly_60':len(pilot)==60 and len(pilot_ids)==60,'pilot_dev_allowlist_subset':pilot_ids<=allow_ids,'pilot_forbidden_intersection_empty':not(pilot_ids&forbidden_ids),'all_pilot_split_dev':all(x['split']=='DEV' for x in pilot),'prepared_exactly_pilot':{x['media_id'] for x in adapted}==pilot_ids,'references_exactly_pilot':ref_ids==pilot_ids,'predictions_exactly_pilot':pred_ids==pilot_ids,'reference_count_matches_pilot':len(refs)==60})
 if not all(checks[k] for k in ['pilot_exactly_60','pilot_dev_allowlist_subset','pilot_forbidden_intersection_empty','all_pilot_split_dev','prepared_exactly_pilot','references_exactly_pilot','predictions_exactly_pilot','reference_count_matches_pilot']): errors.append('SPLIT_OR_COVERAGE_INTEGRITY')
 mismatches=[]
 for name,expected in freeze.get('files',{}).items():
  p=V4/'reference'/name
  if not p.exists() or sha(p)!=expected: mismatches.append(name)
 checks['reference_files_match_freeze']=not mismatches
 checks['reference_basis_consistent']=all(x.get('label_basis')=='AI_VISUAL_REVIEWED_PROVISIONAL' and x.get('human_gold') is False for x in refs+inst)
 checks['all_reviews_complete']=len(refs)==60 and all(x.get('review_status')=='REVIEWED_PIXELS_ORIGINAL_PLUS_CONTEXT_CROP' for x in refs)
 if mismatches or not checks['reference_basis_consistent'] or not checks['all_reviews_complete']: errors.append('REFERENCE_FREEZE_OR_REVIEW_INTEGRITY')
 checks['prepared_source_hashes_match']=all(sha(x['source_path'])==x['image_sha256'] for x in adapted if pathlib.Path(x['source_path']).exists())
 checks['batch_size_le_3']=all(len(x['target_ids'])<=3 for x in batches)
 checks['cache_and_target_mapping_present']=all(all('raw_detection_id' in t for t in x['raw_detections']) and all('target_id' in t for t in x['kept_targets']) for x in adapted)
 checks['reference_cache_hash_consistent']=all(x.get('detector_cache_sha256')==contract['detector_cache_sha256'] for x in refs)
 if not all(checks[k] for k in ['prepared_source_hashes_match','batch_size_le_3','cache_and_target_mapping_present','reference_cache_hash_consistent']): errors.append('INPUT_OR_CACHE_MAPPING_INTEGRITY')
 checks['physical_request_count_matches_summary']=len(logs)==summary.get('physical_model_requests')==len(batches)
 checks['request_ids_unique']=len({x.get('request_id') for x in logs})==len(logs)
 checks['client_concurrency_declared_le_2']=summary.get('max_client_concurrency',99)<=2
 checks['transport_retries_le_one_each']=all(int(x.get('retry_count',0))<=1 for x in logs)
 checks['no_semantic_retry_reason']=not any(x.get('retry_reason') not in (None,'CONNECTION_ERROR') for x in logs)
 checks['model_success_identity_correct']=all(x.get('http_status')!=200 or x.get('actual_model')==contract['model'] for x in logs)
 checks['request_input_hashes_match_files']=all(all(sha(p)==h for p,h in zip(x.get('input_paths_local',[]),x.get('input_sha256s',[]))) for x in logs)
 if not all(checks[k] for k in ['physical_request_count_matches_summary','request_ids_unique','client_concurrency_declared_le_2','transport_retries_le_one_each','no_semantic_retry_reason','model_success_identity_correct','request_input_hashes_match_files']): errors.append('REQUEST_INTEGRITY')
 prompt=(V4/'contracts'/('prompt_v4_r1.txt' if 'pilot_r1' in str(inputs) else 'prompt_v4_r0.txt')).read_text(encoding='utf-8')
 checks['prompt_does_not_include_dataset_values']=not any(x['media_id'] in prompt or x['group_key'] in prompt or x['image_sha256'] in prompt for x in pilot)
 if not checks['prompt_does_not_include_dataset_values']: errors.append('PROMPT_DATASET_VALUE_LEAK')
 if 'pilot_r1' in str(inputs):
  r1f=V4/'contracts/r1_protocol_freeze.json'
  checks['r1_protocol_freeze_present']=r1f.exists()
  if r1f.exists():
   rf=json.load(open(r1f))
   def fsha(q):
    h=hashlib.sha256();
    with pathlib.Path(q).open('rb') as f:
     for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
   checks['r1_protocol_hashes_match']=rf.get('prompt_sha256')==fsha(V4/'contracts/prompt_v4_r1.txt') and rf.get('batches_sha256')==fsha(inputs/'request_batches.jsonl') and rf.get('prepared_inputs_sha256')==fsha(inputs/'adapted_inputs.jsonl')
   checks['r1_only_input_protocol_change_declared']=rf.get('change_dimension')=='input_protocol_only' and rf.get('same 60 pilot media IDs',None) is None
   checks['r1_composite_one_image_per_request']=all(len(x.get('input_sha256s',[]))==1 for x in logs)
   checks['r1_candidate_metadata_corrected']=all(x.get('candidate_id')=='V4_R1_GLOBAL_TARGET_CONTEXT_COMPOSITE' for x in logs)
   if not all(checks[k] for k in ['r1_protocol_hashes_match','r1_only_input_protocol_change_declared','r1_composite_one_image_per_request','r1_candidate_metadata_corrected']): errors.append('R1_PROTOCOL_FREEZE_INTEGRITY')

 # Evaluation-input integrity and independent result recompute.
 checks['evaluation_cache_hashes_match']=all(x.get('detector_cache_sha256')==contract['detector_cache_sha256'] for x in preds)
 checks['evaluation_prediction_ids_match']=len({x['media_id'] for x in preds})==len(preds)==60
 if not checks['evaluation_cache_hashes_match'] or not checks['evaluation_prediction_ids_match']: errors.append('EVALUATION_JOIN_INTEGRITY')
 # Findings are deliberately not treated as audit corruption: they are the experimental result.
 findings['all_http_success']=all(x.get('http_status')==200 for x in logs); findings['http_status_counts']={str(s):sum(x.get('http_status')==s for x in logs) for s in sorted({x.get('http_status') for x in logs},key=str)}
 findings['raw_parse_ok_rate']={'numerator':sum(x.get('parse_status')=='ok' for x in logs),'denominator':len(logs)}
 findings['required_target_schema_coverage']={'numerator':sum(x.get('required_target_schema_complete') is True for x in preds),'denominator':len(preds)}
 # Recompute image alert confusion from frozen reference + evaluator's exact merged prediction records.
 pby={x['media_id']:x for x in preds}; primary=[x for x in refs if x.get('label') in {'positive','negative'}]; tp=fp=tn=fn=0
 for r in primary:
  alert=pby[r['media_id']].get('image_decision')=='positive'
  if r['label']=='positive': tp+=int(alert); fn+=int(not alert)
  else: fp+=int(alert); tn+=int(not alert)
 recomputed={'tp':tp,'fp':fp,'tn':tn,'fn':fn,'support':tp+fp+tn+fn}
 findings['independent_primary_image_confusion']=recomputed
 ac=metrics.get('image',{}).get('alert_confusion',{}); checks['metrics_match_independent_recompute']=(ac.get('tp'),ac.get('fp'),ac.get('tn'),ac.get('fn'))==(tp,fp,tn,fn)
 if not checks['metrics_match_independent_recompute']: errors.append('METRICS_RECOMPUTE_MISMATCH')
 findings.update({'reference_images':len(refs),'reference_vehicles':len(inst),'raw_detection_rows':sum(len(x['raw_detections']) for x in adapted),'unique_targets':sum(len(x['kept_targets']) for x in adapted),'duplicate_suppressed':sum(len(x['suppressed_detections']) for x in adapted),'physical_requests':len(logs),'parse_ok_requests':sum(x.get('parse_status')=='ok' for x in logs),'forbidden_intersection_count':len(pilot_ids&forbidden_ids)})
 result={'status':'PASS_INTEGRITY' if not errors else 'FAIL_INTEGRITY','checks':checks,'errors':errors,'warnings':warnings,'findings':findings,'contract_sha256':sha(V4/'contracts/run_contract.json'),'pilot_manifest_sha256':sha(V4/'contracts/pilot_manifest.csv'),'reference_freeze_sha256':sha(V4/'reference/REFERENCE_FREEZE.json'),'request_log_sha256':sha(run/'request_log.jsonl'),'prediction_sha256':sha(run/'image_predictions.jsonl')}
 (V4/'audit/audit_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if not errors else 1
if __name__=='__main__':raise SystemExit(main())
