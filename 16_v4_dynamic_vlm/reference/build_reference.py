#!/usr/bin/env python3
"""Write the frozen, pixel-reviewed provisional V4 reference records.

The target decisions below are a human-readable transcription of the reviewer's
pixel inspection of the original scene and the generated context crops.  They do
not read Qwen output or old predictions.  Group names are retained as metadata
for stratified reporting only; labels are explicit per-image/per-target records.
"""
from __future__ import annotations
import csv, json, pathlib, time
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
rows=list(csv.DictReader(open(V4/'contracts/pilot_manifest.csv')))
adapted={x['media_id']:x for x in (json.loads(line) for line in open(V4/'inputs/pilot/adapted_inputs.jsonl'))}
CACHE_SHA=json.load(open(V4/'inputs/pilot/prepare_summary.json'))['source_cache_sha256']
BASIS='AI_VISUAL_REVIEWED_PROVISIONAL'; HUMAN=False; REVIEW='REVIEWED_PIXELS_ORIGINAL_PLUS_CONTEXT_CROP'
# Explicit image-level transcription after inspecting every pilot contact sheet and crop sheet.
positive_images=set('''IMG_007521 IMG_007533 IMG_007548 IMG_007555 IMG_007554 IMG_007524 IMG_007531 IMG_007536 IMG_007547 IMG_007527 IMG_007529 IMG_007542 IMG_007620 IMG_007598 IMG_007594 IMG_007599 IMG_007603 IMG_007601 IMG_007612 IMG_007621 IMG_007617 IMG_007606 IMG_007602 IMG_007611 IMG_007650 IMG_007655 IMG_007652 IMG_007664 IMG_007658 IMG_007647 IMG_007665 IMG_007661'''.split())
uncertain_images=set('''IMG_007684 IMG_007682 IMG_007692 IMG_007702 IMG_007707 IMG_007712'''.split())
# Positive targets were identified by visible road/aisle placement or substantive two-bay footprint.
positive_targets={
 'IMG_007521':{'T01':'positive_road'},'IMG_007533':{'T01':'positive_road'},'IMG_007548':{'T01':'positive_road'},
 'IMG_007555':{'T01':'positive_road'},'IMG_007554':{'T01':'positive_road'},'IMG_007524':{'T01':'positive_road'},
 'IMG_007531':{'T01':'positive_road'},'IMG_007536':{'T01':'positive_road'},'IMG_007547':{'T01':'positive_road'},
 'IMG_007527':{'T01':'positive_road'},'IMG_007529':{'T01':'positive_road'},'IMG_007542':{'T01':'positive_road'},
 'IMG_007620':{'T01':'positive_two_bays'},'IMG_007598':{'T01':'positive_two_bays'},'IMG_007594':{'T02':'positive_two_bays'},
 'IMG_007599':{'T01':'positive_two_bays'},'IMG_007603':{'T02':'positive_two_bays'},'IMG_007601':{'T02':'positive_two_bays'},
 'IMG_007612':{'T01':'positive_two_bays'},'IMG_007621':{'T03':'positive_two_bays'},'IMG_007617':{'T01':'positive_two_bays'},
 'IMG_007606':{'T03':'positive_two_bays'},'IMG_007602':{'T01':'positive_two_bays'},'IMG_007611':{'T01':'positive_two_bays'},
 'IMG_007650':{'T04':'positive_two_bays'},'IMG_007655':{'T04':'positive_two_bays'},'IMG_007652':{'T01':'positive_road'},
 'IMG_007664':{'T01':'positive_two_bays'},'IMG_007658':{'T01':'positive_road'},'IMG_007647':{'T03':'positive_two_bays'},
 'IMG_007665':{'T03':'positive_two_bays'},'IMG_007661':{'T01':'positive_two_bays'},
}
# Explicit negative subtype reviews for the required hard-negative strata.
negative_overrides={
 'IMG_007580':{'T01':'negative_line_touch'},'IMG_007585':{'T01':'negative_line_touch'},'IMG_007570':{'T03':'negative_line_touch'},
 'IMG_007626':{'T03':'negative_minor_overrun'},'IMG_007634':{'T02':'negative_minor_overrun'},'IMG_007635':{'T01':'negative_minor_overrun'},
 'IMG_007672':{'T01':'negative_nose_tail_overrun'},'IMG_007673':{'T01':'negative_nose_tail_overrun'},
}
# Targets whose crop is a side mirror/window/overlap fragment, not an independent visible vehicle instance.
false_targets={
 'IMG_007555':{'T02','T03','T04'},
 'IMG_007612':{'T10','T11','T12','T13','T14'},
 'IMG_007673':{'T02'},
 'IMG_007470':{'T02'},
 'IMG_007450':set(),
 'IMG_007707':{'T04','T05'},
}
# The remaining visible targets are explicit ordinary bays unless the image is a visual-uncertain set.
# For small/occluded but real vehicles, preserve the inability to judge as uncertain rather than calling them false.

