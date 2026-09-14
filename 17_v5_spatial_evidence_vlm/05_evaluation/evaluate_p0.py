"""Post-inference detector diagnostics only; labels never flow back into inference."""
import json,pathlib,csv,math,statistics
R=pathlib.Path(__file__).resolve().parents[1]
def read(p):return [json.loads(x) for x in p.read_text().splitlines()]
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def rate(k,n):
 if not n:return {'numerator':k,'denominator':n,'ratio':None,'wilson95':None}
 z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return {'numerator':k,'denominator':n,'ratio':p,'wilson95':[max(0,c-h),min(1,c+h)]}
def iou(a,b):
 i=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i;return i/u if u else 0
if __name__=='__main__':
 refs=read(R/'reference/reference_instances.jsonl');old=read(R.parent/'16_v4_dynamic_vlm/inputs/pilot/adapted_inputs.jsonl');new=read(R/'01_footprint/footprint_outputs.jsonl');log=read(R/'01_footprint/detector_manifest.jsonl');raw=read(R/'01_footprint/segmentation_outputs.jsonl')
 boxes={(x['media_id'],t['target_id']):t['bbox'] for x in old for t in x['kept_targets']};matches=[];used=set()
 # Global greedy descending IoU, one-to-one, threshold 0.50. Post-hoc diagnostic, NOT tuned classifier.
 edges=sorted([(iou(boxes[(r['media_id'],r['target_id'])],n['bbox_xyxy']),i,j) for i,r in enumerate(refs) for j,n in enumerate(new) if r['media_id']==n['image_id']],reverse=True);matched={}
 for score,i,j in edges:
  if score>=.5 and i not in matched and j not in used:matched[i]=(j,score);used.add(j)
 for i,r in enumerate(refs):
  m=matched.get(i);matches.append({'image_id':r['media_id'],'reference_vehicle_id':r['target_id'],'reference_label':r['label'],'reference_bbox':boxes[(r['media_id'],r['target_id'])],'matched_vehicle_id':new[m[0]]['vehicle_id'] if m else None,'iou':m[1] if m else None,'reason_code':'matched_bbox_not_mask_quality' if m else 'detector_unmatched_reference_not_individually_reviewed','rule_only_label':'NOT_EXECUTED','vlm_label':'NOT_EXECUTED','final_label':'NOT_EXECUTED'})
 (R/'05_evaluation/detector_matches.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in matches))
 groups={l:rate(sum(x['matched_vehicle_id'] is not None for x in matches if x['reference_label']==l),sum(x['reference_label']==l for x in matches)) for l in sorted({x['reference_label'] for x in matches})}
 with (R/'05_evaluation/errors.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(matches[0]));w.writeheader();w.writerows(x for x in matches if x['matched_vehicle_id'] is None)
 lat=sorted(x['latency_seconds'] for x in log)
 metrics={'scope':'P0_POSTHOC_DIAGNOSTIC_NOT_CLASSIFICATION','fixed_snapshot_only':True,'zero_vlm_request_basis':'execution record: no VLM client or request initiated; not inferred from this evaluator','zero_ground_and_roi_basis':'current raw records all ground_contact null and pilot ROI unavailable; not a reusable downstream evaluator','images':len(log),'mask_valid_among_detections':rate(sum(x['mask_status']=='ok' for x in new),len(new)),'detector_reference_bbox_match':rate(len(matched),len(refs)),'mask_available_for_reference_bbox_matches':rate(sum(new[j]['mask_status']=='ok' for j,score in matched.values()),len(refs)),'validated_ground_contact_reference_coverage':rate(0,len(refs)),'matched_positive_coverage':rate(sum(x['matched_vehicle_id'] is not None for x in matches if x['reference_label'].startswith('positive')),sum(x['reference_label'].startswith('positive') for x in matches)),'by_reference_label_detector_match_NOT_RECALL':groups,'unmatched_reference_count':len(refs)-len(matched),'unmatched_new_targets_not_confirmed_false_detections':len(new)-len(used),'zero_detection_images':[x['image_id'] for x in log if x.get('dedup_count')==0],'road_evidence_coverage':rate(0,len(refs)),'bay_evidence_coverage':rate(0,len(refs)),'two_bay_evidence_coverage':rate(0,len(refs)),'classification_metrics':{'status':'NOT_EXECUTED_P0_STOP','road_recall':None,'two_bay_recall':None,'ordinary_fpr':None,'line_fpr':None,'nose_tail_fpr':None,'gate_fpr':None,'uncertain_rate':None,'decisive_coverage':None},'latency_seconds':{'median':statistics.median(lat),'p95_nearest_rank':lat[math.ceil(.95*len(lat))-1],'total':sum(lat),'scope':'per_image_predict_extract_overlay_save; excludes model/encoder initialization'},'physical_vlm_requests':0,'vlm_concurrency':0,'vlm_latency':None}
 write(R/'05_evaluation/p0_metrics.json',metrics)
 categories=['detector_miss','duplicate_detection','false_detection','mask_failure','footprint_failure','coordinate_space_error','roi_missing','road_overlap_error','two_bay_overlap_error','adjacency_error','gate_queue_error','minor_overrun_false_positive','nose_tail_false_positive','rule_conflict','vlm_veto_error','vlm_accept_error','vlm_semantic_uncertain','protocol_failure','reference_uncertain','reference_disputed']
 write(R/'05_evaluation/error_attribution_summary.json',{'categories':{x:({'count':None,'unmatched_reference_candidates':len(refs)-len(matched),'visually_confirmed_lower_bound':5,'basis':'five documented partial-review observations; remaining unmatched not individually confirmed'} if x=='detector_miss' else {'count':None,'algorithmic_suppression_count':sum(len(y['suppressed']) for y in raw),'basis':'not independently confirmed duplicate objects'} if x=='duplicate_detection' else {'count':len(refs),'basis':'validated_ground_contact_missing'} if x=='footprint_failure' else {'count':len(refs),'basis':'ROI_missing'} if x=='roi_missing' else {'count':sum(r['label']=='uncertain' for r in refs),'basis':'frozen_reference'} if x=='reference_uncertain' else {'count':None,'basis':'NOT_INDIVIDUALLY_ASSESSED_OR_DOWNSTREAM_NOT_EXECUTED'}) for x in categories}})
 print(json.dumps(metrics,indent=2))
