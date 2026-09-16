#!/usr/bin/env python3

def target_decision(inside,multi,outside,anchor_valid=True):
    if not anchor_valid: return 'UNCERTAIN_ANCHOR'
    if inside=='YES' and (multi=='YES' or outside=='YES'): return 'UNCERTAIN_CONFLICT'
    if multi=='YES' or outside=='YES': return 'POSITIVE'
    if inside=='YES' and multi=='NO' and outside=='NO': return 'NEGATIVE'
    return 'UNCERTAIN'

def frame_decision(ds):
    if any(x=='POSITIVE' for x in ds): return 'positive'
    if ds and all(x=='NEGATIVE' for x in ds): return 'negative'
    return 'uncertain'

def main():
    cases=[(('YES','NO','NO',True),'NEGATIVE'),(('NO','YES','NO',True),'POSITIVE'),(('NO','NO','YES',True),'POSITIVE'),(('YES','YES','NO',True),'UNCERTAIN_CONFLICT'),(('YES','NO','YES',True),'UNCERTAIN_CONFLICT'),(('UNCERTAIN','NO','NO',True),'UNCERTAIN'),(('NO','NO','NO',True),'UNCERTAIN'),(('NO','NO','NO',False),'UNCERTAIN_ANCHOR')]
    for args,want in cases:
        got=target_decision(*args); assert got==want,(args,got,want)
    assert frame_decision(['NEGATIVE','NEGATIVE'])=='negative'
    assert frame_decision(['NEGATIVE','UNCERTAIN'])=='uncertain'
    assert frame_decision(['UNCERTAIN_ANCHOR'])=='uncertain'
    assert frame_decision(['NEGATIVE','POSITIVE'])=='positive'
    print('fusion tests: PASS (12 assertions)')
if __name__=='__main__': main()
