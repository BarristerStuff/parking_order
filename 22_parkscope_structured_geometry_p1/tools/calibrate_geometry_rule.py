#!/usr/bin/env python3
import csv,json,itertools,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def rows(p): return list(csv.DictReader(open(p,newline='')))
def b(v): return str(v).lower()=='true'
targets=rows(ROOT/'02_feature_extraction/target_features.csv'); comps=rows(ROOT/'02_feature_extraction/geometry_components.csv'); split={r['media_id']:r['partition'] for r in rows(ROOT/'01_input_audit/cal_eval_split.csv')}
bytarget={}
for c in comps: bytarget.setdefault((c['media_id'],c['selected_rank']),[]).append(c)
def angle_diff(a,bv):
 d=abs(a-bv)%180; return min(d,180-d)
def decide_target(t,cfg):
 if t['anchor_status']!='ANCHOR_VALID': return 'UNCERTAIN_ANCHOR',{}
 cs=bytarget.get((t['media_id'],t['selected_rank']),[])
 lines=[c for c in cs if float(c['elongation'])>=cfg[0] and float(c['thickness_ratio'])<=cfg[1]]
 areas=[c for c in cs if c not in lines]
 separator=[]
 for c in lines:
  # central span is geometric, margin additionally requires closeness to central ground region.
  if b(c['line_crosses_central_ground_span']) and float(c['distance_to_bottom_center_normalized'])<=cfg[3]: separator.append(c)
 bracket=False;best_bracket=0.0
 for a,z in itertools.combinations(lines,2):
  if angle_diff(float(a['orientation_deg']),float(z['orientation_deg']))>cfg[2]: continue
  sa,sz=float(a['signed_normal_offset']),float(z['signed_normal_offset'])
  if sa*sz>=0: continue
  gap=abs(sa-sz)
  if gap<=cfg[4]: bracket=True;best_bracket=max(best_bracket,1-gap/max(cfg[4],1e-9))
 best_area=max([max(float(c['overlap_with_ground_proxy']),1.0 if b(c['bottom_center_inside_area']) else 0.0) for c in areas] or [0.0])
 area_support=best_area>=cfg[5]
 if separator: dec='POSITIVE_MULTIBAY'
 elif bracket or area_support: dec='NEGATIVE_IN_BAY'
 elif cs: dec='POSITIVE_OUTSIDE'
 else: dec='UNCERTAIN_GEOMETRY'
 return dec,{'line_count':len(lines),'area_count':len(areas),'separator_score':max([1-float(c['distance_to_bottom_center_normalized'])/max(cfg[3],1e-9) for c in separator] or [0]),'best_bracket_score':best_bracket,'best_area_support':best_area,'geometry_nearby':bool(cs)}
def predict_frames(cfg,partition):
 ts=[t for t in targets if split[t['media_id']]==partition]; by={}
 for t in ts:
  d,f=decide_target(t,cfg); by.setdefault(t['media_id'],[]).append((t,d,f))
 out=[]
 for mid,vals in by.items():
  ds=[v[1] for v in vals]
  pred='positive' if any(x.startswith('POSITIVE') for x in ds) else ('uncertain' if any(x.startswith('UNCERTAIN') for x in ds) else 'negative')
  out.append({'media_id':mid,'gt':vals[0][0]['event_label'],'group_key':vals[0][0]['group_key'],'prediction':pred,'target_results':vals})
 return out
def metrics(out):
 tp=sum(x['gt']=='positive' and x['prediction']=='positive' for x in out);fp=sum(x['gt']=='negative' and x['prediction']=='positive' for x in out)
 fn=sum(x['gt']=='positive' and x['prediction']!='positive' for x in out);tn=sum(x['gt']=='negative' and x['prediction']!='positive' for x in out);u=sum(x['prediction']=='uncertain' for x in out)
 prec=tp/(tp+fp) if tp+fp else 0;rec=tp/(tp+fn) if tp+fn else 0;f1=2*prec*rec/(prec+rec) if prec+rec else 0;fpr=fp/(fp+tn) if fp+tn else 0
 return {'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':prec,'recall':rec,'f1':f1,'fpr':fpr,'uncertain_rate':u/len(out),'decision_coverage':1-u/len(out)}
vals=[[2.5,3.5,5.0],[.15,.25,.35],[15,25,35],[.15,.25,.35],[.75,1,1.25],[.3,.5,.7]]
grid=[]
for cfg in itertools.product(*vals):
 m=metrics(predict_frames(cfg,'CALIBRATION')); safe=m['precision']>=.9 and m['fpr']<=.1
 row={'line_elongation_min':cfg[0],'line_max_thickness_ratio':cfg[1],'parallel_angle_max':cfg[2],'separator_center_margin':cfg[3],'bracket_max_distance_ratio':cfg[4],'area_support_min':cfg[5],**m,'safe':safe};grid.append(row)
with open(ROOT/'03_calibration/calibration_grid.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(grid[0]),lineterminator='\n');w.writeheader();w.writerows(grid)
safe=[r for r in grid if r['safe']]
winner=None
if safe:
 winner=sorted(safe,key=lambda r:(-r['recall'],-r['f1'],r['uncertain_rate'],tuple(r[k] for k in ['line_elongation_min','line_max_thickness_ratio','parallel_angle_max','separator_center_margin','bracket_max_distance_ratio','area_support_min'])))[0]
 cfg={k:winner[k] for k in ['line_elongation_min','line_max_thickness_ratio','parallel_angle_max','separator_center_margin','bracket_max_distance_ratio','area_support_min']};raw=json.dumps(cfg,sort_keys=True,separators=(',',':')).encode();config_sha=hashlib.sha256(raw).hexdigest()
out={'calibration_gate':'PASS' if winner else 'FAIL','grid_count':len(grid),'safe_config_count':len(safe),'winner':winner,'config_sha256':config_sha if winner else None,'config_canonical_json':raw.decode() if winner else None}
(ROOT/'03_calibration/calibration_winner.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
