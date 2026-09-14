#!/usr/bin/env python3
"""Independent stdlib-only audit. Never imports/runs implementation or decodes images.
Run python3 -B audit_v5_p0.py; --finalcheck validates manifest without changing reports.
"""
import sys
sys.dont_write_bytecode = True
import argparse, collections, csv, hashlib, json, math, os, pathlib, subprocess, time
O = pathlib.Path(__file__).resolve().parent
R = O.parent
P = R.parent
C = R/'contracts'
V = P/'17_v5_spatial_evidence_vlm'
F = P/'16_v4_dynamic_vlm'
checks = []
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def load(p): return json.loads(pathlib.Path(p).read_text())
def lines(p): return [json.loads(s) for s in pathlib.Path(p).read_text().splitlines() if s.strip()]
def csvrows(p):
    with pathlib.Path(p).open() as f: return list(csv.DictReader(f))
def check(name, ok, detail=None, pending=False):
    checks.append(dict(check=name,status='PASS' if ok else ('PENDING' if pending else 'FAIL'),detail=detail))
def write(name, value):
    dest=O/name
    if dest.resolve().parent != O: raise ValueError('write outside audit')
    dest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n' if not isinstance(value,str) else value)
def verify(name, files):
    bad=[]
    for p,h in files.items():
        try:
            if sha(p)!=h: bad.append({'path':str(p),'reason':'hash mismatch'})
        except OSError as e: bad.append({'path':str(p),'reason':str(e)})
    check(name,not bad,{'expected':len(files),'verified':len(files)-len(bad),'bad':bad})
    return not bad

def iou(a,b):
    for box in (a,b):
        if len(box)!=4 or not all(math.isfinite(v) for v in box) or box[2]<box[0] or box[3]<box[1]: raise ValueError('invalid bbox')
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union else 0.
def match(ref_boxes,det_boxes):
    edges=[]
    for ri,a in enumerate(ref_boxes):
        for di,b in enumerate(det_boxes):
            score=iou(a,b)
            if score>=.5: edges.append((-score,ri,di))
    seen_r=set();seen_d=set();out=[]
    for neg,ri,di in sorted(edges):
        if ri in seen_r or di in seen_d: continue
        seen_r.add(ri);seen_d.add(di)
        out.append(dict(reference_index=ri,detection_index=di,iou=-neg))
    return out,[i for i in range(len(ref_boxes)) if i not in seen_r],[i for i in range(len(det_boxes)) if i not in seen_d]

def finalcheck():
    p=C/'hash_manifest.json'
    if not p.exists(): return {'status':'PENDING','reason':'PENDING_FINAL_MANIFEST: contracts/hash_manifest.json not generated'}
    data=load(p);files=data.get('files',{})
    bad=[]
    for name,h in files.items():
        relative=pathlib.Path(name)
        q=R/relative
        # Validate the manifest key lexically. A bounded runtime symlink may
        # resolve to the frozen model store and is still hashed by content.
        if relative.is_absolute() or '..' in relative.parts or q==p: bad.append({'path':name,'reason':'outside root or self-reference'});continue
        try:
            if sha(q)!=h: bad.append({'path':name,'reason':'hash mismatch'})
        except OSError as e: bad.append({'path':name,'reason':str(e)})
    actual={str(q.relative_to(R)) for q in R.rglob('*') if q.is_file() and q!=p}
    missing=sorted(actual-set(files))
    return {'status':'PASS' if files and not bad and not missing else 'FAIL','manifest':str(p),'verified_entries':len(files)-len(bad),'bad':bad,'unlisted_files':missing,'writes_performed':False}

