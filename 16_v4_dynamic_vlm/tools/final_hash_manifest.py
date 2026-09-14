#!/usr/bin/env python3
import hashlib,json,pathlib
root=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm'); out=root/'contracts/final_hash_manifest.json'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
files=[]
for p in sorted(root.rglob('*')):
 if not p.is_file() or p==out or '__pycache__' in p.parts: continue
 files.append({'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size})
manifest={'status':'FINAL_FROZEN_HASHES','hash_manifest_excludes_itself':True,'file_count':len(files),'files':files}
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':manifest['status'],'file_count':len(files),'manifest_path':str(out)},indent=2))
