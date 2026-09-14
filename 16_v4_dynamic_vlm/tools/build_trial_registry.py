import json,pathlib,hashlib,collections
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
def load(p): return json.load(open(p))
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
r=[]
for rev,candidate in [('r0','V4_R0_GLOBAL_TARGET_CONTEXT'),('r1','V4_R1_GLOBAL_TARGET_CONTEXT_COMPOSITE')]:
 s=load(V4/f'outputs/pilot_{rev}/run_summary.json'); m=load(V4/f'metrics/pilot_{rev}/metrics.json'); a=load(V4/f'audit/audit_result_{rev}.json')
 r.append({'trial_id':f'pilot_{rev}','candidate_id':candidate,'pilot_manifest_sha256':sha(V4/'contracts/pilot_manifest.csv'),'batches_sha256':s['batches_sha256'],'prompt_sha256':s['prompt_sha256'],'physical_requests':s['physical_model_requests'],'successful_http':s['successful_http_requests'],'parse_ok':s['parse_ok_requests'],'protocol_failures':s['protocol_failure_requests'],'max_client_concurrency':s['max_client_concurrency'],'image_alert_confusion':m['image']['alert_confusion'],'vehicle_alert_confusion':m['vehicle']['alert_confusion'],'vehicle_metrics':{k:m['vehicle'][k] for k in ['road_positive_alert_recall','road_positive_subtype_accuracy','two_bay_positive_alert_recall','two_bay_positive_subtype_accuracy','ordinary_parking_fpr','line_minor_nose_tail_fpr','gate_queue_fpr','decisive_coverage','protocol_failure_rate','visual_uncertain_rate','semantic_uncertain_rate']},'error_category_counts':dict(collections.Counter(x.get('category') for x in m['errors'])),'audit_status':a['status'],'audit_errors':a['errors'],'run_summary_sha256':sha(V4/f'outputs/pilot_{rev}/run_summary.json'),'request_log_sha256':sha(V4/f'outputs/pilot_{rev}/request_log.jsonl'),'metrics_sha256':sha(V4/f'metrics/pilot_{rev}/metrics.json')})
smokes=[]
for p in sorted((V4/'logs').glob('smoke*.json')):
 x=load(p); smokes.append({'file':str(p),'request_id':x.get('request_id'),'candidate_id':x.get('candidate_id'),'http_status':x.get('http_status'),'target_ids':x.get('target_ids'),'image_count':x.get('image_count'),'input_sha256s':x.get('input_sha256s'),'error':x.get('error')})
out={'status':'NO_QUALIFIED_CANDIDATE','trials':r,'smokes':smokes,'physical_model_requests_total':sum(x['physical_requests'] for x in r)+len(smokes),'max_client_concurrency':2,'dev_expansion_executed':False,'reason':'R0 and the single evidence-driven R1 both failed alert recall/coverage gates; no third candidate authorized'}
(V4/'contracts/trial_registry.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
