#!/usr/bin/env python3
import csv,json,random,hashlib,platform,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score
ROOT=Path(__file__).resolve().parents[1]
def jdump(p,o):p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def write_csv(p,rows,fields):
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def calc(rows,t):
 tp=fp=tn=fn=0;sc=0
 for r in rows:
  y=int(r['gt_binary']); pred=(float(r['frame_probability'])>=t) if r['status']=='SCORABLE' else False; sc+=r['status']=='SCORABLE'
  if y and pred:tp+=1
  elif y:fn+=1
  elif pred:fp+=1
  else:tn+=1
 p=tp/(tp+fp) if tp+fp else 0.;r=tp/(tp+fn) if tp+fn else 0.;fpr=fp/(fp+tn) if fp+tn else 0.;f1=2*p*r/(p+r) if p+r else 0.;tnr=tn/(tn+fp) if tn+fp else 0.
 return {'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':p,'recall':r,'f1':f1,'fpr':fpr,'balanced_accuracy':(r+tnr)/2,'coverage':sc/len(rows) if rows else 0.}
scores=list(csv.DictReader(open(ROOT/'05_oof/oof_scores.csv',newline=''))); man={r['media_id']:r for r in csv.DictReader(open(ROOT/'01_dataset/p3_primary_manifest.csv',newline=''))}
win=json.load(open(ROOT/'06_threshold/threshold_winner.json')); winner=win['winner']
if not winner:
 decision={'final_status':'P3_LEARNED_RELATION_HEAD_NO_SAFE_THRESHOLD','p3_oof_gate_pass':False,'ready_for_p3_sealed_eval':False,'safe_threshold_count':0}
 jdump(ROOT/'08_reports/decision.json',decision);(ROOT/'08_reports/P3_OOF_REPORT.md').write_text('# P3 OOF Report\n\nNo preregistered threshold satisfied Precision >= 0.85 and FPR <= 0.10. Sealed EVALUATION remained unopened.\n')
 print(json.dumps(decision,indent=2));sys.exit(0)
t=float(winner['threshold']);overall=calc(scores,t)
# subgroup metrics
by=defaultdict(list)
for r in scores: by[man[r['media_id']]['group_key']].append(r)
sub=[]
for g,rs in sorted(by.items()):
 m=calc(rs,t);sub.append({'group_key':g,'total':len(rs),**m})
write_csv(ROOT/'07_diagnostics/subgroup_metrics.csv',sub,['group_key','total','TP','FP','TN','FN','precision','recall','f1','fpr','balanced_accuracy','coverage'])
def group_metric(name,key):
 x=next((r for r in sub if r['group_key']==key),None);return x[name] if x else None
# cases
for fn,key in [('p01_cases.csv','p01-outside-legal-bay-clear'),('p03_cases.csv','p03-span-two-bays'),('minor_crossing_cases.csv','n02-close-to-line-but-inside'),('multi_vehicle_cases.csv','p05-multi-vehicle-at-least-one-violation')]:
 rs=[]
 for r in scores:
  if man[r['media_id']]['group_key']==key:
   rs.append({**r,'group_key':key,'winner_threshold':t,'strict_prediction':'positive' if r['status']=='SCORABLE' and float(r['frame_probability'])>=t else ('negative' if r['status']=='SCORABLE' else 'UNSCORABLE')})
 write_csv(ROOT/'07_diagnostics'/fn,rs,list(rs[0]) if rs else ['media_id'])
un=[r for r in scores if r['status']!='SCORABLE'];write_csv(ROOT/'07_diagnostics/unscorable_frames.csv',un,list(scores[0]))
# negative families
ordinary={'n01-standard-inside-bay','n02-close-to-line-but-inside','n03-diagonal-bay-correct','n04-parallel-bay-correct','n05-multiple-all-correct','n06-special-marked-space-geometry-correct'}
hard={'hn02-faded-lines-but-confirmably-inside','hn03-perspective-looks-like-crossing','hn04-large-vehicle-compliant','hn05-adjacent-vehicle-occludes-lines','hn06-shadows-cracks-curbs-mimic-lines'}
def subset(keys):return [r for r in scores if man[r['media_id']]['group_key'] in keys]
ordinary_m=calc(subset(ordinary),t); hard_m=calc(subset(hard),t)
# AUC only scorable
sc=[r for r in scores if r['status']=='SCORABLE'];ys=[int(r['gt_binary']) for r in sc];ps=[float(r['frame_probability']) for r in sc]
roc=float(roc_auc_score(ys,ps));pr=float(average_precision_score(ys,ps))
# fold stability at frozen winner threshold
fold_rows=[]
for fold in sorted({int(r['fold']) for r in scores}):
 rs=[r for r in scores if int(r['fold'])==fold];m=calc(rs,t);s=[r for r in rs if r['status']=='SCORABLE']; yy=[int(r['gt_binary']) for r in s];pp=[float(r['frame_probability']) for r in s]
 auc=float(roc_auc_score(yy,pp)) if len(set(yy))==2 else None
 fold_rows.append({'fold':fold,'positive_count':sum(int(r['gt_binary']) for r in rs),'negative_count':sum(not int(r['gt_binary']) for r in rs),'auc':auc,**m})
