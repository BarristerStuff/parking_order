import sys;sys.dont_write_bytecode=True
import json,pathlib,time,csv,math,collections
O=pathlib.Path(__file__).resolve().parent
def load(p):return [json.loads(x) for x in p.read_text().splitlines()]
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def rate(k,n):
 z=1.95996398454;p=k/n;c=(p+z*z/(2*n))/(1+z*z/n);h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
 return dict(numerator=k,denominator=n,rate=p,wilson95=[max(0,c-h),min(1,c+h)])
dec=json.loads((O/'visual_decisions.json').read_text());logs=[];allrows=[];metrics={};tables={k:[] for k in ['unmatched_reference','unmatched_detection','duplicate_detection']}
for run in ['r0','r1']:
 rows=load(O/f'{run}_matching.jsonl');rv=dec[run];good=[];geometric=[];refs=[]
 for ix,x in enumerate(rows):
  img=x['image_id'];suffix=img[4:];viewed=ix<rv['viewed_sheets']*6;medium=str(O/'detection_overlays'/f'{run}_sheet_{ix//6+1:02d}.jpg');byref={m['reference_index']:m for m in x['matches']}
  for ri,r in enumerate(x['references']):
   status='unresolved_reference_matching';obs='Small, occluded, overlapping or ambiguous reference identity/localization; contact sheet insufficient to confirm pairing.' if viewed else 'Not visually inspected yet.'
   if r['target_id'] in rv['confirmed'].get(suffix,[]):
    assert ri in byref,(run,img,r['target_id']);status='correct_detection';obs='Explicit visual decision: yellow reference and cyan detection enclose the same visible vehicle; recognizable body and location agree.';good.append(r)
   elif r['target_id'] in rv['miss'].get(suffix,[]):
    assert ri not in byref;status='confirmed_detector_miss';obs='Explicit visual decision: clearly visible vehicle enclosed by yellow reference lacks a cyan full-vehicle detection.'
   elif r['target_id'] in rv.get('reference_disputes',{}).get(suffix,[]):
    status='unresolved_reference_matching';obs='Explicit visual decision: frozen box appears to enclose a gate booth rather than a vehicle; retained in denominator as a disputed provisional reference and not called a detector miss.'
   m=byref.get(ri);d=x['detections'][m['detection_index']] if m else None
   log=dict(run=run,image_id=img,reference_id=r['target_id'],detection_id=d['vehicle_id'] if d else None,entity='reference',status=status,observation=obs,review_medium=medium if viewed else None,reviewed=viewed,reviewer='AI_visual_audit',recorded_at_unix=time.time())
   logs.append(log);r['audit_status']=status;r['audit_medium']=log['review_medium'];refs.append(r)
   if m:geometric.append(r);m['visual_status']=status
   else:tables['unmatched_reference'].append(dict(run=run,image_id=img,target_id=r['target_id'],status=status,observation=obs))
  for di in x['unmatched_detection_indices']:
   d=x['detections'][di];status='unresolved_reference_matching';obs='Cyan detection has no frozen geometric reference pairing; could be real unreferenced vehicle, reflection, localization mismatch or false detection. Not called false solely for lacking match.'
   if d['vehicle_id'] in rv.get('confirmed_unmatched_detections',{}).get(suffix,[]): status='correct_detection';obs='Explicit risk-sheet decision: visible vehicle without a frozen one-to-one reference pairing.'
   elif d['vehicle_id'] in rv.get('possible_false_detections',{}).get(suffix,[]): status='possible_false_detection';obs='Explicit risk-sheet decision: detection appears to cover booth/wall structure, but resolution is insufficient for confirmed false detection.'
   log=dict(run=run,image_id=img,target_id=d['vehicle_id'],raw_detection_id=d['raw_detection_id'],bbox=d['bbox_xyxy'],class_name=d['class_name'],confidence=d['confidence'],matched_reference_vehicle_id=None,match_status=status,dedup_status='kept',evidence=obs,entity='detection',status=status,observation=obs,review_medium=medium if viewed else None,reviewed=viewed)
   logs.append(log);tables['unmatched_detection'].append(log)
  for d in x['suppressed']:
   confirmed=d['raw_detection_id'] in rv.get('confirmed_duplicate_raw_ids',{}).get(suffix,[]);status='duplicate_detection' if confirmed else 'unresolved_reference_matching';obs='Explicit risk-sheet decision: two highly overlapping raw boxes cover the same visible background vehicle.' if confirmed else 'Algorithmic IoU>0.8 suppression; visual identity unresolved.'
   log=dict(run=run,image_id=img,target_id=d['raw_detection_id'],entity='duplicate',status=status,match_status=status,dedup_status='suppressed',evidence=obs,observation=obs,review_medium=medium if viewed else None,reviewed=confirmed,**d);logs.append(log);tables['duplicate_detection'].append(log)
  x['visual_status']='reviewed_with_unresolved' if viewed else 'not_reviewed';allrows.append(x)
 groups={'overall':lambda r:True,'positive_road':lambda r:r['label']=='positive_road','positive_two_bays':lambda r:r['label']=='positive_two_bays'}
 met={'images':60,'raw_detection_count':sum(len(x['detections'])+len(x['suppressed']) for x in rows),'detection_count':sum(len(x['detections']) for x in rows),'duplicate_count':sum(len(x['suppressed']) for x in rows),'geometric_matching':{k:rate(sum(f(r) for r in geometric),sum(f(r) for r in refs)) for k,f in groups.items()},'confirmed_match_coverage':{k:rate(sum(f(r) for r in good),sum(f(r) for r in refs)) for k,f in groups.items()},'reviewed_images':rv['viewed_sheets']*6,'review_status_counts':dict(collections.Counter(l['status'] for l in logs if l['run']==run)),'gate_status':'BLOCKED'}
 metrics[run]=met;dump(O/f'{run}_metrics.json',met)
 (O/f'{run}_reviewed_matching.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in allrows if x['run']==run))
(O/'review_log.jsonl').write_text(''.join(json.dumps(l)+'\n' for l in logs))
(O/'reference_detection_matching.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in allrows))
for name,data in tables.items():
 fields=sorted({k for x in data for k in x})
 with (O/f'{name}.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
dump(O/'detector_metrics.json',dict(metric_name='AI_PROVISIONAL_REFERENCE_COVERAGE',human_gold=False,source_run='r1',runs=metrics,gate_status='BLOCKED',footprint_scope='DIAGNOSTIC_ONLY',local_detector_calls=120,physical_remote_model_requests=0,review_complete=dec['r1']['viewed_sheets']==10))
print({run:m['confirmed_match_coverage'] for run,m in metrics.items()})
