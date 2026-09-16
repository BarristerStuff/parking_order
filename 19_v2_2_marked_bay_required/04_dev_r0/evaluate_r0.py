import csv,json,math,statistics,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).parent
inputs=[json.loads(x) for x in open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl')]
token_to_mid={r['sample_token']:Path(r['image_path']).stem for r in inputs}
gt={r['media_id']:r for r in csv.DictReader(open(ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv'))}
preds=[json.loads(x) for x in open(OUT/'predictions.jsonl')]
errors=[]; enriched=[]
for p in preds:
 mid=token_to_mid.get(p['media_id'])
 if not mid or mid not in gt:errors.append({'sample_token':p.get('media_id'),'error':'source_binding_failure'});continue
 r={**p,'media_id_actual':mid,'gt':gt[mid]['event_label'],'group_key':gt[mid]['group_key'],'gt_source':gt[mid]['gt_source']};enriched.append(r)
if len(enriched)!=238:errors.append({'error':f'enriched_count={len(enriched)}'})

def binpred(p):return 'positive' if p['frame_decision']=='positive' else 'negative' if p['frame_decision']=='negative' else 'uncertain'
primary=[r for r in enriched if r['gt'] in ('positive','negative')]
tp=sum(r['gt']=='positive' and binpred(r)=='positive' for r in primary); fn=sum(r['gt']=='positive' and binpred(r)!='positive' for r in primary)
fp=sum(r['gt']=='negative' and binpred(r)=='positive' for r in primary); tn=sum(r['gt']=='negative' and binpred(r)!='positive' for r in primary)
div=lambda a,b:a/b if b else None
precision=div(tp,tp+fp);recall=div(tp,tp+fn);f1=div(2*precision*recall,precision+recall) if precision is not None and recall is not None and precision+recall else 0
fpr=div(fp,fp+tn);spec=1-fpr;acc=div(tp+tn,len(primary));bal=(recall+spec)/2

def wilson(k,n,z=1.959963984540054):
 if not n:return [None,None]
 ph=k/n; den=1+z*z/n; c=(ph+z*z/(2*n))/den; h=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den;return [c-h,c+h]
def rate(rows,gtlabel='positive'):
 den=[r for r in rows if r['gt']==gtlabel];num=sum(binpred(r)=='positive' for r in den);return {'numerator':num,'denominator':len(den),'rate':div(num,len(den))}
def subgroup(group,label=None):return rate([r for r in enriched if r['group_key']==group],label or 'positive')
p01=subgroup('p01-outside-legal-bay-clear');p03=subgroup('p03-span-two-bays')
minor=[r for r in enriched if r['group_key']=='n02-close-to-line-but-inside' or (r['group_key']=='p02-cross-single-boundary-line' and r['gt']=='negative')]
minor_fp=sum(binpred(r)=='positive' for r in minor);minor_fpr=div(minor_fp,len(minor))
gate=[r for r in enriched if r['gt']=='secondary_gate_queue'];gate_fp=sum(binpred(r)=='positive' for r in gate);gate_fpr=div(gate_fp,len(gate))
# semantic risk metrics
marked=[r for r in enriched if r['gt']=='negative']; marked_recall=div(sum(binpred(r)!='positive' for r in marked),len(marked))
outside=[r for r in enriched if r['gt']=='positive' and r['group_key'] in ('p01-outside-legal-bay-clear','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation','p06-nose-or-tail-intrudes-aisle')]
multibay=[r for r in enriched if r['gt']=='positive' and r['group_key'] in ('p03-span-two-bays','p02-cross-single-boundary-line','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation')]
model_unc=sum(binpred(r)=='uncertain' for r in enriched)
ledger=[json.loads(x) for x in open(OUT/'request_ledger.jsonl')]; starts=[r for r in ledger if r['event']=='request_start'];results=[r for r in ledger if r['event']=='request_result'];success=[r for r in results if r.get('schema_success')]
logical_expected=sum(1+(any(v.get('q1') in ('B','C') for v in [vv] ) and 1 or 0) for p in enriched for vv in p.get('vehicles',[]))
# each vehicle Q1 plus Q3 for B/C
logical_expected=sum(len(p.get('vehicles',[]))+sum(v.get('q1') in ('B','C') for v in p.get('vehicles',[])) for p in enriched)
protocol=div(len(success),len(results)) if results else 0
lats=[r.get('total_latency_seconds',0) for r in enriched]
metrics={'stage':'V2_2_R0_MINIMAL_SEMANTIC_CHANGE','primary_denominator':len(primary),'positive_gt':sum(r['gt']=='positive' for r in primary),'negative_gt':sum(r['gt']=='negative' for r in primary),'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':precision,'recall':recall,'f1':f1,'accuracy':acc,'specificity':spec,'fpr':fpr,'balanced_accuracy':bal,'recall_wilson95':wilson(tp,tp+fn),'fpr_wilson95':wilson(fp,fp+tn),'model_uncertain_count':model_unc,'model_uncertain_rate':model_unc/238,'p01_recall':p01,'p03_recall':p03,'minor_crossing_fpr':{'numerator':minor_fp,'denominator':len(minor),'rate':minor_fpr},'gate_queue_fpr':{'numerator':gate_fp,'denominator':len(gate),'rate':gate_fpr},'marked_bay_recall':marked_recall,'unmarked_or_outside_recall':rate(outside),'multibay_recall':rate(multibay),'protocol_success_rate':protocol,'physical_request_count':len(starts),'logical_expected_request_count':logical_expected,'request_result_count':len(results)}
# gate
gates={'precision':precision>=.90,'recall':recall>=.85,'f1':f1>=.87,'negative_fpr':fpr<=.05,'p01_recall':p01['rate']>=.85,'p03_recall':p03['rate']>=.80,'minor_crossing_fpr':minor_fpr<=.10,'gate_queue_fpr':gate_fpr==0,'protocol_success':protocol==1.0}
metrics['gates']=gates;metrics['gate_pass']=all(gates.values())
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
# subgroup table, including adjudicated polarity slices
subrows=[]
for g in sorted({r['group_key'] for r in enriched}):
 for label in ('positive','negative','uncertain','secondary_gate_queue'):
  rr=[r for r in enriched if r['group_key']==g and r['gt']==label]
  if rr:subrows.append({'subgroup':g+('_'+label if g.startswith('p0') and label in ('positive','negative') else ''),'gt_label':label,'count':len(rr),'pred_positive':sum(binpred(x)=='positive' for x in rr),'pred_negative':sum(binpred(x)=='negative' for x in rr),'pred_uncertain':sum(binpred(x)=='uncertain' for x in rr),'positive_rate':div(sum(binpred(x)=='positive' for x in rr),len(rr))})
with (OUT/'subgroup_metrics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=subrows[0],lineterminator='\n');w.writeheader();w.writerows(subrows)
lat={'count':len(lats),'p50_seconds':statistics.median(lats),'p95_seconds':sorted(lats)[math.ceil(.95*len(lats))-1],'max_seconds':max(lats),'physical_request_count':len(starts),'q1_request_count':sum(r.get('question')=='q1' for r in starts),'q3_request_count':sum(r.get('question')=='q3' for r in starts)};(OUT/'latency.json').write_text(json.dumps(lat,indent=2)+'\n')
with (OUT/'errors.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['sample_token','error'],lineterminator='\n');w.writeheader();w.writerows([{'sample_token':e.get('sample_token',''),'error':e['error']} for e in errors])
validation={'error_count':len(errors),'prediction_count':len(preds),'source_bound_count':len(enriched),'unique_media_ids':len({r['media_id_actual'] for r in enriched}),'gt_sha256':hashlib.sha256((ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv').read_bytes()).hexdigest(),'recomputed_metrics':metrics,'ledger_request_starts':len(starts),'ledger_results':len(results),'ledger_successes':len(success)};(OUT/'independent_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
# failure taxonomy
if not metrics['gate_pass']:
 tax=[]
 for r in primary+gate:
  wrong=(r['gt']=='positive' and binpred(r)!='positive') or (r['gt'] in ('negative','secondary_gate_queue') and binpred(r)=='positive')
  if not wrong:continue
  vs=r.get('vehicles',[]); kind='protocol_error' if r.get('status')!='ok' else 'detector_no_vehicle' if not vs else 'multi_vehicle_fusion_error' if len(vs)>1 else 'q1_D_uncertain' if any(v.get('q1')=='D' for v in vs) else 'q3_gate_false_suppression' if r['gt']=='positive' and any(v.get('q3')=='A' for v in vs) else 'q3_gate_false_positive' if r['gt']=='secondary_gate_queue' and any(v.get('q3') in ('B','C') for v in vs) else 'q1_A_false_negative' if r['gt']=='positive' and all(v.get('q1')=='A' for v in vs) else 'q1_B_false_positive' if any(v.get('q1')=='B' for v in vs) else 'q1_C_false_positive' if any(v.get('q1')=='C' for v in vs) else 'selection_wrong_vehicle'
  tax.append({'media_id':r['media_id_actual'],'group_key':r['group_key'],'gt':r['gt'],'prediction':binpred(r),'taxonomy':kind})
 with (OUT/'failure_taxonomy.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=tax[0] if tax else ['media_id','group_key','gt','prediction','taxonomy'],lineterminator='\n');w.writeheader();w.writerows(tax)
# R1 conclusion
if recall<.75 and fpr>.10:r1_allowed=False;r1='NONE';status='V2_2_MINIMAL_SUCCESSOR_NOT_VIABLE'
elif recall<.85 and fpr<=.05:r1_allowed=True;r1='RECALL';status='V2_2_R0_DEV_GATE_FAIL_R1_RECALL_ALLOWED'
elif recall>=.85 and fpr>.05:r1_allowed=True;r1='PRECISION';status='V2_2_R0_DEV_GATE_FAIL_R1_PRECISION_ALLOWED'
elif metrics['gate_pass']:r1_allowed=False;r1='NONE';status='V2_2_R0_DEV_GATE_PASS'
else:r1_allowed=False;r1='NONE';status='V2_2_R0_DEV_GATE_FAIL_MIXED_REVIEW_REQUIRED'
report=f'''# V2.2 R0 DEV report\n\nFINAL_STATUS={status}\n\nPrimary denominator: {len(primary)} (positive {metrics['positive_gt']}, negative {metrics['negative_gt']}); uncertain GT and gate secondary excluded from primary confusion.\n\nTP={tp} FP={fp} TN={tn} FN={fn}\nPrecision={precision:.6f} Recall={recall:.6f} F1={f1:.6f} FPR={fpr:.6f} BalancedAccuracy={bal:.6f}\nP01Recall={p01['rate']:.6f} P03Recall={p03['rate']:.6f} MinorCrossingFPR={minor_fpr:.6f} GateQueueFPR={gate_fpr:.6f}\nProtocolSuccessRate={protocol:.6f}; ModelUncertainRate={model_unc/238:.6f}\nR0_GATE_PASS={str(metrics['gate_pass']).lower()}\nR1_ALLOWED={str(r1_allowed).lower()}\nR1_RECOMMENDED={r1}\nDEV_CHAMPION={'R0' if metrics['gate_pass'] else 'NONE'}\n\nNo VAL/HOLDOUT was executed.\n'''
(OUT/'R0_REPORT.md').write_text(report)
print(json.dumps({'status':status,'metrics':metrics,'latency':lat,'r1_allowed':r1_allowed,'r1':r1},indent=2))
