#!/usr/bin/env python3
"""Create the one-image-per-batch R1 protocol from frozen R0 pilot artifacts."""
from __future__ import annotations
import csv,hashlib,json,pathlib,shutil
from PIL import Image,ImageDraw,ImageFont
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm'); SRC=V4/'inputs/pilot'; OUT=V4/'inputs/pilot_r1'
def sha(p):
 h=hashlib.sha256();
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
try: FONT=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',18)
except: FONT=ImageFont.load_default()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rows=[json.loads(x) for x in open(SRC/'adapted_inputs.jsonl') if x.strip()]
 all_batches=[]; newrows=[]
 for a in rows:
  od=OUT/a['image_sha256']; od.mkdir(parents=True,exist_ok=True)
  pano=Image.open(a['panorama_path']).convert('RGB')
  # One composite image: complete scene on top; requested context crops below in left-to-right target order.
  width=1024; pano.thumbnail((width,576)); margin=42; gap=10
  crops=[Image.open(p).convert('RGB') for p in [t['crop_path'] for t in a['kept_targets']]]
  for c in crops: c.thumbnail((330,330))
  maxh=max([c.height for c in crops[:3]] or [0]); height=margin+pano.height+gap+(maxh+margin if crops else 0)
  # Build one composite per batch below, not one for all targets, to keep target-local identity explicit.
  batches=[]
  for start in range(0,len(crops),3):
   ts=a['kept_targets'][start:start+3]; cs=crops[start:start+3]
   bh=max([c.height for c in cs] or [0]); H=margin+pano.height+gap+margin+bh
   comp=Image.new('RGB',(width,H),'white'); d=ImageDraw.Draw(comp); d.text((8,10),'SCENE (complete image)',fill='black',font=FONT); comp.paste(pano,(0,margin))
   d.text((8,margin+pano.height+gap+4),'REQUESTED CONTEXT CROPS: '+', '.join(t['target_id'] for t in ts),fill='black',font=FONT)
   y=margin+pano.height+gap+margin
   x=0
   for t,c in zip(ts,cs):
    comp.paste(c,(x,y)); d.rectangle((x,y,x+c.width,y+c.height),outline=(0,0,0),width=2); x+=c.width+10
   bpath=od/f"{ts[0]['target_id']}_{ts[-1]['target_id']}_composite.jpg"; comp.save(bpath,quality=90,optimize=False,subsampling=0)
   b={'batch_id':f"B{start//3+1:02d}",'target_ids':[t['target_id'] for t in ts],'composite_path':str(bpath),'composite_sha256':sha(bpath),'image_order':['SCENE']+[t['target_id'] for t in ts],'media_id':a['media_id'],'image_sha256':a['image_sha256'],'group_key':a['group_key']}
   batches.append(b); all_batches.append(b)
  newrows.append({**a,'protocol':'single_composite_image_v1','batches':batches,'composite_batch_count':len(batches)})
 (OUT/'adapted_inputs.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in newrows),encoding='utf-8')
 (OUT/'request_batches.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in all_batches),encoding='utf-8')
 summary={'images':len(newrows),'batches':len(all_batches),'composite_inputs':len(all_batches),'target_batch_size':3,'source_r0_adapted_sha256':sha(SRC/'adapted_inputs.jsonl'),'source_r0_batches_sha256':sha(SRC/'request_batches.jsonl'),'protocol':'one composite image: scene top + requested context crops below','source_image_and_crop_geometry_unchanged':True}
 (OUT/'prepare_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
