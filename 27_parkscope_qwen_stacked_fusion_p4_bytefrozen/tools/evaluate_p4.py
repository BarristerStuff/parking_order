#!/usr/bin/env python3
import json,math
from collections import defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score
from common import ROOT,P3,rows,write_csv,write_json,sha256_file
score_path=ROOT/'04_nested_oof/p4_oof_scores.csv';side=(ROOT/'04_nested_oof/p4_oof_scores.csv.sha256').read_text().split()[0];assert sha256_file(score_path)==side
scores=rows(score_path);man={r['media_id']:r for r in rows(P3/'01_dataset/p3_primary_manifest.csv')};feat={r['media_id']:r for r in rows(ROOT/'03_qwen/qwen_features_frozen.csv')};base={r['media_id']:r for r in rows(ROOT/'04_nested_oof/outer_base_scores.csv')};assert len(scores)==len(man)==len(feat)==len(base)==166 and set(man)==set(r['media_id'] for r in scores)==set(feat)==set(base)
def metric(rs,t,prob='p4_hybrid_probability'):
 tp=fp=tn=fn=0
 for r in rs:
  y=int(man[r['media_id']]['label_binary']);p=float(r[prob])>=t
  if y and p:tp+=1
  elif y:fn+=1
  elif p:fp+=1
  else:tn+=1
 prec=tp/(tp+fp) if tp+fp else 0.;rec=tp/(tp+fn) if tp+fn else 0.;fpr=fp/(fp+tn) if fp+tn else 0.;f1=2*prec*rec/(prec+rec) if prec+rec else 0.
 return {'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':prec,'recall':rec,'f1':f1,'fpr':fpr,'coverage':1.0}
def group_rows(keys):return [r for r in scores if man[r['media_id']]['group_key'] in keys]
def qmetric(rs):
 tp=fp=tn=fn=0
 for r in rs:
  y=int(man[r['media_id']]['label_binary']);p=float(feat[r['media_id']]['qwen_frame_positive'])==1.0
  if y and p:tp+=1
  elif y:fn+=1
  elif p:fp+=1
  else:tn+=1
 prec=tp/(tp+fp) if tp+fp else 0.;rec=tp/(tp+fn) if tp+fn else 0.;fpr=fp/(fp+tn) if fp+tn else 0.;f1=2*prec*rec/(prec+rec) if prec+rec else 0.
 return {'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':prec,'recall':rec,'f1':f1,'fpr':fpr}
ordinary={'n01-standard-inside-bay','n02-close-to-line-but-inside','n03-diagonal-bay-correct','n04-parallel-bay-correct','n05-multiple-all-correct','n06-special-marked-space-geometry-correct'}
hard={'hn02-faded-lines-but-confirmably-inside','hn03-perspective-looks-like-crossing','hn04-large-vehicle-compliant','hn05-adjacent-vehicle-occludes-lines','hn06-shadows-cracks-curbs-mimic-lines'}
qbase=qmetric(scores);qbase.update({'p01_recall':qmetric(group_rows({'p01-outside-legal-bay-clear'}))['recall'],'p03_recall':qmetric(group_rows({'p03-span-two-bays'}))['recall'],'minor_crossing_fpr':qmetric(group_rows({'n02-close-to-line-but-inside'}))['fpr'],'gt_join_after_qwen_feature_freeze':True,'qwen_feature_sha256':sha256_file(ROOT/'03_qwen/qwen_features_frozen.csv')});write_json(ROOT/'03_qwen/qwen_baseline_metrics.json',qbase)
grid=[]
for i in range(1,20):
 t=i*.05;m=metric(scores,t);grid.append({'threshold':f'{t:.2f}',**m,'safe':m['precision']>=.85 and m['fpr']<=.10})
