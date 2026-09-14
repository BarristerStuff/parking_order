import sys;sys.dont_write_bytecode=True
from pathlib import Path
from PIL import Image,ImageDraw
import json
O=Path(__file__).resolve().parent
run=sys.argv[1];rows=[json.loads(l) for l in (O/f'{run}_matching.jsonl').read_text().splitlines()]
for start in range(0,60,6):
 sheet=Image.new('RGB',(1920,1740),'#202020');draw=ImageDraw.Draw(sheet)
 for k,r in enumerate(rows[start:start+6]):
  im=Image.open(O/'detection_overlays'/run/f"{r['image_id']}.jpg");im.thumbnail((960,540));x=k%2*960;y=k//2*580;sheet.paste(im,(x,y+30));draw.text((x+5,y+5),f"{start+k+1}: {r['image_id']} unmatched refs {[r['references'][i]['target_id'] for i in r['unmatched_reference_indices']]}",fill='white')
 sheet.save(O/'detection_overlays'/f'{run}_sheet_{start//6+1:02d}.jpg')
print({k:sum(len(r[k]) for r in rows) for k in ['references','detections','matches','unmatched_reference_indices','unmatched_detection_indices','suppressed']})
