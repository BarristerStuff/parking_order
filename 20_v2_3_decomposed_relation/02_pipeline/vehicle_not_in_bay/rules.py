def vehicle_decision(outside,multibay,gate=None):
    if outside=='YES' or multibay=='YES':
        if gate=='A': return 'negative','gate_queue'
        if gate in ('B','C'): return 'positive',None
        if gate=='D': return 'uncertain',None
        raise ValueError('candidate requires gate')
    if outside=='NO' and multibay=='NO': return 'negative',None
    if 'UNCERTAIN' in (outside,multibay): return 'uncertain',None
    raise ValueError('invalid branch answer')
def frame_decision(vehicles):
    if any(v['decision']=='positive' for v in vehicles):return 'positive'
    if any(v['decision']=='uncertain' for v in vehicles):return 'uncertain'
    return 'negative'
