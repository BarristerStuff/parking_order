import pathlib,json,csv,hashlib,time,shutil
R=pathlib.Path(__file__).resolve().parents[1]; P=R.parent; V=P/'16_v4_dynamic_vlm'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
if (R/'contracts/protected_hashes_before.json').exists() or (R/'reference/reference_freeze.json').exists():
 raise SystemExit('REFUSE_TO_OVERWRITE_EXISTING_BASELINE_OR_FREEZE')
# Snapshot protected source files only; never walk formal image/label data.
protected={}
for root in [P/x for x in ['12_v2_not_in_bay','14_v3_parked_on_road','15_v3_roi_r1','16_v4_dynamic_vlm']]+[pathlib.Path('/home/yanbo/net_vlm_yanboversion/vlm')]:
 for p in root.rglob('*'):
  if p.is_file() and not p.is_symlink() and not any(x in p.parts for x in ['.git','__pycache__']):
   if root.name=='12_v2_not_in_bay' and p.name not in ['v2_split.csv','v2_dev_vehicle_detections.jsonl']:continue
   if p.suffix.lower() in ['.png','.jpg','.jpeg','.mp4']:continue
   protected[str(p)]=sha(p)
write(R/'contracts/protected_hashes_before.json',protected)
f=json.loads((V/'reference/REFERENCE_FREEZE.json').read_text());assert all(sha(V/'reference'/k)==v for k,v in f['files'].items())
rows=list(csv.DictReader((V/'contracts/pilot_manifest.csv').open())); splits=list(csv.DictReader((P/'12_v2_not_in_bay/01_gt_and_split/v2_split.csv').open()));dev={x['media_id'] for x in splits if x['split']=='DEV'}
assert len(rows)==60 and all(x['media_id'] in dev and x['split']=='DEV' for x in rows)
for name in ['pilot_manifest.csv'] :shutil.copyfile(V/'contracts'/name,R/'contracts'/name)
with (R/'contracts/input_allowlist.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=['image_id','absolute_path','image_sha256']);w.writeheader();w.writerows(dict(image_id=x['media_id'],absolute_path=x['absolute_path'],image_sha256=x['image_sha256']) for x in rows)
with (R/'contracts/forbidden_split_metadata.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=['media_id','split']);w.writeheader();w.writerows({k:x[k] for k in ['media_id','split']} for x in splits if x['split']!='DEV')
for name in ['reference_instances.jsonl','reference_images.jsonl','review_log.csv']:shutil.copyfile(V/'reference'/name,R/'reference'/name)
write(R/'reference/reference_freeze.json',{'frozen_at_unix':time.time(),'basis':'AI_VISUAL_REVIEWED_PROVISIONAL','human_gold':False,'reused_v4':True,'files':{p.name:sha(p) for p in (R/'reference').iterdir() if p.is_file() and p.name!='reference_freeze.json'}})
write(R/'contracts/run_contract.json',{'date':'2026-09-10','revision':'V5_SPATIAL_EVIDENCE_VLM','source':'AIGC','pilot_images':60,'dedup_iou':0.8,'classes':['car','truck','bus'],'conf':0.25,'imgsz':640,'max_det':50,'footprint_min_coverage':0.6,'mask_is_ground_footprint':False,'mask_lower_fraction':0.2,'mask_lower_is_ground_truth':False,'new_images':'NOT_EXECUTED: first assess existing pilot P0; no generation needed if footprint gate blocks','positive_requires_validated_ground_contact':True,'vlm_max_requests':300,'vlm_max_concurrency':2,'inference_reference_access':False})
print('frozen',len(rows),'protected',len(protected))
