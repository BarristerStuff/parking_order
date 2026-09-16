#!/usr/bin/env python3
from __future__ import annotations
import csv, json, itertools, hashlib, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parent
P1=REPO/'22_parkscope_structured_geometry_p1'
sys.path.insert(0,str(ROOT/'02_rule'))
from conservative_geometry_rule import decide_target, derive_evidence, fuse_frame
PARAMS=['line_elongation_min','line_max_thickness_ratio','parallel_angle_max','separator_center_margin','bracket_max_distance_ratio','area_support_min']
VALUES=[[2.5,3.5,5.0],[.15,.25,.35],[15,25,35],[.15,.25,.35],[.75,1.0,1.25],[.3,.5,.7]]
def readcsv(p): return list(csv.DictReader(open(p,newline='')))
def writecsv(p,rs,fields=None):
 fields=fields or (list(rs[0]) if rs else [])
 with open(p,'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rs)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical_sha(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
split_rows=readcsv(P1/'01_input_audit/cal_eval_split.csv'); split={r['media_id']:r['partition'] for r in split_rows}
assert sha(P1/'01_input_audit/cal_eval_split.csv')=='bf8d5ba02dc0a2c5a0f1384ca0dfacd9afe3dcdbd440c7775b9cdd943d68b332'
targets=readcsv(P1/'02_feature_extraction/target_features.csv'); comps=readcsv(P1/'02_feature_extraction/geometry_components.csv')
bytarget=defaultdict(list)
for c in comps: bytarget[(c['media_id'],c['selected_rank'])].append(c)
byframe=defaultdict(list)
for t in targets: byframe[t['media_id']].append(t)

def partition_frames(partition):
 # Governance: GT fields are only accessed for the requested partition.
 out=[]
 for mid in sorted(m for m,p in split.items() if p==partition):
  ts=byframe[mid]
  out.append((mid,ts[0]['event_label'],ts[0]['group_key'],ts))
 return out
CAL=partition_frames('CALIBRATION')
assert len(CAL)==30 and Counter(x[1] for x in CAL)=={'positive':15,'negative':15}

def old_target(t,cfg):
 cs=bytarget[(t['media_id'],t['selected_rank'])]
 if t['anchor_status']!='ANCHOR_VALID': return 'UNCERTAIN_ANCHOR','OTHER',{}
 ev=derive_evidence(cs,cfg)
 if ev['strong_separator']: return 'POSITIVE_MULTIBAY','SEPARATOR_POSITIVE',ev
 if ev['strong_in_bay']: return 'NEGATIVE_IN_BAY','OTHER',ev
 if cs: return 'POSITIVE_OUTSIDE','OUTSIDE_FALLBACK_POSITIVE',ev
 return 'UNCERTAIN_GEOMETRY','OTHER',ev

def config_from_row(r): return {k:float(r[k]) for k in PARAMS}
# 1. Attribute the old P1 minimum-FP family without changing the old rule.
old_grid=readcsv(P1/'03_calibration/calibration_grid.csv'); min_fp=min(int(r['FP']) for r in old_grid); family=[r for r in old_grid if int(r['FP'])==min_fp]
writecsv(ROOT/'01_failure_attribution/minimum_fp_config_family.csv',family,list(old_grid[0]))
occ=[]; target_occ=[]
for ci,r in enumerate(family):
 cfg=config_from_row(r)
 for mid,gt,gk,ts in CAL:
  vals=[]
  for t in ts:
   d,tr,e=old_target(t,cfg); vals.append((t,d,tr,e))
  pred='positive' if any(v[1].startswith('POSITIVE') for v in vals) else ('uncertain' if any(v[1].startswith('UNCERTAIN') for v in vals) else 'negative')
  if gt=='negative' and pred=='positive':
   triggers={v[2] for v in vals if v[1].startswith('POSITIVE')}
   cat='BOTH' if {'SEPARATOR_POSITIVE','OUTSIDE_FALLBACK_POSITIVE'}<=triggers else ('SEPARATOR_POSITIVE' if 'SEPARATOR_POSITIVE' in triggers else ('OUTSIDE_FALLBACK_POSITIVE' if 'OUTSIDE_FALLBACK_POSITIVE' in triggers else 'OTHER'))
   occ.append({'config_family_index':ci,'media_id':mid,'group_key':gk,'frame_trigger':cat})
   for t,d,tr,e in vals:
    target_occ.append({'config_family_index':ci,'media_id':mid,'group_key':gk,'selected_rank':t['selected_rank'],'target_decision':d,'target_trigger':tr,'caused_frame_positive':d.startswith('POSITIVE'),'strong_separator':e.get('strong_separator',''),'strong_in_bay':e.get('strong_in_bay',''),'geometry_candidate_count':e.get('geometry_candidate_count','')})
writecsv(ROOT/'01_failure_attribution/cal_fp_target_attribution.csv',target_occ)
byfp=defaultdict(list)
for x in occ: byfp[x['media_id']].append(x)
attr=[]
for mid,gt,gk,ts in [x for x in CAL if x[1]=='negative']:
 xs=byfp[mid]; cats=Counter(x['frame_trigger'] for x in xs)
 attr.append({'media_id':mid,'group_key':gk,'fp_occurrence_count':len(xs),'fp_occurrence_rate':len(xs)/len(family),'outside_fallback_occurrences':cats['OUTSIDE_FALLBACK_POSITIVE']+cats['BOTH'],'separator_occurrences':cats['SEPARATOR_POSITIVE']+cats['BOTH'],'both_occurrences':cats['BOTH']})
writecsv(ROOT/'01_failure_attribution/cal_fp_attribution.csv',attr)
union=sum(bool(byfp[x[0]]) for x in CAL if x[1]=='negative'); inter=sum(len(byfp[x[0]])==len(family) for x in CAL if x[1]=='negative')
summary={'old_p1_min_fp':min_fp,'old_p1_min_fpr':min_fp/15,'min_fp_config_count':len(family),'fp_frame_union_count':union,'fp_frame_intersection_count':inter,'fp_occurrence_total':len(occ),'fp_with_outside_fallback_count':sum(x['frame_trigger'] in {'OUTSIDE_FALLBACK_POSITIVE','BOTH'} for x in occ),'fp_with_separator_count':sum(x['frame_trigger'] in {'SEPARATOR_POSITIVE','BOTH'} for x in occ),'fp_with_both_count':sum(x['frame_trigger']=='BOTH' for x in occ),'count_unit_for_trigger_fields':'configuration-frame FP occurrence'}
(ROOT/'01_failure_attribution/cal_fp_attribution_summary.json').write_text(json.dumps(summary,indent=2)+'\n')

def run_partition(partition,cfg,include_details=False):
 frames=partition_frames(partition); out=[]
 for mid,gt,gk,ts in frames:
  details=[]
  for t in ts:
   cs=bytarget[(mid,t['selected_rank'])]; d,e=decide_target(t['anchor_status'],cs,cfg); details.append({'selected_rank':t['selected_rank'],'decision':d,**e})
  pred=fuse_frame([d['decision'] for d in details])
  out.append({'media_id':mid,'group_key':gk,'gt':gt,'prediction':pred,'target_details':details if include_details else None})
 return out

def metrics(out):
 tp=sum(x['gt']=='positive' and x['prediction']=='positive' for x in out); fp=sum(x['gt']=='negative' and x['prediction']=='positive' for x in out)
 tn_exp=sum(x['gt']=='negative' and x['prediction']=='negative' for x in out); fn_exp=sum(x['gt']=='positive' and x['prediction']=='negative' for x in out)
 pos=sum(x['prediction']=='positive' for x in out);neg=sum(x['prediction']=='negative' for x in out);unc=sum(x['prediction']=='uncertain' for x in out)
 p03=[x for x in out if x['group_key'].startswith('p03-')];p01=[x for x in out if x['group_key'].startswith('p01-')];minor=[x for x in out if x['group_key'].startswith('p02-') and x['gt']=='negative']
 return {'TP':tp,'FP':fp,'TN_explicit':tn_exp,'explicit_negative_on_positive_count':fn_exp,'explicit_positive_count':pos,'explicit_negative_count':neg,'uncertain_count':unc,'conditional_positive_precision':tp/(tp+fp) if tp+fp else 0.0,'explicit_negative_npv':tn_exp/neg if neg else 0.0,'strict_recall':tp/sum(x['gt']=='positive' for x in out),'decision_coverage':(pos+neg)/len(out),'uncertain_rate':unc/len(out),'p03_strict_recall':sum(x['prediction']=='positive' for x in p03)/len(p03),'p01_explicit_positive_recall':sum(x['prediction']=='positive' for x in p01)/len(p01),'minor_crossing_fp_count':sum(x['prediction']=='positive' for x in minor)}

def safe(m): return m['FP']==0 and m['explicit_negative_on_positive_count']==0 and m['conditional_positive_precision']==1.0 and m['p03_strict_recall']>=.60 and m['minor_crossing_fp_count']==0 and m['decision_coverage']>=.40
# 2. The one preregistered CAL grid.
grid=[]
for tup in itertools.product(*VALUES):
 cfg=dict(zip(PARAMS,tup)); m=metrics(run_partition('CALIBRATION',cfg)); grid.append({**cfg,**m,'safe':safe(m)})
writecsv(ROOT/'03_calibration/calibration_grid.csv',grid)
safes=[r for r in grid if r['safe']]; writecsv(ROOT/'03_calibration/calibration_safe_configs.csv',safes,list(grid[0]))
base_decision={'outside_fallback_removed':True,'outside_positive_enabled':False,'calibration_grid_count':729,'calibration_safe_config_count':len(safes),'evaluation_executed':False,'parkscope_new_requests':0,'ollama_requests':0}
if not safes:
 winner_doc={'calibration_gate':'FAIL','winner_frozen':False,'winner':None,'config_sha256':None,**base_decision}
 (ROOT/'03_calibration/calibration_winner.json').write_text(json.dumps(winner_doc,indent=2)+'\n')
 (ROOT/'06_reports/decision.json').write_text(json.dumps({'FINAL_STATUS':'PARKSCOPE_P1_1_NO_SAFE_TRIAGE_RULE','P1_1_GATE_PASS':False,'READY_FOR_FULL_DEV_GEOMETRY':False,**winner_doc},indent=2)+'\n')
 print(json.dumps(winner_doc,indent=2)); raise SystemExit(3)
# Fixed winner ordering.
def tuple_key(r): return tuple(float(r[k]) for k in PARAMS)
winner=sorted(safes,key=lambda r:(-float(r['p03_strict_recall']),-float(r['decision_coverage']),-float(r['strict_recall']),float(r['uncertain_rate']),tuple_key(r)))[0]
cfg={k:float(winner[k]) for k in PARAMS}; freeze={'rule_version':'PARKSCOPE_CONSERVATIVE_GEOMETRY_P1_1','outside_positive_enabled':False,'parameters':cfg,'calibration_metrics':{k:winner[k] for k in winner if k not in PARAMS+['safe']}}
config_sha=canonical_sha(freeze); timestamp=datetime.now(timezone(timedelta(hours=8))).isoformat()
winner_doc={'calibration_gate':'PASS','winner_frozen':True,'winner_freeze_timestamp':timestamp,'winner':freeze,'config_sha256':config_sha,**base_decision}
(ROOT/'03_calibration/calibration_winner.json').write_text(json.dumps(winner_doc,indent=2)+'\n')
# 3. Open EVAL exactly once only after winner bytes and SHA exist.
eval_out=run_partition('EVALUATION',cfg,True); em=metrics(eval_out)
predrows=[]
for x in eval_out: predrows.append({'media_id':x['media_id'],'group_key':x['group_key'],'gt':x['gt'],'prediction':x['prediction'],'target_details':json.dumps(x['target_details'],sort_keys=True,separators=(',',':'))})
writecsv(ROOT/'04_evaluation/predictions.csv',predrows)
gate=em['FP']==0 and em['explicit_negative_on_positive_count']==0 and em['conditional_positive_precision']==1.0 and em['p03_strict_recall']>=.60 and em['minor_crossing_fp_count']==0 and em['decision_coverage']>=.40 and em['uncertain_rate']<=.60
em.update({'evaluation_executed':True,'config_sha256':config_sha,'gate_checks':{'fp_zero':em['FP']==0,'explicit_negative_on_positive_zero':em['explicit_negative_on_positive_count']==0,'conditional_positive_precision_one':em['conditional_positive_precision']==1.0,'p03_recall_gte_0_60':em['p03_strict_recall']>=.60,'minor_crossing_fp_zero':em['minor_crossing_fp_count']==0,'decision_coverage_gte_0_40':em['decision_coverage']>=.40,'uncertain_rate_lte_0_60':em['uncertain_rate']<=.60},'p1_1_gate_pass':gate})
(ROOT/'04_evaluation/metrics.json').write_text(json.dumps(em,indent=2)+'\n')
sub=[]
for g in sorted({x['group_key'] for x in eval_out}):
 xs=[x for x in eval_out if x['group_key']==g]; sub.append({'group_key':g,'total':len(xs),'positive':sum(x['prediction']=='positive' for x in xs),'negative':sum(x['prediction']=='negative' for x in xs),'uncertain':sum(x['prediction']=='uncertain' for x in xs)})
writecsv(ROOT/'04_evaluation/subgroup_metrics.csv',sub)
# Diagnostics only after complete EVAL.
def diag_rows(prefix,name):
 rs=[]
 for x in eval_out:
  if x['group_key'].startswith(prefix): rs.append({'media_id':x['media_id'],'group_key':x['group_key'],'gt':x['gt'],'prediction':x['prediction'],'target_details':json.dumps(x['target_details'],sort_keys=True,separators=(',',':'))})
 writecsv(ROOT/'05_diagnostics'/name,rs,['media_id','group_key','gt','prediction','target_details'])
diag_rows('p03-','p03_diagnostics.csv');diag_rows('p01-','p01_diagnostics.csv');diag_rows('p02-','minor_crossing_diagnostics.csv')
invalid=[]
for x in eval_out:
 for d in x['target_details']:
  if d['decision']=='UNCERTAIN_ANCHOR': invalid.append({'media_id':x['media_id'],'group_key':x['group_key'],'selected_rank':d['selected_rank'],'frame_prediction':x['prediction']})
writecsv(ROOT/'05_diagnostics/anchor_invalid.csv',invalid,['media_id','group_key','selected_rank','frame_prediction'])
gate_out=run_partition('GATE_SECONDARY',cfg,True); gate_counts=Counter(x['prediction'] for x in gate_out)
writecsv(ROOT/'05_diagnostics/gate_queue_diagnostics.csv',[{'media_id':x['media_id'],'group_key':x['group_key'],'prediction':x['prediction'],'target_details':json.dumps(x['target_details'],sort_keys=True,separators=(',',':'))} for x in gate_out])
status='PARKSCOPE_P1_1_CONSERVATIVE_TRIAGE_PASS' if gate else 'PARKSCOPE_P1_1_CONSERVATIVE_TRIAGE_FAIL'
decision={'FINAL_STATUS':status,'P1_1_GATE_PASS':gate,'READY_FOR_FULL_DEV_GEOMETRY':gate,'EVALUATION_EXECUTED':True,'CALIBRATION_CONFIG_SHA':config_sha,'calibration_metrics':{k:winner[k] for k in winner if k not in PARAMS+['safe']},'evaluation_metrics':em,'gate_queue_counts':dict(gate_counts),**summary,**base_decision,'CURRENT_DEVELOPMENT_WINNER':'NONE','FULL_DEV_EXECUTED':False,'VAL_EXECUTED':False,'HOLDOUT_EXECUTED':False}
(ROOT/'06_reports/decision.json').write_text(json.dumps(decision,indent=2)+'\n')
# update seal with auditable opening event
seal=json.loads((ROOT/'00_protocol/eval_seal.json').read_text());seal.update({'winner_frozen':True,'winner_freeze_timestamp':timestamp,'calibration_config_sha256':config_sha,'eval_opened_after_winner_freeze':True,'evaluation_executed_once':True});(ROOT/'00_protocol/eval_seal.json').write_text(json.dumps(seal,indent=2)+'\n')
(ROOT/'06_reports/P1_1_REPORT.md').write_text(f'''# ParkScope Conservative Geometry P1.1\n\n## Decision\n\n`{status}`\n\nP1.1 removed the unsafe outside fallback and treats unresolved geometry as uncertain. The old P1 minimum-FP family still produced {min_fp}/15 false positives (FPR {min_fp/15:.6f}); {len(family)} configurations shared that minimum.\n\nThe preregistered 729-config CAL grid produced {len(safes)} safe configurations. The mechanically selected winner was frozen at `{config_sha}` before EVAL was opened.\n\n### CAL winner\n\n- FP: {winner['FP']}\n- Explicit negative on positive: {winner['explicit_negative_on_positive_count']}\n- Conditional positive precision: {float(winner['conditional_positive_precision']):.6f}\n- P03 strict recall: {float(winner['p03_strict_recall']):.6f}\n- Decision coverage: {float(winner['decision_coverage']):.6f}\n- Uncertain rate: {float(winner['uncertain_rate']):.6f}\n\n### Independent EVAL\n\n- TP / FP: {em['TP']} / {em['FP']}\n- Explicit negative on positive: {em['explicit_negative_on_positive_count']}\n- Conditional positive precision: {em['conditional_positive_precision']:.6f}\n- Explicit negative NPV: {em['explicit_negative_npv']:.6f}\n- Strict recall: {em['strict_recall']:.6f}\n- P03 strict recall: {em['p03_strict_recall']:.6f}\n- P01 explicit positive recall: {em['p01_explicit_positive_recall']:.6f}\n- Coverage / uncertain: {em['decision_coverage']:.6f} / {em['uncertain_rate']:.6f}\n- Minor-crossing FP: {em['minor_crossing_fp_count']}\n\nP1.1 remains a safe geometry triage frontend, not a complete classifier. No FULL DEV, VLM, VAL, or HOLDOUT execution occurred.\n''')
print(json.dumps(decision,indent=2))