write_csv(ROOT/'05_threshold/threshold_grid.csv',grid,['threshold','TP','FP','TN','FN','precision','recall','f1','fpr','coverage','safe'])
safe=[r for r in grid if r['safe']];winner=max(safe,key=lambda r:(r['recall'],r['f1'],r['precision'],float(r['threshold']))) if safe else None
write_json(ROOT/'05_threshold/threshold_winner.json',{'threshold_grid_count':19,'safe_threshold_count':len(safe),'selection_order':['recall_desc','f1_desc','precision_desc','threshold_desc'],'winner':winner})
ys=np.array([int(man[r['media_id']]['label_binary']) for r in scores]);ps=np.array([float(r['p4_hybrid_probability']) for r in scores]);roc=float(roc_auc_score(ys,ps));pr=float(average_precision_score(ys,ps))
def dist(vals):
 if not vals:return {'count':0,'min':None,'p25':None,'median':None,'p75':None,'max':None}
 return {'count':len(vals),'min':min(vals),'p25':float(np.percentile(vals,25)),'median':float(np.percentile(vals,50)),'p75':float(np.percentile(vals,75)),'max':max(vals)}
overlap=[];tpvals=[];fpvals=[]
for r in scores:
 mid=r['media_id'];y=int(man[mid]['label_binary']);qp=int(float(feat[mid]['qwen_frame_positive'])==1.0);p3=float(base[mid]['outer_validation_p3_probability']);kind='TP' if y and qp else ('FP' if (not y) and qp else ('FN' if y else 'TN'))
 if kind=='TP':tpvals.append(p3)
 if kind=='FP':fpvals.append(p3)
 overlap.append({'media_id':mid,'label_binary':y,'group_key':man[mid]['group_key'],'qwen_frame_positive':qp,'qwen_outcome':kind,'p3_probability':p3,'qwen_candidate_fraction':feat[mid]['qwen_candidate_fraction'],'p4_hybrid_probability':r['p4_hybrid_probability']})
write_csv(ROOT/'06_diagnostics/qwen_p3_error_overlap.csv',overlap,list(overlap[0]));write_json(ROOT/'06_diagnostics/qwen_tp_p3_score_distribution.json',dist(tpvals));write_json(ROOT/'06_diagnostics/qwen_fp_p3_score_distribution.json',dist(fpvals))
coefs=rows(ROOT/'04_nested_oof/meta_coefficients.csv');p3_unused=all(abs(float(r['coef_p3']))<.05 for r in coefs);q_unused=all(abs(float(r['coef_qwen_positive']))<.05 and abs(float(r['coef_qwen_candidate_fraction']))<.05 for r in coefs);write_json(ROOT/'06_diagnostics/channel_usage.json',{'p3_channel_unused':p3_unused,'qwen_channel_unused':q_unused,'criterion':'all outer folds standardized abs(coef) < 0.05'})
case_specs=[('p01_cases.csv',{'p01-outside-legal-bay-clear'}),('p03_cases.csv',{'p03-span-two-bays'}),('p05_cases.csv',{'p05-multi-vehicle-at-least-one-violation'}),('minor_crossing_cases.csv',{'n02-close-to-line-but-inside'})]
sub=[]
for key in sorted({r['group_key'] for r in man.values()}):
 rs=group_rows({key});m=metric(rs,float(winner['threshold'])) if winner else None;sub.append({'group_key':key,'total':len(rs),**(m or {'TP':'N/A','FP':'N/A','TN':'N/A','FN':'N/A','precision':'N/A','recall':'N/A','f1':'N/A','fpr':'N/A','coverage':1.0})})
write_csv(ROOT/'06_diagnostics/subgroup_metrics.csv',sub,list(sub[0]))
for fn,keys in case_specs:
 rs=[]
 for r in group_rows(keys):
  z={**r,'label_binary':man[r['media_id']]['label_binary'],'group_key':man[r['media_id']]['group_key'],'winner_threshold':winner['threshold'] if winner else '','strict_prediction':('positive' if float(r['p4_hybrid_probability'])>=float(winner['threshold']) else 'negative') if winner else 'N/A_NO_SAFE_THRESHOLD'};rs.append(z)
 write_csv(ROOT/'06_diagnostics'/fn,rs,list(rs[0]) if rs else ['media_id'])
