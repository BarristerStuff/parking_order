from pathlib import Path
import json,csv,hashlib,io,math
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];D=R/'01_detector_audit';allow={r['image_id']:r for r in csv.DictReader((R/'contracts/allowlist.csv').read_text().splitlines())};ims={}
def image(id):
 if id not in ims:
  r=allow[id];b=Path(r['absolute_path']).read_bytes()
  if hashlib.sha256(b).hexdigest()!=r['image_sha256']:raise ValueError('SHA')
  ims[id]=Image.open(io.BytesIO(b)).convert('RGB')
 return ims[id]
rows=[json.loads(x) for x in (D/'r1_matching.jsonl').read_text().splitlines()];index={x['image_id']:x for x in rows};cases=[]
for id in ['IMG_007598','IMG_007548','IMG_007542','IMG_007673','IMG_007692']:
 x=index[id]
 for j in x['unmatched_detection_indices']:
  d=x['detections'][j];cases.append({'image_id':id,'type':'unmatched_detection','id':d['vehicle_id'],'bbox':d['bbox_xyxy']})
for id,rid in [('IMG_007547','T01'),('IMG_007601','T02'),('IMG_007650','T04'),('IMG_007606','T02'),('IMG_007340','T05')]:
 ref=next(r for r in index[id]['references'] if r['target_id']==rid);cases.append({'image_id':id,'type':'unmatched_reference','id':rid,'bbox':ref['bbox_xyxy']})
cases.append({'image_id':'IMG_007672','type':'duplicate_pair','id':'raw_0006+raw_0007','bbox':[1609,151,1766,224]})
for start in range(0,len(cases),8):
 part=cases[start:start+8];out=Image.new('RGB',(1600,350*math.ceil(len(part)/4)),(245,245,245));dr=ImageDraw.Draw(out)
 for i,c in enumerate(part):
  im=image(c['image_id']);x1,y1,x2,y2=c['bbox'];bw=x2-x1;bh=y2-y1;box=(max(0,int(x1-max(30,bw*.3))),max(0,int(y1-max(30,bh*.3))),min(im.width,math.ceil(x2+max(30,bw*.3))),min(im.height,math.ceil(y2+max(30,bh*.3))))
  crop=im.crop(box);cd=ImageDraw.Draw(crop);cd.rectangle([x1-box[0],y1-box[1],x2-box[0],y2-box[1]],outline='red',width=2);crop.thumbnail((395,300));x=i%4*400;y=i//4*350;out.paste(crop,(x,y+45));dr.text((x+2,y+3),f"{start+i+1} {c['image_id']} {c['id']}\n{c['type']}",fill='black');c['evidence']=str(D/'detection_overlays'/f'final_risks_{start//8+1}.jpg')
 out.save(D/'detection_overlays'/f'final_risks_{start//8+1}.jpg')
(D/'risk_review_index.json').write_text(json.dumps(cases,indent=2)+'\n')
print(json.dumps(cases,indent=2))
