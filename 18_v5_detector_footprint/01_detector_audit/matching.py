"""Label-blind deterministic bbox matching; no dependencies or filesystem writes."""
def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=max(0,a[2]-a[0])*max(0,a[3]-a[1])+max(0,b[2]-b[0])*max(0,b[3]-b[1])-inter
    return inter/union if union else 0.0

def greedy_match(references,detections,minimum_iou=0.5):
    pairs=sorted(((-iou(a,b),r,d) for r,a in enumerate(references) for d,b in enumerate(detections) if iou(a,b)>=minimum_iou))
    used_r=set();used_d=set();matches=[]
    for neg,r,d in pairs:
        if r not in used_r and d not in used_d:
            used_r.add(r);used_d.add(d);matches.append({'reference_index':r,'detection_index':d,'iou':-neg})
    return matches,[r for r in range(len(references)) if r not in used_r],[d for d in range(len(detections)) if d not in used_d]
