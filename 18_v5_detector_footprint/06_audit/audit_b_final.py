"""Independent B artifact/schema/count/reference review. No pixel decoding/model calls.
Tests are run through reviewed Python audit-hook wrapper, never B write entrypoints.
"""
import ast,collections,hashlib,importlib.util,json,math,os,pathlib,subprocess,sys,time
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).resolve().parent;R=O.parent;B=R/'02_footprint_audit';D=R/'01_detector_audit'
spec=importlib.util.spec_from_file_location('c_core',O/'audit_v5_p0.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
load=core.load;lines=core.lines;sha=core.sha;checks=[]
def ck(name,ok,details=None):checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':details})
manifest=load(B/'artifact_hash_manifest.json');bad=[]
for name,h in manifest['files'].items():
 p=pathlib.Path(name)
 if not p.resolve().is_relative_to(B) or p==B/'artifact_hash_manifest.json' or not p.is_file() or sha(p)!=h:bad.append(name)
ck('B_manifest_hashes',not bad,{'entries':len(manifest['files']),'bad':bad,'scope':'listed artifacts only; visuals separately hashed below'})
fc=load(B/'footprint_contract.json');ck('frozen_method_unchanged',sha(B/'footprint.py')==fc['code_sha256']=='fc8c4c7abeb586815ed29f001e54afc5088ff45c8af3d97ec4cb0d6e7cb42564')
ck('frozen_contract_payload',hashlib.sha256(json.dumps({k:v for k,v in fc.items() if k!='contract_sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()==fc['contract_sha256'])
source=D/'r1_targets.jsonl';targets=lines(source);rows=lines(B/'footprint_outputs.jsonl');fm=load(B/'footprint_metrics.json');targetmap={(t['image_id'],t['vehicle_id']):t for t in targets};methods=fc['methods'];rowmap={(r['image_id'],r['vehicle_id'],r['method']):r for r in rows}
ck('exact_target_method_cartesian_product',len(targetmap)==len(targets)==fm['unique_vehicles'] and len(rows)==len(rowmap)==fm['method_rows'] and set(rowmap)=={(*k,m) for k in targetmap for m in methods})
ck('source_identity',sha(source)==fm['source_sha256']==manifest['source_target_sha256'] and pathlib.Path(fm['source'])==source)
ck('schema_adapter_hash',sha(B/'serialize_audit.py')==fm['schema_serialization']['schema_adapter_sha256'])
allow=core.csvrows(R/'contracts/allowlist.csv');ids={x['image_id'] for x in allow};ck('DEV_allowlisted_keys',all(k[0] in ids for k in targetmap) and sha(R/'contracts/allowlist.csv')==fm['allowlist_sha256'])
aliasbad=[]
for r in rows:
 k=(r['image_id'],r['vehicle_id']);t=targetmap[k];q=r.get('quality',{});ev=r.get('evidence',{});algo=q.get('algorithmic',{});src=ev.get('source_target',{})
 ok=(r.get('bbox_xyxy')==t['bbox_xyxy'] and r.get('raw_detection_id')==t['raw_detection_id'] and r.get('footprint_source')==dict(zip(methods,['mask_bottom_band','bbox_lower_proxy']))[r['method']] and r.get('ground_contact_status')==r['status'] and algo.get('status')==r['status'] and algo.get('reasons')==r['reasons'] and q.get('visual')==ev.get('visual_review')==r['visual_review'] and ev.get('algorithmic_reasons')==r['reasons'] and src=={'path':str(source),'sha256':sha(source),'image_id':k[0],'vehicle_id':k[1]} and r['input_sha256']==sha(source) and r['contract_sha256']==fc['contract_sha256'])
 if not ok:aliasbad.append((*k,r['method']))
ck('all_442_alias_and_provenance_joins',not aliasbad,aliasbad)
ck('no_ground_promotion',all(r['ground_contact_polygon'] is None and r['footprintIoU'] is None and r['ground_validated'] is False and r['quality']['ground_validated'] is False and r['status'] in ('proxy','uncertain','failed') and r['ground_contact_status']!='validated' and r['scope']=='DIAGNOSTIC_ONLY' and r['data_role']=='latest_completed_R1_diagnostic_NOT_winner' and r['reference_association_status']=='geometric_association_only' for r in rows))
recomputed={}
for method in methods:
 subset=[r for r in rows if r['method']==method];count=collections.Counter(r['status'] for r in subset);reasons=collections.Counter(s for r in subset for s in r['reasons']);m=fm['methods'][method]
 available=sum(r['status']!='failed' and bool(r['contact_band_polygon'] if method==methods[0] else r['bbox_proxy_polygon']) for r in subset)
 valid=sum(r['visual_review'].get('proxy_visual_quality')=='qualitatively_valid_proxy' for r in subset);unreviewed=sum(r['visual_review']['status']=='unreviewed' for r in subset)
 ck(method+'_recounts',len(subset)==m['denominator'] and all(count[s]==v for s,v in m['status_counts'].items()) and sum(m['status_counts'].values())==len(subset) and dict(reasons)==m['reason_counts'] and available==m['available'] and valid==m['visually_qualitatively_valid_proxy'] and unreviewed==m['unreviewed'])
 recomputed[method]={'statuses':dict(count),'available':available,'documented_visually_plausible_proxy':valid,'unreviewed':unreviewed}
# Independent shoelace / segment intersection on serialized original mask polygons.
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def touches(a,b,c,d):
 e=1e-9
 if max(a[0],b[0])+e<min(c[0],d[0]) or max(c[0],d[0])+e<min(a[0],b[0]) or max(a[1],b[1])+e<min(c[1],d[1]) or max(c[1],d[1])+e<min(a[1],b[1]):return False
 vals=[cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)]
 def opposed(x,y):return abs(x)<=e or abs(y)<=e or (x>e and y<-e) or (y>e and x<-e)
 return opposed(*vals[:2]) and opposed(*vals[2:])
diags={(x['image_id'],x['vehicle_id']):x for x in lines(B/'mask_representation_diagnostics.jsonl')};numeric=0;rejected=0;diagbad=[];reasoncount=collections.Counter()
for k,t in targetmap.items():
 p=t['mask_polygon_image'];p=p[:-1] if len(p)>1 and p[0]==p[-1] else p;n=len(p);w,h=t['source_size']
 finite=all(math.isfinite(v) for xy in p for v in xy);inbounds=finite and all(0<=x<=w and 0<=y<=h for x,y in p);area=abs(sum(p[i][0]*p[(i+1)%n][1]-p[(i+1)%n][0]*p[i][1] for i in range(n)))/2;valid=n>=3 and finite and inbounds and math.isfinite(area) and area>0
 issues=[]
 if any(p[i]==p[(i+1)%n] for i in range(n)):issues.append('zero_length_edge')
 hit=False
 for i in range(n):
  if hit:break
  for j in range(i+2,n):
   if i==0 and j==n-1:continue
   if touches(p[i],p[(i+1)%n],p[j],p[(j+1)%n]):hit=True;break
 if hit:issues.append('self_intersection_or_nonadjacent_touch')
 passed=valid and not issues;numeric+=valid;rejected+=not passed;reasoncount.update(issues);d=diags[k]
 if d['numeric_valid']!=valid or d['exported_polygon_topology_pass']!=passed or set(d['topology_issues'])!=set(issues):diagbad.append(k)
 for method in methods:
  a=rowmap[(*k,method)]['quality']['algorithmic']
  if a['mask_numeric_validity']!={s:d[s] for s in ('finite','in_bounds','positive_area','numeric_valid')} or a['exported_polygon_topology_pass']!=passed:diagbad.append((*k,method))
ck('independent_numeric_topology_and_quality',not diagbad and numeric==fm['mask_numeric_validity']['joint_numeric_valid'] and rejected==fm['stricter_polygon_topology_validity']['exported_polygon_rejected'] and dict(reasoncount)==fm['stricter_polygon_topology_validity']['rejection_reason_counts'],{'numeric_valid':numeric,'topology_rejected':rejected,'mismatches':diagbad})
vl=load(B/'visual_review_log.json');reviews={(x['image_id'],x['vehicle_id']):x for x in vl['reviews']};index=load(B/'footprint_visuals/visual_index.json');ix={(x['image_id'],x['vehicle_id']):x for x in index};evidence_hashes={};reviewbad=[]
ck('review_log_binding',vl['source_sha256']==sha(source) and len(reviews)==len(vl['reviews']) and set(reviews)<=set(targetmap) and set(reviews)==set(ix) and sha(B/'visual_review_log.json')==fm['visual_review']['review_log_sha256'])
for k,rev in reviews.items():
 entry=ix[k]
 if targetmap[k]!=targets[entry['target_index']] or entry['source_sha256']!=sha(source):reviewbad.append(k)
 for evidence in rev['evidence']:
  ep=pathlib.Path(evidence)
  if not ep.resolve().is_relative_to(B/'footprint_visuals') or not ep.is_file():reviewbad.append((k,evidence))
  else:evidence_hashes[evidence]=sha(ep)
 for method,quality in zip(methods,['mask_method_proxy_quality','bbox_method_proxy_quality']):
  row=rowmap[(*k,method)];r=row['visual_review'];poly=row['contact_band_polygon'] if method==methods[0] else row['bbox_proxy_polygon']
  if r['status']!='reviewed_pixels_via_view_image' or r['proxy_visual_quality']!=rev[quality] or r['evidence']!=rev['evidence'] or r['observations']!=rev['observations'] or (r['proxy_visual_quality']=='qualitatively_valid_proxy' and (row['status']=='failed' or not poly)):reviewbad.append((*k,method))
ck('review_evidence_application',not reviewbad and len(reviews)==fm['visual_review']['reviewed_unique_vehicles'] and 2*len(reviews)==fm['visual_review']['reviewed_method_rows'] and sum(r['visual_review']['status']=='unreviewed' for r in rows)==2*(len(targets)-len(reviews)),{'documented_reviewed':len(reviews),'bad':reviewbad,'evidence_file_hashes':evidence_hashes,'limit':'Documentary verification, not independently observed B tool calls or C pixel review.'})
# Reconstruct fixed matches from independent C matcher and frozen reference, then group.
refs=lines(R.parent/'16_v4_dynamic_vlm/reference/reference_instances.jsonl');adapt=lines(R.parent/'16_v4_dynamic_vlm/inputs/pilot/adapted_inputs.jsonl');boxes={(x['media_id'],t['target_id']):t['bbox'] for x in adapt for t in x['kept_targets']};matched={}
for im in lines(D/'r1_matching.jsonl'):
 rr=[r for r in refs if r['media_id']==im['image_id']];m,_,_=core.match([boxes[(r['media_id'],r['target_id'])] for r in rr],[d['bbox_xyxy'] for d in im['detections']])
 for v in m:matched[(im['image_id'],rr[v['reference_index']]['target_id'])]=im['detections'][v['detection_index']]['vehicle_id']
groups={}
for group,label in [('road','positive_road'),('two_bay','positive_two_bays')]:
 groups[group]={}
 for method in methods:
  c=dict(denominator=0,available=0,qualitatively_valid=0,unavailable=0,available_unreviewed=0,available_reviewed_not_qualitatively_valid=0,unmatched_reference=0)
  for ref in refs:
   if ref['label']!=label:continue
   c['denominator']+=1;vehicle=matched.get((ref['media_id'],ref['target_id']))
   if vehicle is None:c['unavailable']+=1;c['unmatched_reference']+=1;continue
   r=rowmap[(ref['media_id'],vehicle,method)];poly=r['contact_band_polygon'] if method==methods[0] else r['bbox_proxy_polygon']
   if r['status']=='failed' or not poly:c['unavailable']+=1;continue
   c['available']+=1;review=r['visual_review']
   if review['status']=='unreviewed':c['available_unreviewed']+=1
   elif review['proxy_visual_quality']=='qualitatively_valid_proxy':c['qualitatively_valid']+=1
   else:c['available_reviewed_not_qualitatively_valid']+=1
  groups[group][method]=c
ck('independent_reference_group_recount',groups==fm['reference_evaluation']['groups'] and fm['reference_evaluation']['confirmed_matches'] is False and sha(D/'r1_matching.jsonl')==fm['reference_evaluation']['matching_sha256'],groups)
# Extract previously reviewed test wrapper without executing its orchestration.
node=next(n for n in ast.parse((O/'recheck_tests.py').read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='wrapper' for t in n.targets));wrapper=ast.literal_eval(node.value)
tests=[]
for name in ['test_footprint_methods.py','test_audit_integrity.py']:
 p=subprocess.run([sys.executable,'-B','-c',wrapper,str(O),str(B/name)],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(O)))
 tests.append({'suite':name,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
ck('B_tests_independent_execution',all(x['returncode']==0 for x in tests),tests)
result={'generated_at_unix':time.time(),'status':'PASS_B_DIAGNOSTIC_ARTIFACT_CHECKS' if all(c['status']=='PASS' for c in checks) else 'FAIL','whole_run_status':'PENDING_A_REVIEW_05_INTEGRATION_FINAL_MANIFEST','checks':checks,'counts':recomputed,'reference_groups':groups,'C_pixel_review_performed':False,'ground_validated':0,'footprintIoU':None,'limitations':['B visual observations are attributed to B, not independently re-observed by C.','Application evidence cannot prove OS access isolation or absence of unlogged calls.','14-entry B manifest is a listed-artifact manifest; it excludes visual media, hashed separately by C, and final run manifest remains pending.']}
(O/'b_final_audit_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':sum(c['status']=='PASS' for c in checks),'failed':[c for c in checks if c['status']=='FAIL'],'counts':recomputed,'tests':tests},ensure_ascii=False,indent=2));sys.exit(any(c['status']=='FAIL' for c in checks))
