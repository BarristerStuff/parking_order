import csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
P3=REPO/'25_parkscope_learned_relation_head_p3_oof'
PIPE=REPO/'19_v2_2_marked_bay_required/05_dev_r1/pipeline_snapshot'
VAULT=Path('/home/yanbo/net_vlm_frozen_artifacts/parking_order/p3_relation_rasters_v1')
BASELINE='5e0a1b241b1e2ca7091ef3afccc9c64e86f34c94'
TARGET_SHA='8cf9fe036594d5f57eafba05a794d719036973438c5ec8925f1c2681830419a3'
GT_SHA='413d0226b0eb8c13f388f3adb051844b0fe6d30b1b06ebc833b614beaffd1e56'
Q1_SHA='12c64bbf69915ac181a91adda39a8bd95ec26528d44f978e1eca6ad475a1cc9e'
Q3_SHA='5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc'
def sha256_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def rows(path):
 with Path(path).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write_csv(path,data,fields):
 Path(path).parent.mkdir(parents=True,exist_ok=True)
 with Path(path).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data)
def write_json(path,obj): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
