import csv,json,hashlib,collections,math,statistics
from pathlib import Path
OUT=Path(__file__).parent;V=OUT.parent;ROOT=V.parent
pred=list(map(json.loads,open(OUT/'predictions.jsonl')));manifest=list(csv.DictReader(open(OUT/'pilot_manifest.csv',newline='')));gt={r['media_id']:r for r in csv.DictReader(open(ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv',newline=''))};ledger=list(map(json.loads,open(OUT/'request_ledger.jsonl')))
errors=[]; pm={r['media_id']:r for r in pred}
if len(pred)!=70 or len(pm)!=70:errors.append('prediction coverage/uniqueness')
for m in manifest:
 if m['media_id'] not in pm:errors.append('missing '+m['media_id'])
primary=[r for r in pred if gt[r['media_id']]['event_label'] in ('positive','negative')]; gate=[r for r in pred if gt[r['media_id']]['event_label']=='secondary_gate_queue']
pos=lambda r:r['frame_decision']=='positive'; label=lambda r:gt[r['media_id']]['event_label']; group=lambda r:gt[r['media_id']]['group_key'];div=lambda a,b:a/b if b else None
tp=sum(label(r)=='positive' and pos(r) for r in primary);fn=sum(label(r)=='positive' and not pos(r) for r in primary);fp=sum(label(r)=='negative' and pos(r) for r in primary);tn=sum(label(r)=='negative' and not pos(r) for r in primary)
precision=div(tp,tp+fp);recall=div(tp,tp+fn);fpr=div(fp,fp+tn);f1=2*precision*recall/(precision+recall) if precision+recall else 0
def rate(rows,positive_fn):return {'numerator':sum(positive_fn(r) for r in rows),'denominator':len(rows),'rate':div(sum(positive_fn(r) for r in rows),len(rows))}
p01=rate([r for r in primary if label(r)=='positive' and group(r)=='p01-outside-legal-bay-clear'],pos);p03=rate([r for r in primary if label(r)=='positive' and group(r)=='p03-span-two-bays'],pos)
minorrows=[r for r in primary if label(r)=='negative' and (group(r)=='n02-close-to-line-but-inside' or group(r)=='p02-cross-single-boundary-line')];minor=rate(minorrows,pos)
gatef=rate(gate,pos)
outside_groups={'p01-outside-legal-bay-clear','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation','p06-nose-or-tail-intrudes-aisle'};multi_groups={'p03-span-two-bays','p02-cross-single-boundary-line','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation'}
def anybranch(r,k):return any(v[k]=='YES' for v in r['vehicles'])
outpos=[r for r in primary if label(r)=='positive' and group(r) in outside_groups]; mulpos=[r for r in primary if label(r)=='positive' and group(r) in multi_groups];negs=[r for r in primary if label(r)=='negative']
outrec=rate(outpos,lambda r:anybranch(r,'outside'));outfpr=rate(negs,lambda r:anybranch(r,'outside'));mulrec=rate(mulpos,lambda r:anybranch(r,'multibay'));mulfpr=rate(negs,lambda r:anybranch(r,'multibay'))
conf=collections.Counter()
for r in pred:
 for v in r['vehicles']:conf[f"OUTSIDE={v['outside']};MULTIBAY={v['multibay']}"]+=1
results=[x for x in ledger if x['event']=='request_result'];succ=[x for x in results if x.get('schema_success')];starts=[x for x in ledger if x['event']=='request_start'];required=sum(2*len(r['vehicles'])+sum(v['outside']=='YES' or v['multibay']=='YES' for v in r['vehicles']) for r in pred);protocol=div(len(succ),required)
if len(succ)!=required:errors.append(f'logical success {len(succ)}/{required}')
# historical R1 subset
r1all=list(map(json.loads,open(ROOT/'19_v2_2_marked_bay_required/05_dev_r1/predictions.jsonl')));token_to_mid={r['sample_token']:Path(r['image_path']).stem for r in map(json.loads,open(ROOT/'12_v2_not_in_bay/03_debug/v2_dev_inference_input.jsonl'))};r1={token_to_mid[x['media_id']]:x for x in r1all};r1p=[r1[m['media_id']] for m in manifest if m['event_label'] in ('positive','negative')]
r1tp=sum(m['event_label']=='positive' and r1[m['media_id']]['frame_decision']=='positive' for m in manifest if m['event_label'] in ('positive','negative'));r1fn=30-r1tp;r1fp=sum(m['event_label']=='negative' and r1[m['media_id']]['frame_decision']=='positive' for m in manifest if m['event_label'] in ('positive','negative'));r1tn=30-r1fp
metrics={'pilot_total':70,'pilot_primary':60,'pilot_gate_secondary':10,'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':precision,'recall':recall,'f1':f1,'fpr':fpr,'p01_recall':p01,'p03_recall':p03,'minor_crossing_fpr':minor,'gate_queue_fpr':gatef,'outside_branch_recall':outrec,'outside_branch_fpr':outfpr,'multibay_branch_recall':mulrec,'multibay_branch_fpr':mulfpr,'branch_conflicts':dict(conf),'protocol_success':protocol,'request_starts':len(starts),'request_results':len(results),'schema_successes':len(succ),'v2_2_r1_subset':{'TP':r1tp,'FP':r1fp,'TN':r1tn,'FN':r1fn,'recall':r1tp/30,'fpr':r1fp/30}}
gates={'recall':recall>=.75,'negative_fpr':fpr<=.15,'p01_recall':p01['rate']>=.80,'p03_recall':p03['rate']>=.70,'minor_crossing_fpr':minor['rate']<=.20,'gate_queue_fpr':gatef['rate']==0,'protocol_success':protocol==1.0};passed=not errors and all(gates.values());metrics['gates']=gates;metrics['gate_pass']=passed
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n');(OUT/'independent_validation.json').write_text(json.dumps({'error_count':len(errors),'errors':errors,'prediction_coverage':len(pred),'unique':len(pm),'gt_sha':hashlib.sha256((ROOT/'19_v2_2_marked_bay_required/01_gt_migration/v2_2_dev_gt.csv').read_bytes()).hexdigest(),'recomputed_metrics':metrics},indent=2)+'\n')
# row-level results and branch diagnostics
with open(OUT/'pilot_results.csv','w',newline='') as f:
 fields=['media_id','group_key','gt','prediction','outside_yes','multibay_yes','vehicle_count'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in pred:w.writerow({'media_id':r['media_id'],'group_key':group(r),'gt':label(r),'prediction':r['frame_decision'],'outside_yes':anybranch(r,'outside'),'multibay_yes':anybranch(r,'multibay'),'vehicle_count':len(r['vehicles'])})
status='V2_3_PILOT_PASS_READY_FULL_DEV' if passed else 'V2_3_PILOT_FAIL';dec={'FINAL_STATUS':status,'READY_FOR_FULL_DEV':passed,'FULL_DEV_EXECUTED':False,'VAL_EXECUTED':False,'HOLDOUT_EXECUTED':False,'ACTIVE_CHAMPION_CHANGED':False};(OUT/'decision.json').write_text(json.dumps(dec,indent=2)+'\n')
(V/'06_reports/HANDOFF_STATUS.md').write_text(f'v2_2_status=DEV_GATE_FAIL\nv2_2_closed=true\nv2_3_status={"PASS" if passed else "FAIL"}\nACTIVE_CHAMPION_UNCHANGED=true\nNEW_CHALLENGE_IMAGES_AVAILABLE=0\n')
(OUT/'PILOT_REPORT.md').write_text(f'''# V2.3 decomposed relation pilot\n\nFINAL_STATUS={status}\n\nPrimary 60: TP={tp} FP={fp} TN={tn} FN={fn}; Precision={precision:.6f}, Recall={recall:.6f}, F1={f1:.6f}, FPR={fpr:.6f}.\nP01 recall={p01['rate']:.6f}; P03 recall={p03['rate']:.6f}; minor-crossing FPR={minor['rate']:.6f}; gate-queue FPR={gatef['rate']:.6f}.\nOutside branch recall={outrec['rate']:.6f}, FPR={outfpr['rate']:.6f}; multibay branch recall={mulrec['rate']:.6f}, FPR={mulfpr['rate']:.6f}.\nBranch combinations: {dict(conf)}.\nV2.2 R1 on the identical primary subset: TP={r1tp} FP={r1fp} TN={r1tn} FN={r1fn}, recall={r1tp/30:.6f}, FPR={r1fp/30:.6f}.\nProtocol success={protocol:.6f}; independent errors={len(errors)}.\n\nNo full DEV, VAL, or HOLDOUT was executed. No prompt revision is authorized after this one-shot pilot.\n''')
print(json.dumps({'decision':dec,'metrics':metrics,'errors':errors},indent=2))
