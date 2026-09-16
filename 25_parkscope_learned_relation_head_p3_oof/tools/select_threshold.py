#!/usr/bin/env python3
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def metrics(rows,t):
 tp=fp=tn=fn=0;sc=0
 for r in rows:
  y=int(r['gt_binary'])
  if r['status']=='SCORABLE': pred=float(r['frame_probability'])>=t;sc+=1
  else: pred=False
  if y and pred:tp+=1
  elif y and not pred:fn+=1
  elif not y and pred:fp+=1
  else:tn+=1
 prec=tp/(tp+fp) if tp+fp else 0.;rec=tp/(tp+fn) if tp+fn else 0.;fpr=fp/(fp+tn) if fp+tn else 0.;f1=2*prec*rec/(prec+rec) if prec+rec else 0.;tnr=tn/(tn+fp) if tn+fp else 0.
 return {'threshold':t,'TP':tp,'FP':fp,'TN':tn,'FN':fn,'precision':prec,'recall':rec,'f1':f1,'fpr':fpr,'balanced_accuracy':(rec+tnr)/2,'oof_frame_coverage':sc/len(rows)}
rows=list(csv.DictReader(open(ROOT/'05_oof/oof_scores.csv',newline=''))); grid=[metrics(rows,i/100) for i in range(5,100,5)]
with open(ROOT/'06_threshold/threshold_grid.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(grid[0]),lineterminator='\n');w.writeheader();w.writerows(grid)
safe=[x for x in grid if x['precision']>=.85 and x['fpr']<=.10]
winner=sorted(safe,key=lambda x:(-x['recall'],-x['f1'],-x['precision'],-x['threshold']))[0] if safe else None
out={'threshold_grid_count':19,'safe_threshold_count':len(safe),'selection_order':['recall desc','f1 desc','precision desc','threshold desc'],'winner':winner,'status':'SAFE_THRESHOLD_FOUND' if winner else 'NO_SAFE_THRESHOLD'}
(ROOT/'06_threshold/threshold_winner.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,indent=2))