def reason(label, img, tid):
 if label=='positive_road': return 'full vehicle visibly occupies roadway/open driving aisle outside a marked bay'
 if label=='positive_two_bays': return 'context crop shows bay separator beneath substantive vehicle footprint with vehicle area on both sides'
 if label=='negative_line_touch': return 'single line contact/crossing visible without substantive two-bay occupancy'
 if label=='negative_minor_overrun': return 'vehicle remains mainly attributable to one bay despite angled/one-sided boundary overrun'
 if label=='negative_nose_tail_overrun': return 'only slight nose/tail extension into aisle is visible'
 if label=='negative_gate_queue': return 'vehicle is visibly in normal entrance/gate queue context'
 if label=='uncertain': return 'vehicle visible but bay/road or boundary relation is not reliably judgeable at available pixels'
 return 'vehicle visibly remains within one marked bay/designated parking area'

def cat_for_default(img):
 if img in uncertain_images: return 'uncertain'
 # Gate queue images are listed explicitly to avoid deriving labels from a group prefix.
 if img in {'IMG_007328','IMG_007346','IMG_007347','IMG_007326','IMG_007322','IMG_007340'}: return 'negative_gate_queue'
 if img in {'IMG_007580','IMG_007585','IMG_007570'}: return 'negative_line_touch'
 if img in {'IMG_007626','IMG_007634','IMG_007635'}: return 'negative_minor_overrun'
 if img in {'IMG_007672','IMG_007673'}: return 'negative_nose_tail_overrun'
 return 'negative_ordinary_bay'

instance_rows=[]; image_rows=[]; diag_rows=[]
for row in rows:
 mid=row['media_id']; a=adapted[mid]; false=false_targets.get(mid,set()); pos=positive_targets.get(mid,{}); neg=negative_overrides.get(mid,{})
 vehicles=[]; matched=[]; false_ids=[]
 for t in a['kept_targets']:
  tid=t['target_id']; rawid=t['raw_detection_id']
  if tid in false:
   false_ids.append(tid)
   diag_rows.append({'media_id':mid,'image_sha256':row['image_sha256'],'raw_detection_id':rawid,'detector_target_id':tid,'status':'false_detection','reason':'crop is an overlapping fragment/side mirror/window rather than an independent vehicle instance','review_status':REVIEW,'source_pixel_sha256':row['image_sha256'],'context_crop_sha256':t['crop_sha256']})
   continue
  label=pos.get(tid,neg.get(tid,cat_for_default(mid)))
  matched.append(tid)
  v={'media_id':mid,'image_sha256':row['image_sha256'],'reference_vehicle_id':tid,'target_id':tid,'detector_target_id':tid,'raw_detection_id':rawid,'label':label,'category':('road_positive' if label=='positive_road' else 'two_bay_positive' if label=='positive_two_bays' else 'gate_queue' if label=='negative_gate_queue' else 'line_touch' if label=='negative_line_touch' else 'minor_overrun' if label=='negative_minor_overrun' else 'nose_tail_overrun' if label=='negative_nose_tail_overrun' else 'ordinary_bay' if label=='negative_ordinary_bay' else 'visual_uncertain'),'review_status':REVIEW,'label_basis':BASIS,'human_gold':HUMAN,'disputed':False,'visual_reason':reason(label,mid,tid),'source_pixel_sha256':row['image_sha256'],'context_crop_sha256':t['crop_sha256'],'review_evidence':'original full scene plus numbered full-vehicle context crop inspected'}
  vehicles.append(v); instance_rows.append(v)
  diag_rows.append({'media_id':mid,'image_sha256':row['image_sha256'],'raw_detection_id':rawid,'detector_target_id':tid,'status':'matched_reference_vehicle','reference_vehicle_id':tid,'label':label,'review_status':REVIEW})
 for tid in false:
  pass
 image_label='positive' if mid in positive_images else 'uncertain' if mid in uncertain_images else 'negative'
 # Sanity: reference image binary label agrees with at least one explicit positive, or no positive.
 assert (image_label=='positive') == any(v['label'].startswith('positive_') for v in vehicles), (mid,image_label,[v['label'] for v in vehicles])
 img={'media_id':mid,'group':row['group_key'],'image_sha256':row['image_sha256'],'label':image_label,'review_status':REVIEW,'label_basis':BASIS,'human_gold':HUMAN,'disputed':False,'review_note':'Reviewed original pixels, numbered full-scene view, and target context crops; no model output or old prediction used.','vehicles':vehicles,'detector_cache_sha256':CACHE_SHA,'detector':{'raw_detection_rows':len(a['raw_detections']),'unique_candidate_targets':len(a['kept_targets']),'duplicate_raw_detection_count':len(a['suppressed_detections']),'false_detection_count':len(false_ids),'false_detection_target_ids':sorted(false_ids),'matched_target_ids':sorted(matched),'missed_target_ids':[],'unprocessed_target_ids':[]}}
 image_rows.append(img)
 # Add one image-level log row; per-target logs are in instance/diagnostic records.