def audit():
    pre=load(C/'preflight.json');freeze=load(C/'preregistration_freeze.json');contract=load(C/'run_contract.json')
    verify('preregistration_hashes',{C/k:h for k,h in freeze['files'].items()})
    check('freeze_required_files',set(freeze['files'])=={'run_contract.json','allowlist.csv','pilot_manifest.csv','forbidden_split_metadata.csv'})
    check('frozen_matching',contract['matching']=={'method':'descending_iou_greedy_one_to_one','minimum_iou':.5,'tie_break':'reference_index_then_detection_index','labels_used':False,'matched_status':'geometric_match_until_visual_review'})
    old=load(V/'06_audit/hash_manifest.json')['files'];f4=load(F/'reference/REFERENCE_FREEZE.json')['files']
    verify('17_manifest_hashes',{V/k:h for k,h in old.items()})
    verify('16_reference_freeze',{F/'reference'/k:h for k,h in f4.items()})
    protected=load(C/'protected_before.json')
    expected=set(load(V/'contracts/protected_hashes_before.json'))|{str(V/k) for k in old}|{str(V/'06_audit/hash_manifest.json'),str(F/'reference/REFERENCE_FREEZE.json')}
    check('protected_keyset_no_silent_missing',set(protected)==expected,{'missing':sorted(expected-set(protected)),'extra':sorted(set(protected)-expected)})
    verify('protected_1121_hashes',protected)
    check('preflight_counts',pre['old_v5_manifest_verified_files']==len(old) and pre['old_v4_reference_verified_files']==len(f4) and pre['protected_file_count']==len(protected)==1121)
    allow=csvrows(C/'allowlist.csv');manifest=csvrows(C/'pilot_manifest.csv');ids={x['image_id'] for x in allow};by_id={x['image_id']:x for x in allow}
    check('allowlist_unique_60_dev',len(allow)==len(ids)==len(manifest)==60 and all(x['split']=='DEV' for x in manifest) and {x['media_id'] for x in manifest}==ids)
    check('allowlist_manifest_identity',all(x['absolute_path']==by_id[x['media_id']]['absolute_path'] and x['image_sha256']==by_id[x['media_id']]['image_sha256'] for x in manifest))
    # Hash only allowlisted originals; never decode an original or inspect forbidden image/label files.
    verify('allowlisted_original_hashes',{x['absolute_path']:x['image_sha256'] for x in allow})
    split=csvrows(P/'12_v2_not_in_bay/01_gt_and_split/v2_split.csv')
    dev={x['media_id'] for x in split if x['split']=='DEV'}
    check('allowlist_independent_split_metadata',ids<=dev and dict(collections.Counter(x['split'] for x in split))==pre['split_counts'])
    before=load(C/'initial_git_status.json');git={}
    for path,initial in before.items():
        proc=subprocess.run(['git','--no-optional-locks','-C',path,'status','--porcelain=v1'],capture_output=True,text=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        git[path]={'initial':initial,'current':proc.stdout,'returncode':proc.returncode}
        check('git_status_unchanged:'+path,proc.returncode==0 and proc.stdout==initial,git[path])
    refs=lines(F/'reference/reference_instances.jsonl');adapt=lines(F/'inputs/pilot/adapted_inputs.jsonl')
    check('reference_allowed_only',all(x['media_id'] in ids for x in refs+adapt))
    check('reference16_17_equal',refs==lines(V/'reference/reference_instances.jsonl'))
    boxes={(x['media_id'],t['target_id']):t['bbox'] for x in adapt for t in x['kept_targets']}
    refs_by={image:[r for r in refs if r['media_id']==image] for image in ids}
    support=collections.Counter(r['label'] for r in refs)
    check('reference_support_frozen',len(refs)==240 and support['positive_road']==14 and support['positive_two_bays']==18,dict(support))
    results={};D=R/'01_detector_audit'
    for run in ('r0','r1'):
        p=D/f'{run}_matching.jsonl'
        if not p.exists():
            check(run+'_outputs_available',False,'await implementation',pending=True);continue
        try:
            records=lines(p);raw=lines(D/f'{run}_raw_outputs.jsonl');targets=lines(D/f'{run}_targets.jsonl');logs=lines(D/f'{run}_log.jsonl')
            complete=(D/f'{run}_completion.json').exists()
            check(run+'_complete_60_images',complete and len(records)==60 and {x['image_id'] for x in records}==ids and len(raw)==len(logs)==60,{'records':len(records),'complete':complete},pending=not complete)
            mismatches=[];geometric=collections.Counter();total=0;details=[]
            for rec in records:
                image=rec['image_id'];rr=refs_by[image];det=rec['detections']
                reference_boxes=[boxes[(image,r['target_id'])] for r in rr]
                expected_refs=[dict(r,bbox_xyxy=b) for r,b in zip(rr,reference_boxes)]
                m,ur,ud=match(reference_boxes,[d['bbox_xyxy'] for d in det])
                if rec['references']!=expected_refs or rec['matches']!=m or rec['unmatched_reference_indices']!=ur or rec['unmatched_detection_indices']!=ud: mismatches.append(image)
                for pair in m: geometric[rr[pair['reference_index']]['label']]+=1
                total+=len(m);details.append({'image_id':image,'matches':m,'unmatched_reference_indices':ur,'unmatched_detection_indices':ud})
            check(run+'_independent_matching',not mismatches,{'mismatch_images':mismatches})
            check(run+'_target_join',targets==[d for rec in records for d in rec['detections']])
            dedup_bad=[]
            for rec,ra in zip(records,raw):
                kept=[];supp=[]
                for det in sorted(ra['detections'],key=lambda x:(-x['confidence'],x['raw_detection_id'])):
                    hit=next((old for old in kept if iou(det['bbox_xyxy'],old['bbox_xyxy'])>.8),None)
                    if hit: supp.append({'raw_detection_id':det['raw_detection_id'],'suppressed_by':hit['raw_detection_id'],'dedup_reason':'class_agnostic_iou_gt_0.80'})
                    else: kept.append(det)
                kept.sort(key=lambda x:x['raw_detection_id'])
                if supp!=ra['suppressed'] or supp!=rec['suppressed'] or len(kept)!=len(rec['detections']) or any(any(out.get(k)!=v for k,v in original.items()) for original,out in zip(kept,rec['detections'])): dedup_bad.append(rec['image_id'])
            check(run+'_independent_dedup_and_raw_join',not dedup_bad,dedup_bad)
            check(run+'_image_bindings',all(ra['image_id'] in ids and ra['source_sha256']==by_id[ra['image_id']]['image_sha256'] for ra in raw) and all(t['source_sha256']==by_id[t['image_id']]['image_sha256'] for t in targets))

            check(run+'_logs_counts',len(logs)==len(records)==len(raw) and all(l['image_id']==rec['image_id']==ra['image_id'] and l['raw']==len(ra['detections']) and l['kept']==len(rec['detections']) and l['matches']==len(rec['matches']) for l,rec,ra in zip(logs,records,raw)))
            config=load(D/f'{run}_config.json');fr=load(D/f'{run}_freeze.json')
            verify(run+'_freeze',{D/f'{run}_config.json':fr['config_sha256'],D/'run_detector.py':fr['source_sha256'],D/'matching.py':fr['matching_source_sha256'],C/'run_contract.json':fr['contract_sha256'],V/'reference/reference_instances.jsonl':fr['reference_sha256'],F/'inputs/pilot/adapted_inputs.jsonl':fr['adapted_inputs_sha256']})
            results[run]={'images':len(records),'raw_detection_count':sum(len(x['detections']) for x in raw),'kept_count':len(targets),'geometric_matches':total,'coverage_gate_upper_bound_pass':total/len(refs)>=.9 and geometric['positive_road']/support['positive_road']>=.9 and geometric['positive_two_bays']/support['positive_two_bays']>=.9,'geometric_by_label':dict(geometric),'support':{'overall':len(refs),**dict(support)},'geometric_coverage':{'overall':total/len(refs),**{k:geometric[k]/v for k,v in support.items()}},'visually_confirmed_count':None,'visual_status':'PENDING_REVIEW_EVIDENCE','local_detector_calls_from_success_logs':sum(x['status']=='ok' for x in logs),'true_recall':None,'true_fpr':None}
            write(run+'_independent_matching.json',details)
        except (OSError,ValueError,KeyError,TypeError) as e: check(run+'_parse_complete',False,str(e),pending=True)
    if (D/'r1_config.json').exists():
        a=load(D/'r0_config.json');b=load(D/'r1_config.json');changed=[k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)]
        check('r1_single_main_factor',len(changed)==1,changed)
        check('r1_rationale_available',(D/'r1_rationale.json').is_file(),pending=True)
        if (D/'r1_rationale.json').is_file():
            rationale=load(D/'r1_rationale.json');f1=load(D/'r1_freeze.json');rt1=load(D/'r1_runtime.json');c0=load(D/'r0_completion.json')
            check('r1_chronology',c0['completed_at_unix']<=rationale['written_at_unix']<=f1['frozen_at_unix']<=rt1['started_at_unix'])
            check('r1_rationale_factor',rationale['changed_main_factor']==changed[0] and rationale['before']==a[changed[0]] and rationale['after']==b[changed[0]] and bool(rationale['evidence']))
    check('no_extra_detector_candidates',not list(D.glob('r[2-9]*_raw_outputs.jsonl')))
    B=R/'02_footprint_audit'
    if (B/'footprint_contract.json').exists():
        fc=load(B/'footprint_contract.json');payload={k:v for k,v in fc.items() if k!='contract_sha256'}
        check('footprint_contract_hash',hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()==fc['contract_sha256'])
        verify('footprint_code_freeze',{B/'footprint.py':fc['code_sha256'],C/'run_contract.json':fc['run_contract_sha256']})
        for prefix in ('development_',''):
            out=B/(prefix+'footprint_outputs.jsonl');mp=B/(prefix+'footprint_metrics.json')
            if not out.exists() or not mp.exists():
                check(prefix+'footprint_outputs_ready',False,'await B final selected-detector outputs',pending=True);continue
            rows=lines(out);metrics=load(mp);keys={(x['image_id'],x['vehicle_id']) for x in rows};methods=fc['methods']
            check(prefix+'footprint_no_true_ground_claim',all(x['ground_contact_polygon'] is None and x['footprintIoU'] is None and x['ground_validated'] is False and x['status']!='validated' and x['scope']=='DIAGNOSTIC_ONLY' for x in rows) and metrics['ground_validated']==0 and metrics['footprintIoU'] is None)
            check(prefix+'footprint_counts',len(rows)==len(keys)*len(methods)==metrics['method_rows'] and len(keys)==metrics['unique_vehicles'] and len({x['image_id'] for x in rows})==metrics['image_count'] and len({(x['image_id'],x['vehicle_id'],x['method']) for x in rows})==len(rows))
            for method in methods:
                subset=[x for x in rows if x['method']==method];counts=collections.Counter(x['status'] for x in subset);reasons=collections.Counter(k for x in subset for k in x['reasons']);reported=metrics['methods'][method]
                check(prefix+method+'_status_reason_recount',len(subset)==len(keys)==reported['denominator'] and all(counts[k]==v for k,v in reported['status_counts'].items()) and sum(reported['status_counts'].values())==len(subset) and dict(reasons)==reported['reason_counts'])
            check(prefix+'footprint_allowed_ids',{x['image_id'] for x in rows}<=ids)
            source=pathlib.Path(metrics['source'])
            check(prefix+'footprint_source_hash',sha(source)==metrics['source_sha256'] and all(x['input_sha256']==metrics['source_sha256'] and x['contract_sha256']==fc['contract_sha256'] for x in rows))
            if not prefix:
                check('footprint_final_not_old_source',source.parent==D and source.name in ('r0_targets.jsonl','r1_targets.jsonl') and all(x['data_role']=='latest_completed_R1_diagnostic_NOT_winner' and x['scope']=='DIAGNOSTIC_ONLY' for x in rows))
    rulemetrics=R/'04_rule_engine/rule_metrics.json'
    if rulemetrics.exists():
        rm=load(rulemetrics);pred=lines(R/'04_rule_engine/rule_predictions.jsonl')
        check('rule_formal_metrics_null',rm['formal_pilot_rules_executed'] is False and all(rm[k] is None for k in ('road_recall','two_bay_recall','negative_fpr','gate_queue_fpr','uncertain_rate')))
        actual=[x['decision']['label']==x['expected'] and (x['decision']['label']!='uncertain' or x['decision']['alert'] is False) for x in pred]
        check('synthetic_result_recount_only',len(pred)==rm['test_count'] and sum(actual)==rm['test_pass_count'] and actual==[x['test_passed'] for x in pred],{'note':'artifact recount, not independent geometry execution'})
    # Completed implementation schemas are inspected and adapted before final sign-off.
    for part in ['01_detector_audit','03_spatial_evidence','04_rule_engine','05_evaluation']:
        check('semantic_review:'+part,False,'independent semantic final review still required; existence is not acceptance',pending=True)
    bpath=O/'b_final_audit_result.json'
    if bpath.exists():
        br=load(bpath)
        check('B_final_semantic_artifact_review',bool(br['checks']) and all(x['status']=='PASS' for x in br['checks']),{'result_sha256':sha(bpath),'scope':'diagnostic artifact verification, not independent visual gold'})
    else: check('B_final_semantic_artifact_review',False,'await B final check',pending=True)
    testpath=O/'independent_test_results.json'
    if testpath.exists():
        tr=load(testpath)
        check('independent_four_test_suites',len(tr['suites'])==4 and all(x['returncode']==0 for x in tr['suites']),tr)
    else: check('independent_four_test_suites',False,'not executed',pending=True)
    check('manifest_finalcheck',False,'PENDING_FINAL_MANIFEST: contracts/hash_manifest.json; --finalcheck is read-only',pending=True)
    result={'generated_at_unix':time.time(),'status':'FAIL' if any(c['status']=='FAIL' for c in checks) else 'PENDING','checks':checks,'detector_recomputed':results,'reference_support':dict(support),'physical_remote_model_requests':None,'remote_request_evidence':'No auditor model/network calls. Other workers require implementation/log review, not an OS-level proof.','auditor_local_detector_calls':0,'auditor_original_images_decoded':0,'access_evidence_limit':'Bounded metadata and hash reads; application logs/source cannot prove OS-level isolation or absence of unlogged calls.','git_limit':'Porcelain equality is not file-content equality; protected hashes cover only the frozen bounded snapshot.','Recall':None,'FPR':None}
    write('audit_result.json',result)
    write('validation_report.json',{'status':result['status'],'checks_passed':sum(x['status']=='PASS' for x in checks),'checks_failed':[x for x in checks if x['status']=='FAIL'],'checks_pending':[x for x in checks if x['status']=='PENDING'],'Recall':None,'FPR':None,'business_gate':'NOT_SIGNED_OFF'})
    write('independent_recheck.md','# Independent C recheck — interim\n\nStatus: '+result['status']+'\n\nActual checks and independently recomputed matching are recorded in audit_result.json. Matching and counts are independently recomputed without importing A matcher. Separate guarded tests and pure B method replay import reviewed implementation functions; no model calls, network calls, installs, or original-image decoding by C.\n\nFrozen reference is AI_VISUAL_REVIEWED_PROVISIONAL, not human gold. Geometric coverage is not visually confirmed coverage. Mask/proxy is never accepted as true ground footprint. Recall/FPR remain null until a real eligible evaluation is independently verified.\n\nB final artifact/alias/count/reference checks completed (see b_final_audit_result.json); B visual observations remain attributed to B, not C independent pixel confirmation. Pending: A final visual artifacts, main final integration and final test rerun, final manifest. Finalcheck does not write or self-hash. Application-level access evidence is not OS-level proof.\n')
    write('BLOCKED_INDEPENDENT_FINAL_REVIEW.md','# Not a final approval\n\nSee pending and failed checks in validation_report.json. Parallel implementation is not yet independently signed off.\n')
    print(json.dumps({'status':result['status'],'passed':sum(x['status']=='PASS' for x in checks),'failed':[x for x in checks if x['status']=='FAIL'],'detector':results},ensure_ascii=False,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--finalcheck',action='store_true');args=parser.parse_args()
    if args.finalcheck:
        result=finalcheck();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['status']=='PASS' else 2)
    audit()
