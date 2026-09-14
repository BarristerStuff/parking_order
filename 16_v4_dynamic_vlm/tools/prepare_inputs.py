#!/usr/bin/env python3
"""Adapt the frozen V2 DEV detector cache into V4 full-scene + dynamic context inputs."""
from __future__ import annotations
import argparse, base64, csv, hashlib, io, json, math, pathlib, shutil, sys, time
from PIL import Image, ImageDraw, ImageFont

V4 = pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
CACHE_DEFAULT = pathlib.Path('/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl')
DATA_ROOT = pathlib.Path('/home/yanbo/net_vlm_xunjian_dataset')
CLASSES = {'car','bus','truck'}
IOU_THRESHOLD = 0.80
COLORS = [(230,25,75),(60,180,75),(255,225,25),(0,130,200),(245,130,48),(145,30,180),(70,240,240),(240,50,230)]

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''): h.update(x)
 return h.hexdigest()
def iou(a,b):
 ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
 ix1,iy1=max(ax1,bx1),max(ay1,by1); ix2,iy2=min(ax2,bx2),min(ay2,by2)
 iw,ih=max(0,ix2-ix1),max(0,iy2-iy1)
 inter=iw*ih
 aa=max(0,ax2-ax1)*max(0,ay2-ay1); ab=max(0,bx2-bx1)*max(0,by2-by1)
 return inter/(aa+ab-inter) if aa+ab-inter else 0.0

def resize_long(im, max_edge):
 w,h=im.size; scale=min(1.0,max_edge/max(w,h))
 if scale==1: return im.copy(),1.0
 return im.resize((max(1,round(w*scale)),max(1,round(h*scale))),getattr(Image, 'Resampling', Image).LANCZOS),scale

def encode_jpeg(im, quality=90):
 b=io.BytesIO(); im.convert('RGB').save(b,'JPEG',quality=quality,optimize=False,subsampling=0); return b.getvalue()
def font():
 try: return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',18)
 except Exception: return ImageFont.load_default()

def raw_detections(cache_row):
 out=[]
 for idx, d in enumerate(cache_row.get('detections', [])):
  rid=f"raw_{idx+1:04d}"
  b=d.get('bbox')
  ok=(d.get('class_name') in CLASSES and isinstance(b,list) and len(b)==4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in b) and b[2]>b[0] and b[3]>b[1])
  out.append({'raw_detection_id': rid, 'raw_index':idx, 'class_name':d.get('class_name'), 'class_id':d.get('class_id'), 'confidence':float(d.get('confidence',0.0)), 'bbox':[float(x) for x in b] if isinstance(b,list) and len(b)==4 else b, 'valid_for_dedup':ok, 'status':'eligible' if ok else 'invalid_or_disallowed'})
 return out

def dedup(raw):
 valid=[r for r in raw if r['valid_for_dedup']]
 # Stable class-agnostic NMS, no size filtering and no top-K truncation.
 order=sorted(valid,key=lambda r:(-r['confidence'],r['class_name'],r['raw_index']))
 kept=[]; suppressed=[]
 for r in order:
  hit=next((k for k in kept if iou(r['bbox'],k['bbox']) > IOU_THRESHOLD),None)
  if hit:
   r=dict(r); r['status']='duplicate_suppressed'; r['suppressed_by_raw_detection_id']=hit['raw_detection_id']; suppressed.append(r)
  else:
   r=dict(r); r['status']='kept'; kept.append(r)
 kept=sorted(kept,key=lambda r:r['raw_index'])
 for i,r in enumerate(kept,1): r['target_id']=f'T{i:02d}'
 return kept, suppressed

def make_crop(im, bbox, target_id, max_edge, quality):
 w,h=im.size; x1,y1,x2,y2=bbox; bw=x2-x1; bh=y2-y1
 crop_box=(max(0,math.floor(x1-0.5*bw)),max(0,math.floor(y1-0.25*bh)),min(w,math.ceil(x2+0.5*bw)),min(h,math.ceil(y2+0.75*bh)))
 c=im.crop(crop_box)
 c,scale=resize_long(c,max_edge)
 f=font(); margin=34
 out=Image.new('RGB',(c.width,c.height+margin),(255,255,255)); out.paste(c,(0,margin)); d=ImageDraw.Draw(out); d.text((5,7),target_id,fill=(0,0,0),font=f)
 b=encode_jpeg(out,quality); return b,crop_box,scale

