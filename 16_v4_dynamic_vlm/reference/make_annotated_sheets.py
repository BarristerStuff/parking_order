from PIL import Image,ImageDraw,ImageFont
import json,pathlib
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
rows=[json.loads(x) for x in open(V4/'inputs/pilot/adapted_inputs.jsonl')]
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',15)
except: font=ImageFont.load_default()
for prefix in ['p03','p05','p02','p04','p06','n','hn','u']:
 sub=[r for r in rows if r['group_key'].startswith(prefix)]
 if not sub: continue
 out=V4/'reference/annotated_sheets'/prefix; out.mkdir(parents=True,exist_ok=True)
 for si in range(0,len(sub),4):
  chunk=sub[si:si+4]; cw,ch=640,390; sheet=Image.new('RGB',(cw*2,ch*2),'white'); d=ImageDraw.Draw(sheet)
  for j,r in enumerate(chunk):
   im=Image.open(r['panorama_path']).convert('RGB'); im.thumbnail((cw,ch-28)); x=(j%2)*cw; y=(j//2)*ch; sheet.paste(im,(x+(cw-im.width)//2,y+24)); d.text((x+5,y+4),r['media_id']+' '+r['group_key'],fill='black',font=font)
  sheet.save(out/f'sheet_{si//4+1:02d}.jpg',quality=90)
print('done')
