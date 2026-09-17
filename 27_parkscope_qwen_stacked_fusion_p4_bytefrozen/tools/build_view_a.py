#!/usr/bin/env python3
import hashlib, io, json
from pathlib import Path
from PIL import Image,ImageDraw
from common import ROOT,P3,rows,write_csv,write_json,sha256_file,TARGET_SHA
OUT=ROOT/'_local_view_a'; OUT.mkdir(exist_ok=True)
primary_rows=rows(P3/'01_dataset/p3_primary_manifest.csv')
primary={r['media_id']:{'image_path':r['image_path']} for r in primary_rows}
qids={r['media_id'] for r in rows(P3/'01_dataset/sealed_eval_exclusion.csv')}
targets=rows(P3/'03_target_binding/frozen_target_manifest.csv')
assert sha256_file(P3/'03_target_binding/frozen_target_manifest.csv')==TARGET_SHA
assert len(primary)==166 and len(qids)==30 and not(set(primary)&qids) and len(targets)==213

def render(raw,bbox):
 with Image.open(raw) as src:
  im=src.convert('RGB')
 scale=min(1.0,896/max(im.size))
 out=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
 ImageDraw.Draw(out).rectangle([x*scale for x in bbox],outline=(255,0,0),width=4)
 b=io.BytesIO();out.save(b,'JPEG',quality=90);return b.getvalue(),im.size,out.size
manifest=[];request=[]
for r in sorted(targets,key=lambda z:(z['media_id'],int(z['selected_rank']))):
 mid=r['media_id']; assert mid in primary and mid not in qids
 bbox=json.loads(r['bbox_xyxy']); raw=Path(primary[mid]['image_path']); assert raw.is_file()
 data,orig_size,out_size=render(raw,bbox); rank=int(r['selected_rank']); dst=OUT/f'{mid}__r{rank:02d}.jpg';dst.write_bytes(data); h=hashlib.sha256(data).hexdigest()
 base={'media_id':mid,'selected_rank':rank,'image_path':str(dst.resolve()),'bbox':json.dumps(bbox,separators=(',',':')),'view_a_sha':h}
 request.append(base)
 manifest.append({**base,'source_image_path':str(raw),'source_image_sha256':sha256_file(raw),'source_width':orig_size[0],'source_height':orig_size[1],'view_width':out_size[0],'view_height':out_size[1],'jpeg_quality':90})
write_csv(ROOT/'03_qwen/view_a_manifest.csv',manifest,list(manifest[0]))
write_csv(ROOT/'03_qwen/request_manifest.csv',request,['media_id','selected_rank','image_path','bbox','view_a_sha'])
checks=[]
for r in request[:20]:
 mid=r['media_id']; assert mid in primary and mid not in qids
 data,_,_=render(Path(primary[mid]['image_path']),json.loads(r['bbox'])); h=hashlib.sha256(data).hexdigest(); checks.append({'media_id':mid,'selected_rank':r['selected_rank'],'expected_sha256':r['view_a_sha'],'repeat_sha256':h,'match':h==r['view_a_sha']})
write_json(ROOT/'03_qwen/view_a_determinism.json',{'selection':'first_20_sorted_media_id_rank','repeat_count':20,'match_count':sum(x['match'] for x in checks),'pass':all(x['match'] for x in checks),'checks':checks})
assert len(manifest)==213 and all(x['match'] for x in checks)
print(json.dumps({'view_a_count':len(manifest),'determinism_match_count':sum(x['match'] for x in checks)},sort_keys=True))
