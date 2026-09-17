#!/usr/bin/env python3
import csv,hashlib,json,platform,random,sys,time
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from torch import nn
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from common import ROOT,P3,VAULT,rows,write_csv,write_json,sha256_file
SEED=20260916
class TinyMILCNNV1(nn.Module):
 def __init__(self):
  super().__init__();self.encoder=nn.Sequential(nn.Conv2d(4,8,5,stride=2,padding=2),nn.ReLU(),nn.Conv2d(8,16,3,stride=2,padding=1),nn.ReLU(),nn.Conv2d(16,16,3,stride=2,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d((1,1)),nn.Flatten(),nn.Linear(16,1))
 def forward(self,x):return self.encoder(x).squeeze(1)
def seed_all(s):
 random.seed(s);np.random.seed(s);torch.manual_seed(s);torch.use_deterministic_algorithms(True);torch.set_num_threads(1)
def train_predict(train_ids,predict_ids,seed,manifest,tensors,model_path):
 seed_all(seed);model=TinyMILCNNV1().cpu();opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
 pos=sum(int(manifest[m]['label_binary']) for m in train_ids);neg=len(train_ids)-pos;pw=neg/pos;lossfn=nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pw],dtype=torch.float32));rng=random.Random(seed);final_loss=None;t0=time.time()
 for epoch in range(100):
  order=list(train_ids);rng.shuffle(order);total=0.;n=0;model.train()
  for i in range(0,len(order),8):
   mids=order[i:i+8];logits=[torch.max(model(tensors[m])) for m in mids];y=torch.tensor([float(manifest[m]['label_binary']) for m in mids],dtype=torch.float32);loss=lossfn(torch.stack(logits),y);opt.zero_grad();loss.backward();opt.step();total+=float(loss.item())*len(mids);n+=len(mids)
  final_loss=total/n
 model.eval();pred={}
 with torch.no_grad():
  for m in predict_ids:pred[m]=float(torch.sigmoid(torch.max(model(tensors[m]))).item())
 torch.save(model.state_dict(),model_path)
 return pred,{'seed':seed,'train_frames':len(train_ids),'train_positive':pos,'train_negative':neg,'pos_weight':pw,'epochs':100,'final_loss':final_loss,'seconds':time.time()-t0,'model_path_local':str(model_path.relative_to(ROOT)),'model_sha256':sha256_file(model_path)}
manifest={r['media_id']:r for r in rows(P3/'01_dataset/p3_primary_manifest.csv')};folds={r['media_id']:int(r['fold']) for r in rows(P3/'05_oof/oof_folds.csv')};features={r['media_id']:r for r in rows(ROOT/'03_qwen/qwen_features_frozen.csv')};assert len(manifest)==len(folds)==len(features)==166 and set(manifest)==set(folds)==set(features) and set(folds.values())==set(range(5))
art=rows(ROOT/'02_p3_artifact/artifact_manifest.csv');by=defaultdict(list)
for r in art:by[r['media_id']].append(r)
assert len(art)==213 and set(by)==set(manifest)
tensors={}
for mid in sorted(by):
 xs=sorted(by[mid],key=lambda r:int(r['selected_rank']));ts=[]
 for r in xs:
  p=VAULT/r['artifact_filename'];assert sha256_file(p)==r['artifact_sha256']==r['expected_sha256'];a=np.load(p,allow_pickle=False);assert a.shape==(4,96,96) and a.dtype==np.float32 and np.isfinite(a).all();ts.append(torch.from_numpy(a.copy()).float())
 tensors[mid]=torch.stack(ts)
