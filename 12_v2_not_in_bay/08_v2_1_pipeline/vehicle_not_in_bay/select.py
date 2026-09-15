def select(ds,w,h):
 valid=[]
 for d in ds:
  b=d['bbox'];x1,y1,x2,y2=b
  if d.get('class_name') not in {'car','bus','truck'} or x2<=x1 or y2<=y1:continue
  if x1<=1 or y1<=1 or x2>=w-1 or y2>=h-1:continue
  valid.append(d)
 valid.sort(key=lambda d:(-((d['bbox'][2]-d['bbox'][0])*(d['bbox'][3]-d['bbox'][1])),-d['confidence'],d['class_id'],*d['bbox']))
 return valid[:1]+(valid[1:2] if len(valid)>1 and valid[1]['bbox'][3]-valid[1]['bbox'][1]>=.25*h else [])