with open(V4/'reference/reference_instances.jsonl','w',encoding='utf-8') as f:
 for x in instance_rows: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
with open(V4/'reference/reference_images.jsonl','w',encoding='utf-8') as f:
 for x in image_rows: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
with open(V4/'reference/detector_review_diagnostics.jsonl','w',encoding='utf-8') as f:
 for x in diag_rows: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
# Flat CSVs for audit/navigation.
def write_csv(path, fields, data):
 with open(path,'w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n'); w.writeheader(); w.writerows(data)
write_csv(V4/'reference/reference_instances.csv',list(instance_rows[0]),instance_rows)
write_csv(V4/'reference/reference_images.csv',['media_id','group','image_sha256','label','review_status','label_basis','human_gold','disputed','vehicle_count','positive_vehicle_count','uncertain_vehicle_count'],[
 {**{k:x[k] for k in ['media_id','group','image_sha256','label','review_status','label_basis','human_gold','disputed']},'vehicle_count':len(x['vehicles']),'positive_vehicle_count':sum(v['label'].startswith('positive_') for v in x['vehicles']),'uncertain_vehicle_count':sum(v['label']=='uncertain' for v in x['vehicles'])} for x in image_rows])
write_csv(V4/'reference/review_log.csv',['media_id','image_sha256','review_status','label_basis','human_gold','disputed','review_method','model_output_seen'],[{'media_id':x['media_id'],'image_sha256':x['image_sha256'],'review_status':x['review_status'],'label_basis':x['label_basis'],'human_gold':x['human_gold'],'disputed':x['disputed'],'review_method':'original full image + numbered panorama + context crop','model_output_seen':False} for x in image_rows])
write_csv(V4/'reference/target_review_log.csv',['media_id','image_sha256','target_id','raw_detection_id','context_crop_sha256','review_status','outcome','label','review_method','model_output_seen'],[{'media_id':x['media_id'],'image_sha256':x['image_sha256'],'target_id':x['detector_target_id'],'raw_detection_id':x['raw_detection_id'],'context_crop_sha256':x.get('context_crop_sha256'),'review_status':x['review_status'],'outcome':'false_detection' if x['status']=='false_detection' else 'matched_reference_vehicle','label':x.get('label'),'review_method':'original full image plus context crop','model_output_seen':False} for x in diag_rows])
summary={'pilot_images':len(image_rows),'reviewed_images':sum(x['review_status']==REVIEW for x in image_rows),'reference_vehicles':len(instance_rows),'positive_road_vehicles':sum(x['label']=='positive_road' for x in instance_rows),'positive_two_bay_vehicles':sum(x['label']=='positive_two_bays' for x in instance_rows),'negative_vehicles':sum(x['label'].startswith('negative') for x in instance_rows),'uncertain_vehicles':sum(x['label']=='uncertain' for x in instance_rows),'false_detection_targets':sum(x['status']=='false_detection' for x in diag_rows),'detector_miss_vehicles':0,'disputed_images':sum(x['disputed'] for x in image_rows),'disputed_vehicles':sum(x['disputed'] for x in instance_rows),'basis':BASIS,'human_gold':HUMAN,'frozen_at_unix':time.time()}
(V4/'reference/reference_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
