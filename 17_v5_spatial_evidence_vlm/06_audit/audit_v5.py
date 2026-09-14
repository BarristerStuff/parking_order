"""Read-only verification of raw outputs; writes only audit_result.json."""
import pathlib,json,csv,hashlib,subprocess,math
R=pathlib.Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def csvrows(p):return list(csv.DictReader(p.read_text().splitlines()))
checks={};details={}
allow=csvrows(R/'contracts/input_allowlist.csv');pilot=csvrows(R/'contracts/pilot_manifest.csv');forbidden=csvrows(R/'contracts/forbidden_split_metadata.csv');ids={x['image_id'] for x in allow}
checks['allowlist_unique_60_dev']=len(allow)==len(ids)==60 and all(x['split']=='DEV' for x in pilot) and not ids & {x['media_id'] for x in forbidden}
checks['allowlist_source_hashes']=all(sha(pathlib.Path(x['absolute_path']))==x['image_sha256'] for x in allow)
f=json.loads((R/'reference/reference_freeze.json').read_text());pre=json.loads((R/'01_footprint/runtime_preflight.json').read_text())
checks['reference_hashes']=all(sha(R/'reference'/k)==v for k,v in f['files'].items());checks['reference_frozen_before_inference']=f['frozen_at_unix']<pre['started_at'];checks['freeze_excludes_self']='reference_freeze.json' not in f['files']
raw=lines(R/'01_footprint/segmentation_outputs.jsonl');fps=lines(R/'01_footprint/footprint_outputs.jsonl');logs=lines(R/'01_footprint/detector_manifest.jsonl');e=lines(R/'02_spatial_evidence/spatial_evidence.jsonl')
checks['all_60_images_accounted']=len(raw)==len(logs)==60 and {x['image_id'] for x in raw}==ids and {x['image_id'] for x in logs}==ids
checks['counts_raw_dedup']=sum(len(x['detections']) for x in raw)==196 and sum(len(x['suppressed']) for x in raw)==1 and len(fps)==195
checks['coordinates_and_area']=all(x['coordinate_space']=='image' and all(math.isfinite(t) for p in x['mask_polygon_image'] for t in p) and all(0<=p[0]<=1920 and 0<=p[1]<=1080 for p in x['mask_polygon_image']) for x in fps)
checks['no_fake_ground_contact']=all(x['ground_contact_polygon_image'] is None and x['ground_contact_status']=='unvalidated' and x['status']=='uncertain' for x in fps)
checks['missing_roi_not_zero_overlap']=len(e)==195 and all(x['road_overlap_ratio'] is None and x['evidence_status']=='uncertain' for x in e)
g=json.loads((R/'06_audit/p0_gate.json').read_text());checks['p0_gate_closed']=not g['vlm_authorized'] and not g['rules_pilot_authorized'] and g['coverage']==0
m=json.loads((R/'05_evaluation/p0_metrics.json').read_text());matches=lines(R/'05_evaluation/detector_matches.jsonl');checks['matched_numerator_recount']=sum(x['matched_vehicle_id'] is not None for x in matches)==m['detector_reference_bbox_match']['numerator']==155 and len(matches)==240
checks['no_classification_metrics_claimed']=all(v is None for k,v in m['classification_metrics'].items() if k!='status')
protected=json.loads((R/'contracts/protected_hashes_before.json').read_text());changed=[p for p,h in protected.items() if not pathlib.Path(p).is_file() or sha(pathlib.Path(p))!=h];checks['protected_snapshot_unchanged']=not changed;details['protected_changed']=changed;details['protected_files_checked']=len(protected)
initial=json.loads((R/'contracts/initial_state.json').read_text());prod='/home/yanbo/net_vlm_yanboversion/vlm';status=subprocess.run(['git','-C',prod,'status','--porcelain=v1'],text=True,capture_output=True,check=True).stdout;checks['production_git_status_unchanged']=status==initial[prod]
results=json.loads((R/'tests/test_results.json').read_text());checks['tests_pass']=all(x['returncode']==0 for x in results)
checks['no_winner']=json.loads((R/'contracts/candidate_registry.json').read_text())['winner'] is None
result={'status':'PASS_SCOPED_INTEGRITY' if all(checks.values()) else 'FAIL','capability_status':'BLOCKED_NOT_PASSED','checks':checks,'details':details,'scope_limits':['source hash reads restricted to 60 allowlisted DEV images','protected snapshot excludes image/video files and most v2 files; no blanket byte-level assertion for all forbidden directories','network protection is Python-level guard, no packet capture; no VLM runner invoked','full pixel alignment and all detector misses not reviewed','candidate thresholds not evaluated','metrics match recount verifies saved posthoc associations; independent reviewer separately checks matching semantics']}
(R/'06_audit/audit_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(not all(checks.values()))