def make_panorama(im, kept, max_edge, quality):
 out,scale=resize_long(im,max_edge); d=ImageDraw.Draw(out); f=font(); width=max(2,round(4*scale))
 for i,r in enumerate(kept):
  x1,y1,x2,y2=[v*scale for v in r['bbox']]; color=COLORS[i%len(COLORS)]
  d.rectangle((x1,y1,x2,y2),outline=color,width=width)
  # place label just outside if possible, never draw a contact/ground line.
  tx=max(0,min(out.width-60,x1)); ty=max(0,y1-22)
  d.rectangle((tx,ty,tx+52,ty+21),fill=(255,255,255),outline=color,width=1); d.text((tx+3,ty+2),r['target_id'],fill=color,font=f)
 return encode_jpeg(out,quality),scale

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--manifest',default=str(V4/'contracts/pilot_manifest.csv')); ap.add_argument('--cache',default=str(CACHE_DEFAULT)); ap.add_argument('--out',default=str(V4/'inputs/pilot')); ap.add_argument('--clean',action='store_true'); args=ap.parse_args()
 out=pathlib.Path(args.out); out.mkdir(parents=True,exist_ok=True)
 if args.clean:
  for p in out.iterdir():
   if p.is_dir(): shutil.rmtree(p)
   else: p.unlink()
 with open(args.manifest,newline='',encoding='utf-8') as f: manifest=list(csv.DictReader(f))
 with open(args.cache,encoding='utf-8') as f: cache={r['image_sha256']:r for r in (json.loads(x) for x in f if x.strip())}
 adapted=[]; batches=[]; total_raw=total_kept=total_suppressed=0
 for row in manifest:
  sha=row['image_sha256']; assert sha in cache, (row['media_id'],sha)
  image_path=pathlib.Path(row['absolute_path']); im=Image.open(image_path).convert('RGB')
  # Recheck source SHA before decoding output; this is an allowed DEV image.
  source_sha=sha_file(image_path); assert source_sha==sha,(row['media_id'],source_sha,sha)
  prep_started=time.time()
  raw=raw_detections(cache[sha]); kept,supp=dedup(raw)
  pano_b,pano_scale=make_panorama(im,kept,1024,90)
  image_dir=out/row['image_sha256']; image_dir.mkdir(parents=True,exist_ok=True)
  pano_path=image_dir/'panorama.jpg'; pano_path.write_bytes(pano_b)
  target_records=[]
  for r in kept:
   crop_b,crop_box,crop_scale=make_crop(im,r['bbox'],r['target_id'],768,90)
   cp=image_dir/f"{r['target_id']}_context.jpg"; cp.write_bytes(crop_b)
   target_records.append({**r,'crop_box_original_xyxy':crop_box,'crop_scale':crop_scale,'crop_path':str(cp),'crop_sha256':sha_bytes(crop_b)})
  batches_for=[]
  for start in range(0,len(target_records),3):
   ts=target_records[start:start+3]
   bid=f'B{start//3+1:02d}'
   batches_for.append({'batch_id':bid,'target_ids':[r['target_id'] for r in ts],'panorama_path':str(pano_path),'panorama_sha256':sha_bytes(pano_b),'crop_paths':[r['crop_path'] for r in ts],'crop_sha256s':[r['crop_sha256'] for r in ts],'image_order':['panorama']+[r['target_id'] for r in ts]})
  adapted.append({'media_id':row['media_id'],'group_key':row['group_key'],'split':'DEV','image_sha256':sha,'source_path':str(image_path),'source_size':list(im.size),'preprocess_seconds':time.time()-prep_started,'panorama_path':str(pano_path),'panorama_sha256':sha_bytes(pano_b),'panorama_scale':pano_scale,'raw_detections':raw,'kept_targets':target_records,'suppressed_detections':supp,'batches':batches_for})
  for b in batches_for: batches.append({**b,'media_id':row['media_id'],'image_sha256':sha,'group_key':row['group_key']})
  total_raw+=len(raw); total_kept+=len(kept); total_suppressed+=len(supp)
 (out/'adapted_inputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in adapted),encoding='utf-8')
 (out/'request_batches.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in batches),encoding='utf-8')
 summary={'images':len(adapted),'batches':len(batches),'raw_detection_rows':total_raw,'kept_targets':total_kept,'suppressed_duplicates':total_suppressed,'invalid_raw':sum(sum(r['status']=='invalid_or_disallowed' for r in x['raw_detections']) for x in adapted),'target_batch_size':3,'dedup_iou_threshold':IOU_THRESHOLD,'source_cache_sha256':sha_file(pathlib.Path(args.cache))}
 (out/'prepare_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
