"""Deterministic vehicle selection matching v2.1 frozen behavior."""
def select(detections,width,height,config=None):
 cfg=(config or {}).get('selection',{}) if config else {}; edge=cfg.get('edge_margin_pixels',1); valid=[]
 for d in detections:
  x1,y1,x2,y2=d['bbox']
  if d.get('class_name') not in {'car','bus','truck'} or x2<=x1 or y2<=y1 or x1<=edge or y1<=edge or x2>=width-edge or y2>=height-edge: continue
  valid.append(d)
 valid.sort(key=lambda d:(-((d['bbox'][2]-d['bbox'][0])*(d['bbox'][3]-d['bbox'][1])),-d['confidence'],d['class_id'],*d['bbox']))
 chosen=valid[:cfg.get('max_selected',2)]
 if chosen and cfg.get('rank2_height_fraction_gte',.25): chosen=chosen[:1]+([chosen[1]] if len(chosen)>1 and chosen[1]['bbox'][3]-chosen[1]['bbox'][1]>=cfg.get('rank2_height_fraction_gte',.25)*height else [])
 return chosen