write_csv(ROOT/'05_oof/fold_metrics.csv',fold_rows,['fold','positive_count','negative_count','TP','FP','TN','FN','precision','recall','f1','fpr','balanced_accuracy','coverage','auc'])
# frame bootstrap fixed seed
rng=random.Random(20260916);vals={k:[] for k in ['precision','recall','f1','fpr']}
for _ in range(2000):
 rs=[scores[rng.randrange(len(scores))] for __ in range(len(scores))];m=calc(rs,t)
 for k in vals: vals[k].append(m[k])
ci={k:{'low':float(np.percentile(v,2.5)),'high':float(np.percentile(v,97.5))} for k,v in vals.items()};jdump(ROOT/'07_diagnostics/bootstrap_ci.json',{'seed':20260916,'replicates':2000,'unit':'frame','ci95':ci})
p01=group_metric('recall','p01-outside-legal-bay-clear');p03=group_metric('recall','p03-span-two-bays');p05=group_metric('recall','p05-multi-vehicle-at-least-one-violation');minor=group_metric('fpr','n02-close-to-line-but-inside')
gates={'precision':overall['precision']>=.85,'recall':overall['recall']>=.70,'f1':overall['f1']>=.75,'fpr':overall['fpr']<=.10,'p01_recall':p01>=.60,'p03_recall':p03>=.60,'minor_crossing_fpr':minor<=.10,'frame_coverage':overall['coverage']>=.95}; passed=all(gates.values())
status='P3_LEARNED_RELATION_HEAD_OOF_PASS' if passed else 'P3_LEARNED_RELATION_HEAD_OOF_FAIL'
decision={'final_status':status,'p3_oof_gate_pass':passed,'ready_for_p3_sealed_eval':passed,'winner_threshold':t,'safe_threshold_count':win['safe_threshold_count'],'metrics':overall,'roc_auc':roc,'pr_auc':pr,'p01_recall':p01,'p03_recall':p03,'p05_recall':p05,'minor_crossing_fpr':minor,'ordinary_negative_fpr':ordinary_m['fpr'],'hard_negative_fpr':hard_m['fpr'],'worst_fold_recall':min(x['recall'] for x in fold_rows),'worst_fold_fpr':max(x['fpr'] for x in fold_rows),'bootstrap_ci95':ci,'gates':gates,'sealed_evaluation_executed':False,'ollama_requests':0}
jdump(ROOT/'08_reports/decision.json',decision)
report=f'''# ParkScope Learned Relation Head P3 OOF Report

## Decision

- Final status: `{status}`
- P3 OOF gate pass: `{str(passed).lower()}`
- Ready for first sealed EVALUATION: `{str(passed).lower()}`
- Sealed EVALUATION executed: `false`

## Frozen development evidence

- Primary frames: {len(scores)} ({sum(int(r['gt_binary']) for r in scores)} positive, {sum(not int(r['gt_binary']) for r in scores)} negative)
- OOF scorable: {sum(r['status']=='SCORABLE' for r in scores)}
- OOF coverage: {overall['coverage']:.6f}
- Winner threshold: {t:.2f}
- Safe thresholds: {win['safe_threshold_count']}

## OOF metrics

- TP/FP/TN/FN: {overall['TP']}/{overall['FP']}/{overall['TN']}/{overall['FN']}
- Precision: {overall['precision']:.6f}
- Recall: {overall['recall']:.6f}
- F1: {overall['f1']:.6f}
- FPR: {overall['fpr']:.6f}
- Balanced accuracy: {overall['balanced_accuracy']:.6f}
- ROC-AUC: {roc:.6f}
- PR-AUC: {pr:.6f}

## Required subgroups

- p01 recall: {p01:.6f}
- p03 recall: {p03:.6f}
- p05 recall: {p05:.6f}
- minor-crossing FPR: {minor:.6f}
- ordinary-negative FPR: {ordinary_m['fpr']:.6f}
- hard-negative FPR: {hard_m['fpr']:.6f}

## Boundary

This is synthetic/frozen development OOF feasibility only. It is not sealed EVALUATION, VAL, HOLDOUT, real-robot, or production validation. Target probabilities have no target-level gold meaning; supervision is frame-level MIL only.
'''
(ROOT/'08_reports/P3_OOF_REPORT.md').write_text(report)
print(json.dumps(decision,indent=2))