inner_assign=[];inner_scores=[];outer_scores=[];p4_scores=[];coefs=[];training=[]
for outer in range(5):
 outer_train=sorted(m for m in manifest if folds[m]!=outer);outer_val=sorted(m for m in manifest if folds[m]==outer);y=np.array([int(manifest[m]['label_binary']) for m in outer_train]);skf=StratifiedKFold(n_splits=4,shuffle=True,random_state=SEED+outer);inner_prob={}
 for inner,(tr_idx,va_idx) in enumerate(skf.split(np.zeros(len(y)),y)):
  tr=[outer_train[i] for i in tr_idx];va=[outer_train[i] for i in va_idx];model_path=ROOT/'_local_models'/f'outer_{outer}_inner_{inner}.pt';pred,info=train_predict(tr,va,SEED+outer*100+inner,tr and manifest,tensors,model_path);info.update({'role':'inner','outer_fold':outer,'inner_fold':inner});training.append(info)
  for m in va:inner_prob[m]=pred[m];inner_assign.append({'outer_fold':outer,'media_id':m,'inner_fold':inner,'label_binary':manifest[m]['label_binary']});inner_scores.append({'outer_fold':outer,'media_id':m,'inner_fold':inner,'inner_oof_p3_probability':pred[m]})
 assert len(inner_prob)==len(outer_train)
 outer_model=ROOT/'_local_models'/f'outer_{outer}_full.pt';oval,info=train_predict(outer_train,outer_val,SEED+outer,manifest,tensors,outer_model);info.update({'role':'outer_full','outer_fold':outer,'inner_fold':None});training.append(info)
 Xtr=np.array([[inner_prob[m],float(features[m]['qwen_frame_positive']),float(features[m]['qwen_candidate_fraction'])] for m in outer_train],dtype=np.float64);ytr=np.array([int(manifest[m]['label_binary']) for m in outer_train]);scaler=StandardScaler();Z=scaler.fit_transform(Xtr);meta=LogisticRegression(penalty='l2',C=1.0,solver='liblinear',class_weight='balanced',max_iter=1000,random_state=SEED+outer);meta.fit(Z,ytr)
 Xv=np.array([[oval[m],float(features[m]['qwen_frame_positive']),float(features[m]['qwen_candidate_fraction'])] for m in outer_val],dtype=np.float64);pv=meta.predict_proba(scaler.transform(Xv))[:,1]
 coefs.append({'outer_fold':outer,'coef_p3':meta.coef_[0,0],'coef_qwen_positive':meta.coef_[0,1],'coef_qwen_candidate_fraction':meta.coef_[0,2],'intercept':meta.intercept_[0],'scaler_mean_p3':scaler.mean_[0],'scaler_mean_qwen_positive':scaler.mean_[1],'scaler_mean_qwen_candidate_fraction':scaler.mean_[2],'scaler_scale_p3':scaler.scale_[0],'scaler_scale_qwen_positive':scaler.scale_[1],'scaler_scale_qwen_candidate_fraction':scaler.scale_[2]})
 for m,p in zip(outer_val,pv):outer_scores.append({'media_id':m,'outer_fold':outer,'outer_validation_p3_probability':oval[m]});p4_scores.append({'media_id':m,'outer_fold':outer,'p3_probability':oval[m],'qwen_frame_positive':features[m]['qwen_frame_positive'],'qwen_candidate_fraction':features[m]['qwen_candidate_fraction'],'p4_hybrid_probability':float(p)})
 print(f'outer fold {outer+1}/5 complete',flush=True)
assert len(p4_scores)==166 and len({r['media_id'] for r in p4_scores})==166
inner_assign.sort(key=lambda r:(r['outer_fold'],r['media_id']));inner_scores.sort(key=lambda r:(r['outer_fold'],r['media_id']));outer_scores.sort(key=lambda r:r['media_id']);p4_scores.sort(key=lambda r:r['media_id'])
write_csv(ROOT/'04_nested_oof/inner_fold_manifest.csv',inner_assign,['outer_fold','media_id','inner_fold','label_binary'])
write_csv(ROOT/'04_nested_oof/inner_oof_scores.csv',inner_scores,['outer_fold','media_id','inner_fold','inner_oof_p3_probability'])
write_csv(ROOT/'04_nested_oof/outer_base_scores.csv',outer_scores,['media_id','outer_fold','outer_validation_p3_probability'])
score_path=ROOT/'04_nested_oof/p4_oof_scores.csv';write_csv(score_path,p4_scores,['media_id','outer_fold','p3_probability','qwen_frame_positive','qwen_candidate_fraction','p4_hybrid_probability']);score_sha=sha256_file(score_path);(ROOT/'04_nested_oof/p4_oof_scores.csv.sha256').write_text(score_sha+'  p4_oof_scores.csv\n')
write_csv(ROOT/'04_nested_oof/meta_coefficients.csv',coefs,list(coefs[0]))
write_csv(ROOT/'04_nested_oof/outer_folds.csv',rows(P3/'05_oof/oof_folds.csv'),['media_id','label','group_id','fold'])
write_json(ROOT/'04_nested_oof/training_manifest.json',{'architecture':'TINY_MIL_CNN_V1','device':'cpu','optimizer':'Adam','learning_rate':.001,'weight_decay':.0001,'epochs':100,'frame_batch_size':8,'loss':'BCEWithLogitsLoss','pos_weight':'training_negatives/training_positives','outer_n_splits':5,'inner_n_splits':4,'inner_split_seed':'20260916 + outer_fold_id','inner_model_seed':'20260916 + outer_fold_id*100 + inner_fold_id','outer_model_seed':'20260916 + outer_fold_id','augmentation':False,'early_stopping':False,'best_epoch':False,'seed_sweep':False,'p4_oof_scores_sha256':score_sha,'runs':training,'environment':{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'torch':torch.__version__}})
print(json.dumps({'p4_oof_scores_sha256':score_sha,'coverage':1.0,'inner_score_rows':len(inner_scores)},sort_keys=True))
