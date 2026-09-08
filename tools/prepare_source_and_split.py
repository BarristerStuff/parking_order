#!/usr/bin/env python3
"""Prepare an auditable parking source inventory and frozen group split plan."""
from __future__ import annotations
import csv, hashlib, json, re, struct, zlib
from collections import Counter
from pathlib import Path

WORKSPACE = Path('/home/yanbo/net_vlm_parking_optimization')
SOURCE = Path('/home/yanbo/下载/batch_20260902_115647_parking-order-violation-batch1-400-retry')

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def png_dims(path: Path) -> tuple[int,int]:
    b=path.read_bytes()
    if b[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError(f'not PNG: {path}')
    pos=8
    while pos+12 <= len(b):
        n=struct.unpack('>I',b[pos:pos+4])[0]; typ=b[pos+4:pos+8]
        end=pos+12+n
        if end>len(b): raise ValueError(f'truncated PNG: {path}')
        payload=b[pos+8:pos+8+n]
        crc=struct.unpack('>I',b[pos+8+n:end])[0]
        if zlib.crc32(typ+payload)&0xffffffff != crc: raise ValueError(f'bad PNG CRC: {path}')
        if typ==b'IHDR': return struct.unpack('>II',payload[:8])
        pos=end
    raise ValueError(f'no IHDR: {path}')

def parse_scene(scene: dict) -> tuple[str,str,str]:
    slug=scene['slug']
    m=re.fullmatch(r'pov-b1-\d+-(?P<group>.+)-front-(?:center|left|right)',slug)
    if not m: raise ValueError(f'unexpected slug: {slug}')
    group=m.group('group')
    code=group.split('-',1)[0]
    if code.startswith('p'): role='positive'; label='1'
    elif code.startswith('n'): role='negative'; label='0'
    elif code.startswith('hn'): role='hard_negative'; label='0'
    elif code.startswith('u'): role='uncertain'; label='uncertain'
    else: raise ValueError(f'unexpected role code: {code}')
    return group, role, label

# Group-level assignment is frozen explicitly and targets 60/20/20 by finalized image count.
GROUP_SPLITS = {
 'p01-outside-legal-bay-clear':'train',
 'p02-cross-single-boundary-line':'train',
 'p03-span-two-bays':'validation',
 'p04-angled-footprint-outside':'holdout',
 'p05-multi-vehicle-at-least-one-violation':'train',
 'p06-nose-or-tail-intrudes-aisle':'holdout',
 'n01-standard-inside-bay':'train',
 'n02-close-to-line-but-inside':'train',
 'n03-diagonal-bay-correct':'holdout',
 'n04-parallel-bay-correct':'train',
 'n05-multiple-all-correct':'holdout',
 'n06-special-marked-space-geometry-correct':'validation',
 'hn01-gate-queue':'train',
 'hn02-faded-lines-but-confirmably-inside':'validation',
 'hn03-perspective-looks-like-crossing':'holdout',
 'hn04-large-vehicle-compliant':'train',
 'hn05-adjacent-vehicle-occludes-lines':'validation',
 'hn06-shadows-cracks-curbs-mimic-lines':'train',
 'u01-insufficient-parking-visual-evidence':'train',
 'u02-markings-severely-missing-or-occluded':'validation',
 'u03-vehicle-cut-by-frame-edge':'holdout',
 'u04-night-or-blur-boundary-unreadable':'train',
 'u05-gate-queue-or-parking-ambiguous':'train',
}

def main() -> None:
    manifest=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    if manifest['scene_count'] != 400: raise SystemExit('scene_count mismatch')
    finalized=[s for s in manifest['scenes'] if s['status']=='finalized']
    if len(finalized)!=397: raise SystemExit(f'finalized mismatch: {len(finalized)}')
    rows=[]; group_counts=Counter(); split_counts=Counter(); role_counts=Counter()
    for scene in sorted(finalized,key=lambda x:x['id']):
        group,role,label=parse_scene(scene)
        if group not in GROUP_SPLITS: raise SystemExit(f'missing split for group {group}')
        image=SOURCE/'final'/(scene['file_stem']+'.png')
        prompt=SOURCE/'prompts'/(scene['file_stem']+'.txt')
        if not image.is_file() or not prompt.is_file(): raise SystemExit(f'missing artifact for {scene["id"]}')
        width,height=png_dims(image)
        if (width,height)!=(1920,1080): raise SystemExit(f'bad dims for {image}: {(width,height)}')
        rows.append({'source_id':str(scene['id']),'slug':scene['slug'],'file_stem':scene['file_stem'],
                     'group_key':group,'scenario_id':'POV_PARKING_B1_'+group.upper().replace('-','_'),
                     'role':role,'event_label':label,'split':GROUP_SPLITS[group],
                     'image_path':str(image),'prompt_path':str(prompt),'sha256':sha256(image),
                     'width':str(width),'height':str(height)})
        group_counts[group]+=1; split_counts[GROUP_SPLITS[group]]+=1; role_counts[(GROUP_SPLITS[group],role)]+=1
    if set(GROUP_SPLITS)!=set(r['group_key'] for r in rows): raise SystemExit('group map mismatch')
    out=WORKSPACE/'02_ingest'
    with (out/'source_inventory.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    plan={'task':'parking_order_violation','event_definition_version':'v1.1','source_batch':manifest['batch_id'],
          'planned_slot_count':400,'successful_image_count':397,'failed_generation_slots':[25,107,121],
          'corrupt_image_count':0,'exact_duplicate_count':0,'prompt_count':400,
          'gt_basis':'generation_intent','gt_review_status':'unreviewed',
          'split_literal_mapping':{'train':'DEV','validation':'VAL','holdout':'HOLDOUT'},
          'group_split_map':GROUP_SPLITS,'group_counts':dict(sorted(group_counts.items())),
          'split_counts':dict(split_counts),
          'role_counts_by_split':{f'{sp}:{role}':n for (sp,role),n in sorted(role_counts.items())},
          'p0_allowed_split':'train','val_consumed':False,'holdout_consumed':False}
    (WORKSPACE/'03_split_freeze'/'group_split_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(plan,ensure_ascii=False,sort_keys=True))

if __name__=='__main__': main()
