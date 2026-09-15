def vehicle_decision(q1,q3=None,legacy=False):
 if q1=='C':
  if q3 in ('B','C') or (legacy and q3 is None): return 'outside'
  if q3=='A': return 'gate_queue'
  return 'uncertain'
 if q1=='D' or q3=='D': return 'uncertain'
 if q1 in ('A','B'): return 'in_bay'
 return 'uncertain'
def frame_decision(ds):
 if not ds:return 'uncertain'
 if any(x=='outside' for x in ds):return 'positive'
 if any(x=='uncertain' for x in ds):return 'uncertain'
 return 'negative'
def apply(vehicles,legacy=False):
 ds=[]
 for v in vehicles:
  d=vehicle_decision(v.get('q1'),v.get('q3'),legacy);v['decision']=d;ds.append(d)
 return frame_decision(ds),[v for v in vehicles if v['decision']=='gate_queue']
