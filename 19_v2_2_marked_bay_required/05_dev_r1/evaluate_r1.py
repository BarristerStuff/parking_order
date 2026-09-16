import csv,json,math,statistics,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).parent
GT_PATH=ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv'
MANIFEST=OUT/'manifest.csv'; PRED=OUT/'predictions.jsonl'; LEDGER=OUT/'request_ledger.jsonl'; R0=ROOT/'19_v2_2_marked_bay_required/04_dev_r0/predictions.jsonl'
EXPECTED_GT_SHA='413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56'
EXPECTED_Q1='12c64bbf69915ac181a91adda39a8bd95ec26528d44f978e1eca6ad475a1cc9e'; EXPECTED_Q3='5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc'
div=lambda a,b:a/b if b else None
def loadj(p): return [json.loads(x) for x in open(p) if x.strip()]
def binpred(p): return p.get('frame_decision') if p.get('frame_decision') in ('positive','negative','uncertain') else 'uncertain'
def wilson(k,n,z=1.959963984540054):
 if not n:return [None,None]
 ph=k/n;den=1+z*z/n;c=(ph+z*z/(2*n))/den;h=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den;return [c-h,c+h]
manifest=list(csv.DictReader(open(MANIFEST,newline=''))); token_to_mid={r['sample_token']:Path(r['image_path']).stem for r in manifest}
gtrows=list(csv.DictReader(open(GT_PATH,newline=''))); gt={r['media_id']:r for r in gtrows}
preds=loadj(PRED); r0preds=loadj(R0); ledger=loadj(LEDGER)
errors=[]
if len(preds)!=238: errors.append({'sample_token':'','error':f'prediction_count={len(preds)}'})
if len({p.get('media_id') for p in preds})!=238:errors.append({'sample_token':'','error':'prediction_tokens_not_unique'})
if len(manifest)!=238 or len({r['sample_token'] for r in manifest})!=238:errors.append({'sample_token':'','error':'manifest_not_238_unique'})
gtsha=hashlib.sha256(GT_PATH.read_bytes()).hexdigest()
if gtsha!=EXPECTED_GT_SHA:errors.append({'sample_token':'','error':f'gt_sha_mismatch:{gtsha}'})
enriched=[]
for p in preds:
 token=p.get('media_id');mid=token_to_mid.get(token)
 if not mid or mid not in gt: errors.append({'sample_token':token or '','error':'source_binding_failure'});continue
 if p.get('status')!='ok' or p.get('error'):errors.append({'sample_token':token,'error':f"prediction_status:{p.get('status')}:{p.get('error')}"})
 if p.get('q1_sha')!=EXPECTED_Q1 or p.get('q3_sha')!=EXPECTED_Q3:errors.append({'sample_token':token,'error':'prompt_hash_mismatch'})
 enriched.append({**p,'media_id_actual':mid,'gt':gt[mid]['event_label'],'group_key':gt[mid]['group_key'],'gt_source':gt[mid]['gt_source']})
# required logical request completion, keyed by sample/rank/question
success_by_key={}
for x in ledger:
 if x.get('event')=='request_result' and x.get('schema_success'):
  success_by_key[(x.get('sample_token'),int(x.get('vehicle_rank')),x.get('question'))]=x
required=[]
for p in enriched:
 for v in p.get('vehicles',[]):
  required.append((p['media_id'],int(v['rank']),'q1'))
  if v.get('q1') in ('B','C'): required.append((p['media_id'],int(v['rank']),'q3'))
missing=[k for k in required if k not in success_by_key]
if missing: errors.extend({'sample_token':k[0],'error':f'missing_logical_success:{k[1]}:{k[2]}'} for k in missing)
logical_protocol=div(len(required)-len(missing),len(required)) or 0
# confusion: uncertain predictions count as not-positive, matching frozen R0 method
primary=[r for r in enriched if r['gt'] in ('positive','negative')]
tp=sum(r['gt']=='positive' and binpred(r)=='positive' for r in primary);fn=sum(r['gt']=='positive' and binpred(r)!='positive' for r in primary)
fp=sum(r['gt']=='negative' and binpred(r)=='positive' for r in primary);tn=sum(r['gt']=='negative' and binpred(r)!='positive' for r in primary)
precision=div(tp,tp+fp);recall=div(tp,tp+fn);f1=div(2*precision*recall,precision+recall) if precision is not None and recall is not None and precision+recall else 0
fpr=div(fp,fp+tn);spec=1-fpr;accuracy=div(tp+tn,len(primary));bal=(recall+spec)/2
def rate(rows,gtlabel='positive'):
 den=[r for r in rows if r['gt']==gtlabel];num=sum(binpred(r)=='positive' for r in den);return {'numerator':num,'denominator':len(den),'rate':div(num,len(den))}
