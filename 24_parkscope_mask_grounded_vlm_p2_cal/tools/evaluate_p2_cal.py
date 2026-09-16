#!/usr/bin/env python3
import csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
from test_fusion import frame_decision
ROOT=Path(__file__).resolve().parents[2]; P2=Path(__file__).resolve().parents[1]; INF=P2/'03_inference'; EV=P2/'04_evaluation'; DG=P2/'05_diagnostics'; RP=P2/'06_reports'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def div(a,b):return a/b if b else 0.0
def main():
 predfile=INF/'target_predictions_frozen.jsonl'; recorded=(INF/'target_predictions_frozen.sha256').read_text().split()[0]
 if sha(predfile)!=recorded:raise SystemExit('P2_CAL_BLOCKED_PREDICTION_FREEZE_MISMATCH')
 split=list(csv.DictReader(open(ROOT/'22_parkscope_structured_geometry_p1/01_input_audit/cal_eval_split.csv',newline=''))); cal={r['media_id'] for r in split if r['partition']=='CALIBRATION'}
 # GT is read only here, after prediction freeze.
 pilot={r['media_id']:r for r in csv.DictReader(open(ROOT/'20_v2_3_decomposed_relation/04_pilot/pilot_manifest.csv',newline='')) if r['media_id'] in cal}
 if len(pilot)!=30 or Counter(r['event_label'] for r in pilot.values())!={'positive':15,'negative':15}:raise SystemExit('P2_CAL_BLOCKED_GT_PARTITION_MISMATCH')
 targets=[json.loads(x) for x in predfile.open()]; by=defaultdict(list)
 for x in targets:by[x['media_id']].append(x)
 frames=[]
 for mid in sorted(cal):
  ds=[x['target_decision'] for x in by[mid]]; dec=frame_decision(ds); gt=pilot[mid]['event_label']
  frames.append({'media_id':mid,'group_key':pilot[mid]['group_key'],'stratum':pilot[mid]['stratum'],'gt':gt,'prediction':dec,'target_count':len(ds),'target_decisions':json.dumps(ds,separators=(',',':'))})
 with (EV/'frame_predictions.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=frames[0],lineterminator='\n');w.writeheader();w.writerows(frames)
 tp=sum(r['gt']=='positive' and r['prediction']=='positive' for r in frames);fp=sum(r['gt']=='negative' and r['prediction']=='positive' for r in frames);tn=sum(r['gt']=='negative' and r['prediction']=='negative' for r in frames);fn=15-tp
 precision=div(tp,tp+fp);recall=div(tp,15);fpr=div(fp,15);f1=div(2*precision*recall,precision+recall);unc=sum(r['prediction']=='uncertain' for r in frames);coverage=div(30-unc,30);neg_exp=div(tn,15)
 p01=[r for r in frames if r['group_key']=='p01-outside-legal-bay-clear'];p03=[r for r in frames if r['group_key']=='p03-span-two-bays'];minor=[r for r in frames if r['group_key']=='n02-close-to-line-but-inside']
 p01tp=sum(r['prediction']=='positive' for r in p01);p03tp=sum(r['prediction']=='positive' for r in p03);mfp=sum(r['prediction']=='positive' for r in minor)
 vals=['YES','NO','UNCERTAIN'];fields=['one_marked_bay','separator_through_vehicle','clearly_outside_marked_bay'];dist={k:{v:sum(x.get(k)==v for x in targets) for v in vals} for k in fields}
 td=Counter(x['target_decision'] for x in targets);valid=[x for x in targets if x['anchor_valid']];pos_t=[x for x in valid if pilot[x['media_id']]['event_label']=='positive'];neg_t=[x for x in valid if pilot[x['media_id']]['event_label']=='negative'];pos_yes=div(sum(x['one_marked_bay']=='YES' for x in pos_t),len(pos_t));neg_yes=div(sum(x['one_marked_bay']=='YES' for x in neg_t),len(neg_t));weak=(neg_yes-pos_yes)<.20
 # protocol success from ledger unique successful keys
 ledger=[json.loads(x) for x in (INF/'request_ledger.jsonl').open()];succ={(x['media_id'],str(x['selected_rank'])) for x in ledger if x.get('schema_success')};valid_count=sum(x['anchor_valid'] for x in targets);protocol=div(len(succ),valid_count)
 gates={'precision_gte_0_90':precision>=.90,'strict_recall_gte_0_70_and_tp_gte_11':recall>=.70 and tp>=11,'fpr_lte_0_10_and_fp_lte_1':fpr<=.10 and fp<=1,'p01_recall_gte_0_60_and_tp_gte_3':div(p01tp,len(p01))>=.60 and p01tp>=3,'p03_recall_gte_0_60_and_tp_gte_3':div(p03tp,len(p03))>=.60 and p03tp>=3,'minor_crossing_fpr_lte_0_10':div(mfp,len(minor))<=.10,'uncertain_rate_lte_0_30_and_count_lte_9':div(unc,30)<=.30 and unc<=9,'protocol_success_eq_1':protocol==1.0};passed=all(gates.values())
 metrics={'gt_join_after_prediction_freeze':True,'cal_total':30,'cal_positive':15,'cal_negative':15,'tp':tp,'fp':fp,'tn_explicit':tn,'fn_strict':fn,'precision':precision,'strict_recall':recall,'f1':f1,'fpr':fpr,'uncertain_count':unc,'uncertain_rate':div(unc,30),'decision_coverage':coverage,'negative_explicit_rate':neg_exp,'p01_total':len(p01),'p01_tp':p01tp,'p01_recall':div(p01tp,len(p01)),'p03_total':len(p03),'p03_tp':p03tp,'p03_recall':div(p03tp,len(p03)),'minor_crossing_total':len(minor),'minor_crossing_fp':mfp,'minor_crossing_fpr':div(mfp,len(minor)),'protocol_success':protocol,'target_counts':dict(td),'field_distributions':dist,'positive_target_one_marked_bay_yes_rate':pos_yes,'negative_target_one_marked_bay_yes_rate':neg_yes,'mask_grounded_multibay_collapse':dist['separator_through_vehicle']['YES']==0,'mask_grounded_outside_collapse':dist['clearly_outside_marked_bay']['YES']==0,'mask_grounded_inbay_discrimination_weak':weak,'gates':gates,'p2_cal_gate_pass':passed}
 dump(EV/'metrics.json',metrics);dump(EV/'field_distributions.json',dist)
 sub=[]
 for name,rows in [('positive_other',[r for r in frames if r['stratum']=='positive_other']),('negative_ordinary',[r for r in frames if r['stratum']=='negative_ordinary']),('negative_hard',[r for r in frames if r['stratum']=='negative_hard']),('negative_adjudicated',[r for r in frames if r['stratum']=='negative_adjudicated'])]:
  sub.append({'subgroup':name,'count':len(rows),'positive_predictions':sum(r['prediction']=='positive' for r in rows),'negative_predictions':sum(r['prediction']=='negative' for r in rows),'uncertain_predictions':sum(r['prediction']=='uncertain' for r in rows),'recall_if_positive':div(sum(r['prediction']=='positive' for r in rows),len(rows)) if name=='positive_other' else '', 'fpr_if_negative':div(sum(r['prediction']=='positive' for r in rows),len(rows)) if name!='positive_other' else ''})
 with (EV/'subgroup_metrics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=sub[0],lineterminator='\n');w.writeheader();w.writerows(sub)
 def write_diag(path,rows,extra=None):
  fields=list(frames[0]);
  with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
 write_diag(DG/'p01_cases.csv',p01);write_diag(DG/'p03_cases.csv',p03);write_diag(DG/'minor_crossing_cases.csv',minor)
 conflicts=[x for x in targets if x['target_decision']=='UNCERTAIN_CONFLICT']; invalid=[x for x in targets if x['target_decision']=='UNCERTAIN_ANCHOR']
 for path,rows in [(DG/'conflicts.csv',conflicts),(DG/'invalid_anchors.csv',invalid)]:
  fields=['media_id','selected_rank','anchor_valid','one_marked_bay','separator_through_vehicle','clearly_outside_marked_bay','target_decision']
  with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(({k:r.get(k) for k in fields} for r in rows))
 final='PARKSCOPE_MASK_GROUNDED_VLM_P2_CAL_PASS' if passed else 'PARKSCOPE_MASK_GROUNDED_VLM_P2_CAL_FAIL'
 decision={'final_status':final,'p2_cal_gate_pass':passed,'ready_for_p2_eval':passed,'current_development_winner':'NONE','evaluation_executed':False,'gate_secondary_executed':False,'full_dev_executed':False,'val_executed':False,'holdout_executed':False,'metrics':metrics}
 dump(RP/'decision.json',decision)
 report=f'''# ParkScope Mask-Grounded VLM P2 CAL Report\n\n## Boundary\n\nCALIBRATION only: 30 images, 42 frozen selected targets. EVALUATION and GATE_SECONDARY remained sealed. ParkScope inference was not rerun.\n\n## Result\n\n- FINAL_STATUS: `{final}`\n- TP / FP / TN explicit / FN strict: `{tp} / {fp} / {tn} / {fn}`\n- Precision: `{precision:.6f}`\n- Strict recall: `{recall:.6f}`\n- F1: `{f1:.6f}`\n- FPR: `{fpr:.6f}`\n- Uncertain: `{unc}/30` (`{div(unc,30):.6f}`)\n- Decision coverage: `{coverage:.6f}`\n- P01 recall: `{p01tp}/{len(p01)} = {div(p01tp,len(p01)):.6f}`\n- P03 recall: `{p03tp}/{len(p03)} = {div(p03tp,len(p03)):.6f}`\n- Minor-crossing FPR: `{mfp}/{len(minor)} = {div(mfp,len(minor)):.6f}`\n- Protocol success: `{protocol:.6f}`\n\n## Gate\n\n```json\n{json.dumps(gates,indent=2,sort_keys=True)}\n```\n\n## Diagnostics\n\n- Field distributions: `{json.dumps(dist,sort_keys=True)}`\n- Target decisions: `{json.dumps(dict(td),sort_keys=True)}`\n- MULTIBAY_COLLAPSE: `{str(metrics['mask_grounded_multibay_collapse']).lower()}`\n- OUTSIDE_COLLAPSE: `{str(metrics['mask_grounded_outside_collapse']).lower()}`\n- INBAY_DISCRIMINATION_WEAK: `{str(weak).lower()}`\n\nThe in-bay diagnostic threshold was preregistered because the source instruction described this flag qualitatively; it does not affect the CAL gate.\n'''
 (RP/'P2_CAL_REPORT.md').write_text(report)
 print(json.dumps(decision,indent=2,sort_keys=True))
if __name__=='__main__':main()
