from PIL import Image,ImageDraw,ImageFont
import json,pathlib
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
rows=[json.loads(x) for x in open(V4/'inputs/pilot/adapted_inputs.jsonl')]
items=[]
for r in rows:
 for t in r['kept_targets']:
  items.append((r['media_id'],r['group_key'],t['target_id'],t['crop_path']))
out=V4/'reference/crop_sheets'; out.mkdir(parents=True,exist_ok=True)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',12)
except: font=ImageFont.load_default()
for si in range(0,len(items),30):
 subset=items[si:si+30]; cw,ch=256,190; sheet=Image.new('RGB',(cw*5,ch*6),'white'); d=ImageDraw.Draw(sheet)
 for j,(mid,g,t,p) in enumerate(subset):
  im=Image.open(p).convert('RGB'); im.thumbnail((cw,ch-26)); x=(j%5)*cw; y=(j//5)*ch; sheet.paste(im,(x+(cw-im.width)//2,y+23)); d.text((x+3,y+4),f'{si+j+1:03d} {mid} {t}',fill='black',font=font)
 sheet.save(out/f'sheet_{si//30+1:02d}.jpg',quality=90)
print('sheets',len(list(out.glob('*.jpg'))),'items',len(items))
