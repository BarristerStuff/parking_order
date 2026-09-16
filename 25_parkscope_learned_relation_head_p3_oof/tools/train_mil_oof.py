#!/usr/bin/env python3
import csv,json,hashlib,random,platform,sys,time
from pathlib import Path
from collections import defaultdict
import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1]
RASTER=ROOT/'_local_rasters'; MODELS=ROOT/'_local_fold_models'
SEED=20260916

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jdump(p,o):p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def write_csv(p,rows,fields):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def seed_all(s):
 random.seed(s);np.random.seed(s);torch.manual_seed(s)
 try: torch.use_deterministic_algorithms(True)
 except Exception: pass
 torch.set_num_threads(1)
class TinyMILCNNV1(nn.Module):
 def __init__(self):
  super().__init__();self.encoder=nn.Sequential(nn.Conv2d(4,8,5,2,2),nn.ReLU(),nn.Conv2d(8,16,3,2,1),nn.ReLU(),nn.Conv2d(16,16,3,2,1),nn.ReLU(),nn.AdaptiveAvgPool2d((1,1)),nn.Flatten(),nn.Linear(16,1))
 def forward(self,x): return self.encoder(x).squeeze(1)

def load_frames():
 manifest={r['media_id']:r for r in csv.DictReader(open(ROOT/'01_dataset/p3_primary_manifest.csv',newline=''))}
 folds={r['media_id']:int(r['fold']) for r in csv.DictReader(open(ROOT/'05_oof/oof_folds.csv',newline=''))}
 rr=list(csv.DictReader(open(ROOT/'04_relation_rasters/raster_manifest.csv',newline=''))); by=defaultdict(list)
 for r in rr:
  if r['status']=='VALID_TARGET': by[r['media_id']].append(r)
 for xs in by.values(): xs.sort(key=lambda r:int(r['selected_rank']))
 return manifest,folds,by

def tensors_for(mid,by):
 return [torch.from_numpy(np.load(ROOT/r['raster_relpath'],allow_pickle=False)).float() for r in by.get(mid,[])]
def frame_logit(model,ts):
 logits=model(torch.stack(ts)); return torch.max(logits)

def main():
 seed_all(SEED); MODELS.mkdir(exist_ok=True)
 manifest,folds,by=load_frames(); nfold=max(folds.values())+1; scores=[]; models=[]; training=[]
 for fold in range(nfold):
  s=SEED+fold;seed_all(s);model=TinyMILCNNV1().cpu();opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
  train_ids=sorted([m for m in manifest if folds[m]!=fold and by.get(m)]); val_ids=sorted([m for m in manifest if folds[m]==fold])
  pos=sum(int(manifest[m]['label_binary']) for m in train_ids);neg=len(train_ids)-pos;pw=neg/pos
  lossfn=nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pw],dtype=torch.float32)); rng=random.Random(s); final_loss=None; t0=time.time()
  for epoch in range(100):
   order=train_ids[:];rng.shuffle(order); epoch_sum=0.;epoch_n=0
   model.train()
   for i in range(0,len(order),8):
    mids=order[i:i+8]; logits=[];labels=[]
    for mid in mids:
     logits.append(frame_logit(model,tensors_for(mid,by)));labels.append(float(manifest[mid]['label_binary']))
    lv=torch.stack(logits); y=torch.tensor(labels,dtype=torch.float32);loss=lossfn(lv,y)
    opt.zero_grad();loss.backward();opt.step();epoch_sum+=float(loss.item())*len(mids);epoch_n+=len(mids)
   final_loss=epoch_sum/max(epoch_n,1)
  model_path=MODELS/f'fold_{fold}.pt';torch.save(model.state_dict(),model_path)
  models.append({'fold':fold,'model_path_local':str(model_path.relative_to(ROOT)),'model_sha256':sha(model_path),'training_seed':s,'epoch_count':100,'training_loss_final':final_loss,'train_scorable_frames':len(train_ids),'train_unscorable_frames':sum(folds[m]!=fold and not by.get(m) for m in manifest),'pos_weight':pw})
  model.eval()
  with torch.no_grad():
   for mid in val_ids:
    ts=tensors_for(mid,by)
    if not ts:
     scores.append({'media_id':mid,'fold':fold,'gt':manifest[mid]['label'],'gt_binary':manifest[mid]['label_binary'],'frame_logit':'','frame_probability':'','valid_target_count':0,'status':'UNSCORABLE','target_probabilities':'[]'});continue
    tlog=model(torch.stack(ts)); flog=torch.max(tlog); probs=torch.sigmoid(tlog).cpu().numpy().tolist()
    scores.append({'media_id':mid,'fold':fold,'gt':manifest[mid]['label'],'gt_binary':manifest[mid]['label_binary'],'frame_logit':float(flog.item()),'frame_probability':float(torch.sigmoid(flog).item()),'valid_target_count':len(ts),'status':'SCORABLE','target_probabilities':json.dumps([{'selected_rank':int(r['selected_rank']),'target_probability':float(p)} for r,p in zip(by[mid],probs)],separators=(',',':'))})
  training.append({'fold':fold,'seconds':time.time()-t0,'final_loss':final_loss,'train_positive':pos,'train_negative':neg,'validation_frames':len(val_ids)})
  print(f'fold {fold+1}/{nfold} complete loss={final_loss:.6f}',flush=True)
 scores.sort(key=lambda x:x['media_id']); assert len(scores)==len(manifest) and len({x['media_id'] for x in scores})==len(manifest)
 write_csv(ROOT/'05_oof/oof_scores.csv',scores,['media_id','fold','gt','gt_binary','frame_logit','frame_probability','valid_target_count','status','target_probabilities'])
 (ROOT/'05_oof/oof_scores.csv.sha256').write_text(sha(ROOT/'05_oof/oof_scores.csv')+'  oof_scores.csv\n')
 jdump(ROOT/'05_oof/fold_model_manifest.json',{'architecture':'TINY_MIL_CNN_V1','models':models})
 jdump(ROOT/'05_oof/training_summary.json',{'global_seed':SEED,'folds':training,'python_version':platform.python_version(),'torch_version':torch.__version__,'numpy_version':np.__version__,'device':'cpu','deterministic_algorithms':True,'model_parameter_count':sum(p.numel() for p in TinyMILCNNV1().parameters()),'oof_score_sha256':sha(ROOT/'05_oof/oof_scores.csv')})
 print(json.dumps({'scores':len(scores),'scorable':sum(x['status']=='SCORABLE' for x in scores),'unscorable':sum(x['status']!='SCORABLE' for x in scores),'sha':sha(ROOT/'05_oof/oof_scores.csv')},indent=2))
if __name__=='__main__':main()
