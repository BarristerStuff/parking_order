"""Post-inference integration. No models, pixels or changes to reference.
Recomputes geometric support/status totals; reviewed facts remain separately
attributed to A's visual-audit metrics, never synthesized from IoU alone.
"""
from pathlib import Path
import json,csv,hashlib,collections,statistics,math,time
from metrics_utils import rate
R=Path(__file__).resolve().parents[1]
def read(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_footprint_rows(rows,targets,metrics):
 source=R/'01_detector_audit/r1_targets.jsonl';expected_sha=sha(source)
 if metrics['source_sha256']!=expected_sha or Path(metrics['source']).resolve()!=source.resolve():raise ValueError('B source binding mismatch')
 lookup={(t['image_id'],t['vehicle_id']):t for t in targets};methods={'mask_bottom_contact_band':'mask_bottom_band','bbox_lower_conservative_proxy':'bbox_lower_proxy'}
 if len(lookup)!=len(targets) or len(rows)!=2*len(targets):raise ValueError('B denominator or target uniqueness error')
 if len({(x['image_id'],x['vehicle_id'],x['method']) for x in rows})!=len(rows):raise ValueError('duplicate B method record')
 for x in rows:
  key=(x['image_id'],x['vehicle_id']);method=x['method']
  if key not in lookup or method not in methods:raise ValueError('B target/method identity mismatch')
  if x['bbox_xyxy']!=lookup[key]['bbox_xyxy'] or x['raw_detection_id']!=lookup[key]['raw_detection_id']:raise ValueError('B geometry provenance mismatch')
  if x['input_sha256']!=expected_sha or Path(x['input_source']).resolve()!=source.resolve():raise ValueError('B row source mismatch')
  if x['status'] not in {'proxy','uncertain','failed'} or x['ground_contact_status']!=x['status'] or x['footprint_source']!=methods[method]:raise ValueError('B status/source alias mismatch')
  if x['ground_contact_polygon'] is not None or x['ground_validated'] or x['footprintIoU'] is not None or x['scope']!='DIAGNOSTIC_ONLY':raise ValueError('B ground promotion forbidden')
  q=x['quality'];e=x['evidence'];st=e['source_target']
  if q['visual']!=x['visual_review'] or q['algorithmic']['status']!=x['status'] or q['algorithmic']['reasons']!=x['reasons'] or q['ground_validated']:raise ValueError('B quality alias mismatch')
  if e['algorithmic_reasons']!=x['reasons'] or e['visual_review']!=x['visual_review']:raise ValueError('B evidence alias mismatch')
  if (st['image_id'],st['vehicle_id'])!=key or st['sha256']!=expected_sha or Path(st['path']).resolve()!=source.resolve():raise ValueError('B evidence source mismatch')
 return True

def evaluate():
 runs={}
 for name in ['r0','r1']:
  p=R/'01_detector_audit'/f'{name}_matching.jsonl';images=read(p);raw=read(R/'01_detector_audit'/f'{name}_raw_outputs.jsonl');targets=read(R/'01_detector_audit'/f'{name}_targets.jsonl');logs=read(R/'01_detector_audit'/f'{name}_log.jsonl')
  refs=[x for im in images for x in im['references']];matched=[im['references'][m['reference_index']] for im in images for m in im['matches']]
  if len(images)!=60 or len(refs)!=240:raise ValueError('incomplete image/reference denominator')
  groups={key:rate(sum(x.get('label')==label for x in matched),sum(x.get('label')==label for x in refs)) for key,label in [('road','positive_road'),('two_bay','positive_two_bays')]}
  groups['overall']=rate(len(matched),len(refs))
  cfg=json.loads((R/'01_detector_audit'/f'{name}_config.json').read_text())
  runs[name]={'config':cfg,'geometric_association_only':groups,'raw_detection_count':sum(len(x['detections']) for x in raw),'dedup_target_count':len(targets),'unmatched_reference_candidates':sum(len(x['unmatched_reference_indices']) for x in images),'unmatched_detection_candidates':sum(len(x['unmatched_detection_indices']) for x in images),'max_raw_targets_per_image':max(len(x['detections']) for x in raw),'zero_detection_images':sum(len(x['detections'])==0 for x in raw),'local_detector_calls_from_raw_image_records':len(raw),'inputs_sha256':sha(p),'review_metrics':json.loads((R/'01_detector_audit'/f'{name}_metrics.json').read_text()),'log_records':len(logs)}
 d0=runs['r0']['config'];d1=runs['r1']['config'];changed=[k for k in set(d0)|set(d1) if d0.get(k)!=d1.get(k)]
 if changed!=['classes']:raise ValueError('R1 factor contract violated: '+str(changed))
 fps=read(R/'02_footprint_audit/footprint_outputs.jsonl');fm=json.loads((R/'02_footprint_audit/footprint_metrics.json').read_text());source=R/'01_detector_audit/r1_targets.jsonl'
 if fm['source_sha256']!=sha(source):raise ValueError('footprint source mismatch')
 targets=read(source);validate_footprint_rows(fps,targets,fm);keys={(x['image_id'],x['vehicle_id']) for x in targets};methods={x['method'] for x in fps}
 if len(methods)!=2 or len(fps)!=2*len(keys) or len({(x['image_id'],x['vehicle_id'],x['method']) for x in fps})!=len(fps):raise ValueError('method denominator invalid')
 if {(x['image_id'],x['vehicle_id']) for x in fps}!=keys:raise ValueError('footprint target mismatch')
 for x in fps:
  if x['ground_contact_polygon'] is not None or x.get('ground_validated') or x['status']=='validated':raise ValueError('proxy unexpectedly promoted to physical ground')
 counts={m:dict(collections.Counter(x['status'] for x in fps if x['method']==m)) for m in sorted(methods)}
 rule=json.loads((R/'04_rule_engine/rule_metrics.json').read_text())
 g=runs['r1']['geometric_association_only'];contract=json.loads((R/'contracts/run_contract.json').read_text());cg=contract['coverage_gate'];thresholds={'overall':cg['overall'],'road':cg['positive_road'],'two_bay':cg['positive_two_bays']};upper_fails=[k for k,x in g.items() if x['ratio'] is None or x['ratio']<thresholds[k]]
 # A failing geometric upper bound proves confirmed matched coverage cannot pass.
 # No READY promotion implementation is included in this diagnostic integrator.
 if not upper_fails:raise RuntimeError('No geometric upper-bound failure: requires reviewed gate implementation, cannot auto-promote or invent gate failure')
 final='V5_DETECTOR_COVERAGE_BLOCKED'
 audit=json.loads((R/'01_detector_audit/detector_metrics.json').read_text())
 result={'evaluated_at_unix':time.time(),'scope':'AIGC_DIAGNOSTIC_REUSED_V4_PILOT','reference_basis':'AI_VISUAL_REVIEWED_PROVISIONAL','human_gold':False,'runs':runs,'reviewed_detector_audit':audit,'r1_changed_main_factors':changed,'detector_gate':{'passed':False,'geometric_upper_bound_failed_subgroups':upper_fails,'reason':'Confirmed coverage cannot exceed the frozen geometric associations. See separate visual-audit confirmed coverage; no unmatched instance is declared a miss here.'},'footprint':{'source_run':'r1_latest_diagnostic_not_winner','unique_target_denominator':len(keys),'method_row_denominator':len(fps),'methods':counts,'validated_ground_count':0,'metrics':fm},'trusted_geometry_available':False,'spatial_evidence_formal_evaluation':'BLOCKED_NO_TRUSTED_GEOMETRY','rules_only_executed_on_pilot':False,'synthetic_rule_tests':rule,'classification_metrics':{'road_recall':None,'two_bay_recall':None,'ordinary_in_bay_fpr':None,'line_minor_fpr':None,'nose_tail_fpr':None,'gate_queue_fpr':None,'uncertain_rate':None},'vlm_executed':False,'physical_model_requests':0,'physical_model_requests_scope':'REMOTE_VLM_HTTP; execution provenance not a network packet audit','local_detector_image_calls':sum(x['local_detector_calls_from_raw_image_records'] for x in runs.values()),'current_status':final,'winner':None,'production_integration_ready':False}
 # Preload all required reviewed CSV before publishing any integrated output.
 error_rows=[]
 for name in ['unmatched_reference.csv','unmatched_detection.csv','duplicate_detection.csv']:
  ep=R/'01_detector_audit'/name
  with ep.open(newline='') as handle:
   reader=csv.DictReader(handle)
   if not reader.fieldnames:raise ValueError('Missing audited CSV header: '+name)
   for i,row in enumerate(reader,1):error_rows.append({'source':str(ep),'row_index':i,'audit_record':json.dumps(row,ensure_ascii=False)})
 (R/'05_evaluation/metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 # Keep error classifications from reviewed audit; do not relabel unmatched rows.
 with (R/'05_evaluation/errors.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=['source','row_index','audit_record']);writer.writeheader()
  writer.writerows(error_rows)
 (R/'05_evaluation/report.md').write_text('# Detector / footprint integration\n\nStatus: '+final+'\n\nR1 geometric associations: '+str(g)+'. These are NOT classification Recall or automatically visually confirmed detections.\n\nTwo methods evaluated on '+str(len(keys))+' detected targets; '+str(len(fps))+' method rows, all ground_contact_polygon null. Footprint visual quality is sampled and separately logged. Formal pilot rules and VLM NOT_EXECUTED. 11 synthetic expectations are code tests, not AIGC accuracy. See metrics.json and the parent EXECUTION_REPORT.md for reviewed detector counts and denominators.\n')
 return result
if __name__=='__main__':
 result=evaluate();print(json.dumps({'status':result['current_status'],'local_detector_calls':result['local_detector_image_calls'],'method_rows':result['footprint']['method_row_denominator']},indent=2))