def sg(g,label='positive'):return rate([r for r in enriched if r['group_key']==g],label)
p01=sg('p01-outside-legal-bay-clear');p03=sg('p03-span-two-bays')
minor=[r for r in enriched if r['group_key']=='n02-close-to-line-but-inside' or (r['group_key']=='p02-cross-single-boundary-line' and r['gt']=='negative')]
minor={'numerator':sum(binpred(r)=='positive' for r in minor),'denominator':len(minor),'rate':div(sum(binpred(r)=='positive' for r in minor),len(minor))}
gate=[r for r in enriched if r['gt']=='secondary_gate_queue'];gate_metric={'numerator':sum(binpred(r)=='positive' for r in gate),'denominator':len(gate),'rate':div(sum(binpred(r)=='positive' for r in gate),len(gate))}
outside_groups={'p01-outside-legal-bay-clear','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation','p06-nose-or-tail-intrudes-aisle'}
multibay_groups={'p03-span-two-bays','p02-cross-single-boundary-line','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation'}
outside=rate([r for r in enriched if r['gt']=='positive' and r['group_key'] in outside_groups])
multibay=rate([r for r in enriched if r['gt']=='positive' and r['group_key'] in multibay_groups])
model_unc=sum(binpred(r)=='uncertain' for r in enriched)
starts=[x for x in ledger if x.get('event')=='request_start']; results=[x for x in ledger if x.get('event')=='request_result']; successes=[x for x in results if x.get('schema_success')];timeouts=[x for x in results if not x.get('schema_success') and 'timed out' in str(x.get('error','')).lower()]
lats=[r.get('total_latency_seconds',0) for r in enriched]
gates={'precision':precision>=.90,'recall':recall>=.85,'f1':f1>=.87,'negative_fpr':fpr<=.05,'p01_recall':p01['rate']>=.85,'p03_recall':p03['rate']>=.80,'minor_crossing_fpr':minor['rate']<=.10,'gate_queue_fpr':gate_metric['rate']==0,'protocol_success':logical_protocol==1.0}
complete=len(enriched)==238 and len({r['media_id_actual'] for r in enriched})==238 and not errors and logical_protocol==1.0
gate_pass=complete and all(gates.values())
metrics={'stage':'V2_2_R1_RECALL','primary_denominator':len(primary),'positive_gt':sum(r['gt']=='positive' for r in primary),'negative_gt':sum(r['gt']=='negative' for r in primary),'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':precision,'recall':recall,'f1':f1,'accuracy':accuracy,'specificity':spec,'fpr':fpr,'balanced_accuracy':bal,'recall_wilson95':wilson(tp,tp+fn),'fpr_wilson95':wilson(fp,fp+tn),'model_uncertain_count':model_unc,'model_uncertain_rate':div(model_unc,len(enriched)),'p01_recall':p01,'p03_recall':p03,'unmarked_or_outside_recall':outside,'multibay_recall':multibay,'minor_crossing_fpr':minor,'gate_queue_fpr':gate_metric,'protocol_success_rate':logical_protocol,'logical_required_request_count':len(required),'logical_successful_request_count':len(required)-len(missing),'historical_physical_start_count':len(starts),'historical_result_count':len(results),'historical_schema_success_count':len(successes),'historical_timeout_count':len(timeouts),'gates':gates,'gate_pass':gate_pass}
# subgroup output
sub=[]
for g in sorted({r['group_key'] for r in enriched}):
 for label in ('positive','negative','uncertain','secondary_gate_queue'):
  rr=[r for r in enriched if r['group_key']==g and r['gt']==label]
  if rr:
   name=g+('_'+label if g.startswith('p0') and label in ('positive','negative') else '')
   sub.append({'subgroup':name,'gt_label':label,'count':len(rr),'pred_positive':sum(binpred(x)=='positive' for x in rr),'pred_negative':sum(binpred(x)=='negative' for x in rr),'pred_uncertain':sum(binpred(x)=='uncertain' for x in rr),'positive_rate':div(sum(binpred(x)=='positive' for x in rr),len(rr))})
