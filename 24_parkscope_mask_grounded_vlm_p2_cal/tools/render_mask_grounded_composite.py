#!/usr/bin/env python3
import argparse, csv, hashlib, io, json, random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
P2 = Path(__file__).resolve().parents[1]
P0_PRED = ROOT/'21_parkscope_segmentation_feasibility_p0/03_inference/parkscope_predictions.jsonl'
P0_BIND = ROOT/'21_parkscope_segmentation_feasibility_p0/02_input_audit/selected_vehicle_binding.csv'
SPLIT = ROOT/'22_parkscope_structured_geometry_p1/01_input_audit/cal_eval_split.csv'
OUTDIR = P2/'_local_composites'
PANEL=(896,672); FINAL=(1792,672); FILL=(0,0,0)

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def parse_box(s): return [float(x) for x in json.loads(s)]
def letterbox(im,size=PANEL,fill=FILL):
    scale=min(size[0]/im.width,size[1]/im.height)
    nw,nh=max(1,round(im.width*scale)),max(1,round(im.height*scale))
    r=im.resize((nw,nh),Image.Resampling.LANCZOS)
    out=Image.new('RGB',size,fill); ox=(size[0]-nw)//2; oy=(size[1]-nh)//2; out.paste(r,(ox,oy))
    return out,scale,ox,oy

def poly_transform(poly,crop,scale,ox,oy):
    l,t,_,_=crop
    return [((float(x)-l)*scale+ox,(float(y)-t)*scale+oy) for x,y in poly]

def overlay_polygon(im, pts, color, alpha, outline_width):
    if len(pts)<3: return
    layer=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(layer)
    d.polygon(pts,fill=(*color,round(alpha*255)))
    if outline_width: d.line(pts+[pts[0]],fill=(*color,255),width=outline_width,joint='curve')
    im.paste(layer,(0,0),layer)

def render_one(row,pred):
    src=Path(row['source_path'])
    with Image.open(src) as z: raw=z.convert('RGB')
    if sha_file(src)!=row['source_sha256']: raise ValueError(f"source SHA mismatch {row['media_id']}")
    bbox=parse_box(row['frozen_bbox']); x0,y0,x1,y1=bbox
    left,scale,ox,oy=letterbox(raw)
    ld=ImageDraw.Draw(left); tb=[x0*scale+ox,y0*scale+oy,x1*scale+ox,y1*scale+oy]
    ld.rectangle(tb,outline=(255,0,0),width=5)
    w=x1-x0; h=y1-y0; crop=(max(0.0,x0-w),max(0.0,y0-.75*h),min(float(raw.width),x1+w),min(float(raw.height),y1+.75*h))
    crop_box=(int(crop[0]),int(crop[1]),int(crop[2]+.999999),int(crop[3]+.999999))
    rcrop=raw.crop(crop_box); crop=(float(crop_box[0]),float(crop_box[1]),float(crop_box[2]),float(crop_box[3]))
    dim=rcrop.point(lambda v: int(max(0,min(255,v*.45))))
    right,rscale,rox,roy=letterbox(dim)
    instances=pred['instances']; target_idx=int(row['matched_instance'])
    # 2. other vehicles, gray outline
    rd=ImageDraw.Draw(right,'RGBA')
    for inst in instances:
        if int(inst['class_id'])==3 and int(inst['instance_index'])!=target_idx and len(inst.get('mask_polygon') or [])>=3:
            pts=poly_transform(inst['mask_polygon'],crop,rscale,rox,roy)
            rd.line(pts+[pts[0]],fill=(160,160,160,255),width=2,joint='curve')
    target=next((x for x in instances if int(x['instance_index'])==target_idx),None)
    if target is None or int(target['class_id'])!=3: raise ValueError(f"invalid frozen target instance {row['media_id']} rank {row['selected_rank']}")
    tpts=poly_transform(target['mask_polygon'],crop,rscale,rox,roy)
    # 3 target fill only
    overlay_polygon(right,tpts,(255,48,48),.30,0)
    # 4 geometry cyan fill/boundary
    for inst in instances:
        if int(inst['class_id']) in (1,2) and len(inst.get('mask_polygon') or [])>=3:
            pts=poly_transform(inst['mask_polygon'],crop,rscale,rox,roy)
            overlay_polygon(right,pts,(0,216,255),.55,3)
    # 5 target boundary
    rd=ImageDraw.Draw(right,'RGBA'); rd.line(tpts+[tpts[0]],fill=(255,48,48,255),width=4,joint='curve')
    final=Image.new('RGB',FINAL,FILL); final.paste(left,(0,0)); final.paste(right,(896,0))
    b=io.BytesIO(); final.save(b,'JPEG',quality=90,subsampling=0,optimize=False,progressive=False)
    return b.getvalue(), {'crop_xyxy':list(crop),'target_instance':target_idx,'width':1792,'height':672}

