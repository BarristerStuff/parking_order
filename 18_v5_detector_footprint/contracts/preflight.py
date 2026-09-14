"""Only metadata/allowlisted image reads; all new writes in this run."""
from pathlib import Path
import csv,json,hashlib,subprocess,sys,importlib.util,glob,time,shutil
R=Path(__file__).resolve().parents[1];P=R.parent;V=P/'17_v5_spatial_evidence_vlm';V4=P/'16_v4_dynamic_vlm'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def out(name,x):(R/'contracts'/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
if (R/'contracts/preflight.json').exists():raise SystemExit('Existing preflight: no overwrite')
initial={d:subprocess.run(['git','-C',d,'status','--porcelain=v1'],capture_output=True,text=True).stdout for d in [str(P),'/home/yanbo/net_vlm_yanboversion/vlm']};out('initial_git_status.json',initial)
expected=json.loads((V/'06_audit/hash_manifest.json').read_text())['files'];changed=[k for k,h in expected.items() if not (V/k).is_file() or sha(V/k)!=h]
f4=json.loads((V4/'reference/REFERENCE_FREEZE.json').read_text());changed4=[k for k,h in f4['files'].items() if sha(V4/'reference'/k)!=h]
if changed or changed4:out('OLD_HASH_MISMATCH.json',{'v5':changed,'v4':changed4});raise SystemExit('OLD_FILE_CHANGED_STOP')
# Reuse the exact previous bounded source snapshot; do not scan label/media directories.
paths=list(json.loads((V/'contracts/protected_hashes_before.json').read_text()))+[str(V/k) for k in expected]+[str(V/'06_audit/hash_manifest.json'),str(V4/'reference/REFERENCE_FREEZE.json')]
missing=[p for p in sorted(set(paths)) if not Path(p).is_file()]
if missing:raise RuntimeError('EXPECTED_PROTECTED_FILE_MISSING: '+repr(missing))
protected={p:sha(Path(p)) for p in sorted(set(paths))};out('protected_before.json',protected)
rows=list(csv.DictReader((V/'contracts/input_allowlist.csv').read_text().splitlines()));splits=list(csv.DictReader((P/'12_v2_not_in_bay/01_gt_and_split/v2_split.csv').read_text().splitlines()));dev={x['media_id'] for x in splits if x['split']=='DEV'}
if len(rows)!=60 or len({x['image_id'] for x in rows})!=60 or any(x['image_id'] not in dev for x in rows):raise RuntimeError('INVALID_ALLOWLIST')
for x in rows:
 if sha(Path(x['absolute_path']))!=x['image_sha256']:raise RuntimeError('SOURCE_CHANGED')
shutil.copyfile(V/'contracts/input_allowlist.csv',R/'contracts/allowlist.csv');shutil.copyfile(V/'contracts/pilot_manifest.csv',R/'contracts/pilot_manifest.csv');shutil.copyfile(V/'contracts/forbidden_split_metadata.csv',R/'contracts/forbidden_split_metadata.csv')
counts={s:sum(x['split']==s for x in splits) for s in ['DEV','VAL','HOLDOUT']}
fp=[json.loads(x) for x in (V/'01_footprint/footprint_outputs.jsonl').read_text().splitlines()]
out('preflight.json',{'date':'2026-09-10','created_at_unix':time.time(),'old_v5_manifest_verified_files':len(expected),'old_v4_reference_verified_files':len(f4['files']),'protected_file_count':len(protected),'split_counts':counts,'allowlist_images':len(rows),'prior_segmentation_image_count':sum(1 for _ in (V/'01_footprint/segmentation_outputs.jsonl').open()),'prior_footprint_rows':len(fp),'prior_validated_ground_contact_count':sum(x.get('ground_contact_status')=='validated' for x in fp),'system_python':sys.executable,'system_modules':{m:bool(importlib.util.find_spec(m)) for m in ['torch','ultralytics','cv2','PIL','numpy']},'nvidia_device_nodes':glob.glob('/dev/nvidia*'),'nvidia_smi':shutil.which('nvidia-smi'),'robot_direct_status':'NO_CONFIRMED_ALLOWED_BUNDLE; current allowed files contain AIGC images only; production runtime data not searched','ground_geometry_status':'NO_VALIDATED_POLYGON_IN_ALLOWED_V5_OUTPUT; no new ground geometry supplied','detector_cache_sha256':sha(P/'12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl')})
out('run_contract.json',{'date':'2026-09-10','revision':'V5_DETECTOR_FOOTPRINT','business_definition':'v3.0_user_confirmed','source':'AIGC','reference':'AI_VISUAL_REVIEWED_PROVISIONAL','human_gold':False,'pilot_count':60,'matching':{'method':'descending_iou_greedy_one_to_one','minimum_iou':0.5,'tie_break':'reference_index_then_detection_index','labels_used':False,'matched_status':'geometric_match_until_visual_review'},'coverage_gate':{'overall':0.9,'positive_road':0.9,'positive_two_bays':0.9,'basis':'visually_confirmed_matches_over_frozen_reference_support'},'max_detector_candidates':2,'r1_requires_r0_error_evidence':True,'r1_allowed_changed_main_factors':1,'max_footprint_methods':2,'footprint_scope_if_detector_blocked':'DIAGNOSTIC_ONLY','ground_contact_proxy_can_alert':False,'vlm_prohibited':True,'physical_remote_model_requests':0,'local_detector_calls_counted_separately':True,'writes_only':str(R)})
out('preregistration_freeze.json',{'frozen_at_unix':time.time(),'files':{p.name:sha(p) for p in (R/'contracts').iterdir() if p.name in ['run_contract.json','allowlist.csv','pilot_manifest.csv','forbidden_split_metadata.csv']}})
print((R/'contracts/preflight.json').read_text())