with (OUT/'subgroup_metrics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=sub[0].keys(),lineterminator='\n');w.writeheader();w.writerows(sub)
# q1 distributions (vehicle-level)
def qdist(rows,keyfn):
 out=[]
 for key,rr in sorted(collections.defaultdict(list,((None,[]),)).items()):pass
 buckets=collections.defaultdict(collections.Counter)
 for r in rows:
  for v in r.get('vehicles',[]):buckets[keyfn(r)][v.get('q1')]+=1
 for k,c in sorted(buckets.items(),key=lambda z:str(z[0])):out.append({'bucket':k,'vehicle_count':sum(c.values()),'A':c['A'],'B':c['B'],'C':c['C'],'D':c['D']})
 return out
for name,rows in [('q1_distribution_by_gt.csv',qdist(enriched,lambda r:r['gt'])),('q1_distribution_by_group.csv',qdist(enriched,lambda r:r['group_key']))]:
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['bucket','vehicle_count','A','B','C','D'],lineterminator='\n');w.writeheader();w.writerows(rows)
# R0 comparison
r0map={p['media_id']:p for p in r0preds};r1map={p['media_id']:p for p in enriched}
def all_a(p):return bool(p.get('vehicles')) and all(v.get('q1')=='A' for v in p['vehicles'])
def any_bc(p):return any(v.get('q1') in ('B','C') for v in p.get('vehicles',[]))
pos_a_to_bc=sum(r['gt']=='positive' and all_a(r0map[r['media_id']]) and any_bc(r) for r in enriched)
neg_a_to_bc=sum(r['gt']=='negative' and all_a(r0map[r['media_id']]) and any_bc(r) for r in enriched)
r0m={'TP':3,'FP':0,'TN':134,'FN':59,'precision':1.0,'recall':3/62,'f1':6/65,'fpr':0.0}
deltas={'TP':tp-r0m['TP'],'FP':fp-r0m['FP'],'FN':fn-r0m['FN'],'recall':recall-r0m['recall'],'fpr':fpr-r0m['fpr'],'f1':f1-r0m['f1'],'positive_gt_r0_all_A_to_r1_B_or_C':pos_a_to_bc,'negative_gt_r0_all_A_to_r1_B_or_C':neg_a_to_bc}
metrics['r0_baseline']=r0m;metrics['r0_to_r1_delta']=deltas
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
lat={'prediction_count':len(lats),'p50_seconds':statistics.median(lats),'p95_seconds':sorted(lats)[math.ceil(.95*len(lats))-1],'max_seconds':max(lats),'physical_request_start_count':len(starts),'physical_request_result_count':len(results),'schema_success_result_count':len(successes),'timeout_result_count':len(timeouts)};(OUT/'latency.json').write_text(json.dumps(lat,indent=2)+'\n')
with (OUT/'errors.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['sample_token','error'],lineterminator='\n');w.writeheader();w.writerows(errors)
validation={'error_count':len(errors),'prediction_coverage':len(enriched),'unique_predictions':len({r['media_id_actual'] for r in enriched}),'manifest_count':len(manifest),'gt_sha256':gtsha,'gt_sha_exact':gtsha==EXPECTED_GT_SHA,'logical_required_requests':len(required),'logical_successful_requests':len(required)-len(missing),'protocol_success_rate':logical_protocol,'historical_failed_transport_results_preserved':len(results)-len(successes),'historical_incomplete_starts_preserved':len(starts)-len(results),'complete_for_gate':complete,'recomputed_metrics':metrics};(OUT/'independent_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
# diagnostic taxonomy; descriptive only, no root-cause claim
bad=[]
for r in primary+gate:
 wrong=(r['gt']=='positive' and binpred(r)!='positive') or (r['gt'] in ('negative','secondary_gate_queue') and binpred(r)=='positive')
 if not wrong:continue
 vs=r.get('vehicles',[])
 kind='protocol_error' if r.get('status')!='ok' else 'detector_no_vehicle' if not vs else 'q1_D_uncertain' if any(v.get('q1')=='D' for v in vs) else 'q3_gate_false_suppression' if r['gt']=='positive' and any(v.get('q3')=='A' for v in vs) else 'q3_gate_false_positive' if r['gt']=='secondary_gate_queue' and any(v.get('q3') in ('B','C') for v in vs) else 'q1_A_false_negative' if r['gt']=='positive' and all(v.get('q1')=='A' for v in vs) else 'q1_B_false_positive' if any(v.get('q1')=='B' for v in vs) else 'q1_C_false_positive' if any(v.get('q1')=='C' for v in vs) else 'multi_vehicle_fusion_error' if len(vs)>1 else 'selection_wrong_vehicle'
 bad.append({'media_id':r['media_id_actual'],'group_key':r['group_key'],'gt':r['gt'],'prediction':binpred(r),'taxonomy':kind})
with (OUT/'failure_taxonomy.csv').open('w',newline='') as f:
 fields=['media_id','group_key','gt','prediction','taxonomy'];w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(bad)
if not complete: status='V2_2_R1_BLOCKED_INDEPENDENT_VALIDATION'; champion='NONE'; gate_value='N/A'
elif gate_pass:status='V2_2_R1_DEV_GATE_PASS';champion='R1';gate_value=True
else:status='V2_2_R1_DEV_GATE_FAIL';champion='NONE';gate_value=False
major=recall<.50 if complete else None;improved=(recall>=.50 and recall<.85 and fpr<=.05) if complete else None
decision={'FINAL_STATUS':status,'R1_GATE_PASS':gate_value,'DEV_CHAMPION':champion,'READY_FOR_NEW_CHALLENGE':bool(gate_pass),'R2_ALLOWED':False,'QWEN4B_MARKED_BAY_RELATION_MAJOR_LIMIT':major,'PROMPT_RECALL_IMPROVED_BUT_GATE_NOT_REACHED':improved,'VAL_EXECUTED':False,'HOLDOUT_EXECUTED':False};(OUT/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
report=f'''# V2.2 R1 Recall DEV Report\n\nFINAL_STATUS={status}\n\nCoverage: {len(enriched)}/238 unique={len({r['media_id_actual'] for r in enriched})}. GT SHA exact={gtsha==EXPECTED_GT_SHA}. Logical protocol success={logical_protocol:.6f}. Historical timeout evidence remains preserved.\n\nPrimary denominator: {len(primary)} (positive {sum(r['gt']=='positive' for r in primary)}, negative {sum(r['gt']=='negative' for r in primary)}); uncertain and gate-secondary GT are excluded from primary confusion.\n\nR0: TP=3 FP=0 TN=134 FN=59\nR1: TP={tp} FP={fp} TN={tn} FN={fn}\nPrecision={precision:.6f} Recall={recall:.6f} F1={f1:.6f} FPR={fpr:.6f} BalancedAccuracy={bal:.6f}\nP01Recall={p01['rate']:.6f} P03Recall={p03['rate']:.6f}\nUnmarkedOrOutsideRecall={outside['rate']:.6f} MultibayRecall={multibay['rate']:.6f} MinorCrossingFPR={minor['rate']:.6f} GateQueueFPR={gate_metric['rate']:.6f}\n\nR0 to R1: delta TP={deltas['TP']} FP={deltas['FP']} FN={deltas['FN']} Recall={deltas['recall']:.6f} FPR={deltas['fpr']:.6f} F1={deltas['f1']:.6f}.\nPositive GT R0-all-A to R1 B/C={pos_a_to_bc}; negative GT R0-all-A to R1 B/C={neg_a_to_bc}.\n\nR1_GATE_PASS={str(gate_value).lower() if isinstance(gate_value,bool) else gate_value}\nDEV_CHAMPION={champion}\nR2_ALLOWED=false\n\nNo VAL or HOLDOUT was executed. Taxonomy is diagnostic and not asserted as proven root cause.\n''';(OUT/'R1_REPORT.md').write_text(report)
print(json.dumps({'decision':decision,'metrics':metrics,'validation':validation,'latency':lat},indent=2))
