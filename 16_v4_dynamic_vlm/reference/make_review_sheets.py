from PIL import Image,ImageDraw,ImageFont
import csv,pathlib,math
V4=pathlib.Path('/home/yanbo/net_vlm_parking_optimization/16_v4_dynamic_vlm')
rows=list(csv.DictReader(open(V4/'contracts/pilot_manifest.csv')))
out=V4/'reference/review_sheets'; out.mkdir(parents=True,exist_ok=True)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',16)
except: font=ImageFont.load_default()
for si in range(0,len(rows),15):
 subset=rows[si:si+15]; cellw,cellh=320,220; sheet=Image.new('RGB',(cellw*5,cellh*3),'white'); d=ImageDraw.Draw(sheet)
 for j,r in enumerate(subset):
  im=Image.open(r['absolute_path']).convert('RGB'); im.thumbnail((cellw,cellh-28)); x=(j%5)*cellw; y=(j//5)*cellh; sheet.paste(im,(x+(cellw-im.width)//2,y+24)); d.text((x+5,y+4),r['pilot_slot']+' '+r['media_id'],fill='black',font=font)
 sheet.save(out/f'sheet_{si//15+1:02d}.jpg',quality=90)
print(out)
