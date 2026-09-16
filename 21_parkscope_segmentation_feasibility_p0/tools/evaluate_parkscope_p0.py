#!/usr/bin/env python3
import csv,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
manifest=list(csv.DictReader(open(REPO/'20_v2_3_decomposed_relation/04_pilot/pilot_manifest.csv',newline='')))
reviews=list(csv.DictReader(open(ROOT/'04_visual_review/parkscope_feasibility_review.csv',newline='')))
preds=[json.loads(x) for x in open(ROOT/'03_inference/parkscope_predictions.jsonl') if x.strip()]
errors=list(csv.DictReader(open(ROOT/'03_inference/technical_errors.csv',newline='')))
usable=lambda v:v in {'GOOD','PARTIAL'}
vc=Counter(r['vehicle_mask_quality'] for r in reviews); gc=Counter(r['parking_geometry_quality'] for r in reviews)
normal_prefixes=('n01-','n02-','n03-','n04-','n05-','n06-')
normal=[r for r in reviews if r['group_key'].startswith(normal_prefixes)]
p01=[r for r in reviews if r['group_key'].startswith('p01-')]
p03=[r for r in reviews if r['group_key'].startswith('p03-')]
def image_grade_rows(rs, field):
    byimg=defaultdict(list)
    for r in rs: byimg[r['media_id']].append(r[field])
    return {mid: ('GOOD' if 'GOOD' in vals else ('PARTIAL' if 'PARTIAL' in vals else 'FAIL')) for mid,vals in byimg.items()}
normal_img=image_grade_rows(normal,'parking_geometry_quality')
p01_img=image_grade_rows(p01,'p01_outside_evidence_quality')
p03_img=image_grade_rows(p03,'p03_separator_evidence_quality')
cat=sum(r['catastrophic_wrong_mask'].lower()=='true' for r in reviews)
cls=Counter(); imgs=defaultdict(set)
for p in preds:
 for x in p['instances']:
  cls[x['class_id']]+=1;imgs[x['class_id']].add(p['media_id'])
def rate(n,d):return n/d if d else None
m={
'TOTAL_IMAGES':len(manifest),'INFERENCE_SUCCESS_IMAGES':len(preds),'SELECTED_VEHICLES':len(reviews),
'VEHICLE_MASK_GOOD':vc['GOOD'],'VEHICLE_MASK_PARTIAL':vc['PARTIAL'],'VEHICLE_MASK_FAIL':vc['FAIL'],'VEHICLE_MASK_USABLE_RATE':rate(vc['GOOD']+vc['PARTIAL'],len(reviews)),
'PARKING_GEOMETRY_GOOD':gc['GOOD'],'PARKING_GEOMETRY_PARTIAL':gc['PARTIAL'],'PARKING_GEOMETRY_FAIL':gc['FAIL'],'PARKING_GEOMETRY_USABLE_RATE':rate(gc['GOOD']+gc['PARTIAL'],len(reviews)),
'NORMAL_MARKED_BAY_TOTAL':len(normal_img),'NORMAL_MARKED_BAY_GEOMETRY_USABLE':sum(usable(v) for v in normal_img.values()),'NORMAL_MARKED_BAY_GEOMETRY_USABLE_RATE':rate(sum(usable(v) for v in normal_img.values()),len(normal_img)),
'P01_TOTAL':len(p01_img),'P01_OUTSIDE_EVIDENCE_USABLE':sum(usable(v) for v in p01_img.values()),'P01_OUTSIDE_EVIDENCE_USABLE_RATE':rate(sum(usable(v) for v in p01_img.values()),len(p01_img)),
'P03_TOTAL':len(p03_img),'P03_SEPARATOR_USABLE':sum(usable(v) for v in p03_img.values()),'P03_SEPARATOR_USABLE_RATE':rate(sum(usable(v) for v in p03_img.values()),len(p03_img)),
'CATASTROPHIC_WRONG_MASK_COUNT':cat,'CATASTROPHIC_WRONG_MASK_RATE':rate(cat,len(reviews)),
'CLASS0_INSTANCE_COUNT':cls[0],'CLASS1_INSTANCE_COUNT':cls[1],'CLASS2_INSTANCE_COUNT':cls[2],'CLASS3_INSTANCE_COUNT':cls[3],
'CLASS0_IMAGE_COUNT':len(imgs[0]),'CLASS1_IMAGE_COUNT':len(imgs[1]),'CLASS2_IMAGE_COUNT':len(imgs[2]),'CLASS3_IMAGE_COUNT':len(imgs[3]),'TECHNICAL_ERROR_COUNT':len(errors)}
gates={
'inference_70_of_70':m['INFERENCE_SUCCESS_IMAGES']==70,
'vehicle_mask_usable_rate_gte_0_95':m['VEHICLE_MASK_USABLE_RATE']>=.95,
'normal_marked_bay_geometry_usable_rate_gte_0_80':m['NORMAL_MARKED_BAY_GEOMETRY_USABLE_RATE']>=.80,
'p01_outside_evidence_usable_rate_gte_0_80':m['P01_OUTSIDE_EVIDENCE_USABLE_RATE']>=.80,
'p03_separator_usable_rate_gte_0_70':m['P03_SEPARATOR_USABLE_RATE']>=.70,
'catastrophic_wrong_mask_rate_lte_0_10':m['CATASTROPHIC_WRONG_MASK_RATE']<=.10}
m['gate_checks']=gates;m['PARKSCOPE_P0_GATE']='GO' if all(gates.values()) else 'NO_GO';m['FINAL_STATUS']='PARKSCOPE_SEGMENTATION_P0_GO' if m['PARKSCOPE_P0_GATE']=='GO' else 'PARKSCOPE_SEGMENTATION_P0_NO_GO';m['OFF_THE_SHELF_PARKSCOPE_GEOMETRY_NOT_SUFFICIENT']=m['P03_SEPARATOR_USABLE_RATE']<.70;m['READY_FOR_P1_STRUCTURED_GEOMETRY']=m['PARKSCOPE_P0_GATE']=='GO'
(ROOT/'05_metrics').mkdir(exist_ok=True);(ROOT/'05_metrics/metrics.json').write_text(json.dumps(m,indent=2)+'\n')
# subgroup vehicle/geometry counts
by=defaultdict(list)
for r in reviews:by[r['group_key']].append(r)
with open(ROOT/'05_metrics/subgroup_metrics.csv','w',newline='') as f:
 fields=['group_key','selected_vehicles','vehicle_mask_usable','vehicle_mask_usable_rate','parking_geometry_usable','parking_geometry_usable_rate','catastrophic_wrong_mask_count']
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for g,rs in sorted(by.items()):
  w.writerow({'group_key':g,'selected_vehicles':len(rs),'vehicle_mask_usable':sum(usable(x['vehicle_mask_quality']) for x in rs),'vehicle_mask_usable_rate':rate(sum(usable(x['vehicle_mask_quality']) for x in rs),len(rs)),'parking_geometry_usable':sum(usable(x['parking_geometry_quality']) for x in rs),'parking_geometry_usable_rate':rate(sum(usable(x['parking_geometry_quality']) for x in rs),len(rs)),'catastrophic_wrong_mask_count':sum(x['catastrophic_wrong_mask']=='true' for x in rs)})
print(json.dumps(m,indent=2))