def load_inputs():
    split=[]
    with SPLIT.open(newline='') as f:
        for r in csv.DictReader(f):
            if r['partition']=='CALIBRATION': split.append(r['media_id'])
    if len(split)!=30 or len(set(split))!=30: raise ValueError('CAL split must contain 30 unique media IDs')
    cal=set(split)
    preds={}
    for line in P0_PRED.open():
        x=json.loads(line);
        if x['media_id'] in cal: preds[x['media_id']]=x
    bindings=[]
    with P0_BIND.open(newline='') as f:
        for r in csv.DictReader(f):
            if r['media_id'] in cal: bindings.append(r)
    return split,preds,bindings

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--prepare',action='store_true'); ap.add_argument('--determinism-only',action='store_true'); args=ap.parse_args()
    split,preds,bindings=load_inputs(); OUTDIR.mkdir(parents=True,exist_ok=True)
    if set(split)!=set(preds): raise ValueError('missing CAL ParkScope predictions')
    rows=[]
    for b in sorted(bindings,key=lambda x:(split.index(x['media_id']),int(x['selected_rank']))):
        p=preds[b['media_id']]
        source=Path(p['image_path'])
        row={'media_id':b['media_id'],'selected_rank':b['selected_rank'],'frozen_bbox':b['frozen_bbox'],'matched_instance':b['matched_instance'],'match_status':b['match_status'],'source_path':str(source),'source_sha256':p['image_sha256']}
        if b['match_status']!='MATCHED': continue
        data,meta=render_one(row,p); out=OUTDIR/f"{b['media_id']}_target{b['selected_rank']}.jpg"; out.write_bytes(data)
        rows.append({**row,'composite_path_local':str(out),'composite_sha256':sha_bytes(data),**meta})
    fields=['media_id','selected_rank','composite_path_local','composite_sha256','width','height','source_path','source_sha256','frozen_bbox','target_instance','crop_xyxy']
    with (P2/'02_composites/composite_manifest.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader();
        for r in rows:
            q=dict(r); q['crop_xyxy']=json.dumps(q['crop_xyxy'],separators=(',',':')); w.writerow({k:q[k] for k in fields})
    rng=random.Random('P2_CAL_COMPOSITE_DETERMINISM_20260916'); chosen=rng.sample(rows,min(10,len(rows))); checks=[]
    for r in chosen:
        data,_=render_one(r,preds[r['media_id']]); checks.append({'media_id':r['media_id'],'selected_rank':int(r['selected_rank']),'expected_sha256':r['composite_sha256'],'regenerated_sha256':sha_bytes(data),'match':sha_bytes(data)==r['composite_sha256']})
    report={'seed':'P2_CAL_COMPOSITE_DETERMINISM_20260916','checked':len(checks),'matched':sum(x['match'] for x in checks),'pass':len(checks)==10 and all(x['match'] for x in checks),'checks':checks}
    (P2/'02_composites/determinism_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'composites':len(rows),'determinism':report['pass']},indent=2))
if __name__=='__main__': main()