fold_metrics=[]
for f in range(5):
 rs=[r for r in scores if int(r['outer_fold'])==f];fm=metric(rs,float(winner['threshold'])) if winner else None;yy=[int(man[r['media_id']]['label_binary']) for r in rs];pp=[float(r['p4_hybrid_probability']) for r in rs];fold_metrics.append({'outer_fold':f,'positive_count':sum(yy),'negative_count':len(yy)-sum(yy),'roc_auc':float(roc_auc_score(yy,pp)),**(fm or {'TP':'N/A','FP':'N/A','TN':'N/A','FN':'N/A','precision':'N/A','recall':'N/A','f1':'N/A','fpr':'N/A','coverage':1.0})})
write_csv(ROOT/'04_nested_oof/fold_metrics.csv',fold_metrics,list(fold_metrics[0]))
if not winner:
 final='P4_QWEN_STACKED_FUSION_NO_SAFE_THRESHOLD';overall=None;gates={};ready=False;p01=p03=p05=minor=ordinary_fpr=hard_fpr=None
else:
 t=float(winner['threshold']);overall=metric(scores,t);p01=metric(group_rows({'p01-outside-legal-bay-clear'}),t)['recall'];p03=metric(group_rows({'p03-span-two-bays'}),t)['recall'];p05=metric(group_rows({'p05-multi-vehicle-at-least-one-violation'}),t)['recall'];minor=metric(group_rows({'n02-close-to-line-but-inside'}),t)['fpr'];ordinary_fpr=metric(group_rows(ordinary),t)['fpr'];hard_fpr=metric(group_rows(hard),t)['fpr'];gates={'precision':overall['precision']>=.85,'recall':overall['recall']>=.70,'f1':overall['f1']>=.75,'fpr':overall['fpr']<=.10,'p01_recall':p01>=.60,'p03_recall':p03>=.60,'minor_crossing_fpr':minor<=.10,'oof_coverage':overall['coverage']==1.0};passed=all(gates.values());final='P4_QWEN_STACKED_FUSION_OOF_PASS' if passed else 'P4_QWEN_STACKED_FUSION_OOF_FAIL';ready=passed
decision={'final_status':final,'ready_for_new_independent_eval_design':ready,'current_development_winner':'NONE','safe_threshold_count':len(safe),'winner_threshold':float(winner['threshold']) if winner else None,'metrics':overall,'roc_auc':roc,'pr_auc':pr,'p01_recall':p01,'p03_recall':p03,'p05_recall':p05,'minor_crossing_fpr':minor,'ordinary_negative_fpr':ordinary_fpr,'hard_negative_fpr':hard_fpr,'gates':gates,'p4_oof_scores_sha256':side,'qwen_feature_sha256':sha256_file(ROOT/'03_qwen/qwen_features_frozen.csv'),'p3_channel_unused':p3_unused,'qwen_channel_unused':q_unused,'new_independent_eval_executed':False,'val_executed':False,'holdout_executed':False,'old_holdout_rerun':False,'real_robot_validated':False,'production_ready':False};write_json(ROOT/'07_reports/decision.json',decision)
report=f'''# Byte-Frozen P3 Raster + Qwen Stacked P4 OOF Report\n\n## Decision\n\n- Final status: `{final}`\n- Safe threshold count: `{len(safe)}`\n- Winner threshold: `{winner['threshold'] if winner else 'N/A'}`\n- Ready for new independent evaluation design: `{str(ready).lower()}`\n- Current development winner: `NONE`\n\n## Frozen development evidence\n\n- Frames: 166 (47 positive, 119 negative)\n- OOF coverage: 1.000000\n- P4 OOF score SHA256: `{side}`\n- ROC-AUC: {roc:.6f}\n- PR-AUC: {pr:.6f}\n- Metrics: `{json.dumps(overall,sort_keys=True) if overall else 'N/A_NO_SAFE_THRESHOLD'}`\n- P01 recall: `{p01}`\n- P03 recall: `{p03}`\n- P05 recall: `{p05}`\n- Minor-crossing FPR: `{minor}`\n\n## Boundary\n\nThis is frozen development nested OOF evidence only. No independent EVAL, legacy quarantined evaluation, VAL, HOLDOUT, real-robot validation, or production integration was executed.\n''';(ROOT/'07_reports/P4_OOF_REPORT.md').write_text(report)
print(json.dumps(decision,indent=2,sort_keys=True))
