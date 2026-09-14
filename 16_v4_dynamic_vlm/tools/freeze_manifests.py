#!/usr/bin/env python3
"""Freeze DEV-only allowlists and the deterministic V4 pilot manifest."""
from __future__ import annotations
import csv, hashlib, json, pathlib, sys
from datetime import datetime, timezone

OPT = pathlib.Path('/home/yanbo/net_vlm_parking_optimization')
DATA = pathlib.Path('/home/yanbo/net_vlm_xunjian_dataset')
V4 = OPT / '16_v4_dynamic_vlm'
SPLIT = OPT / '12_v2_not_in_bay/01_gt_and_split/v2_split.csv'
MAPPING = OPT / '02_ingest/manifests/formal_media_mapping.csv'
CACHE = OPT / '12_v2_not_in_bay/03_debug/v2_dev_vehicle_detections.jsonl'
SEED = '20260909'
# The prefix is the only stratification key; no label is inferred here.
REQUESTED = {
    'p01': 12, 'p03': 12, 'p05': 8, 'p02': 3, 'p04': 3, 'p06': 2,
    'n01': 1, 'n02': 1, 'n03': 1, 'n04': 1, 'n05': 1, 'n06': 1,
    'hn04': 1, 'hn06': 1, 'hn01': 6,
    'u01': 2, 'u02': 1, 'u03': 1, 'u04': 1, 'u05': 1,
}

def sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def write_csv(p, fields, rows):
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader(); w.writerows(rows)

def main():
    V4.mkdir(parents=True, exist_ok=True)
    with SPLIT.open(newline='', encoding='utf-8') as f: split_rows = list(csv.DictReader(f))
    with MAPPING.open(newline='', encoding='utf-8') as f: mapping = {r['media_id']: r for r in csv.DictReader(f)}
    with CACHE.open(encoding='utf-8') as f: cache_rows = [json.loads(x) for x in f if x.strip()]
    cache_by_sha = {r['image_sha256']: r for r in cache_rows}
    dev = [r for r in split_rows if r['split'] == 'DEV']
    val_holdout = [r for r in split_rows if r['split'] in {'VAL', 'HOLDOUT'}]
    assert len(dev) == 238, len(dev)
    assert len(val_holdout) == 159, len(val_holdout)
    assert all(r['media_id'] in mapping for r in split_rows)
    allow_rows = []
    for r in dev:
        m = mapping[r['media_id']]
        path = DATA / m['relative_path']
        # This existence check is metadata/filesystem only; no image is decoded here.
        allow_rows.append({
            'media_id': r['media_id'], 'group_key': r['group_key'], 'split': r['split'],
            'image_sha256': m['sha256'], 'relative_path': m['relative_path'],
            'absolute_path': str(path), 'cache_key_sha256': m['sha256'],
            'cache_present': str(m['sha256'] in cache_by_sha).lower(),
            'path_exists': str(path.is_file()).lower(),
        })
    write_csv(V4/'contracts/dev_image_allowlist.csv', list(allow_rows[0]), allow_rows)
    forbidden_rows = []
    for r in val_holdout:
        m = mapping[r['media_id']]
        # Metadata only: this file intentionally omits any image decoding or image-derived fields.
        forbidden_rows.append({'media_id': r['media_id'], 'group_key': r['group_key'], 'split': r['split'], 'image_sha256': m['sha256'], 'relative_path': m['relative_path']})
    write_csv(V4/'contracts/forbidden_split_metadata.csv', list(forbidden_rows[0]), forbidden_rows)

    selected = []
    shortages = []
    for prefix, n in REQUESTED.items():
        pool = [r for r in allow_rows if r['group_key'].startswith(prefix + '-')]
        ranked = sorted(pool, key=lambda r: hashlib.sha256((SEED + '\0' + r['image_sha256']).encode()).hexdigest())
        if len(pool) < n: shortages.append({'group_prefix': prefix, 'requested': n, 'available': len(pool)})
        for rank, r in enumerate(ranked[:n], start=1):
            selected.append({
                'pilot_slot': prefix + f'-{rank:02d}', 'group_prefix': prefix, 'selection_rank': rank,
                'media_id': r['media_id'], 'group_key': r['group_key'], 'split': 'DEV',
                'image_sha256': r['image_sha256'], 'relative_path': r['relative_path'],
                'absolute_path': r['absolute_path'], 'cache_key_sha256': r['cache_key_sha256'],
            })
    # Stable contract order: requested group order, then selection rank.
    assert not shortages, shortages
    assert len(selected) == 60, len(selected)
    assert len({r['media_id'] for r in selected}) == 60
    write_csv(V4/'contracts/pilot_manifest.csv', list(selected[0]), selected)
    contract = {
        'contract_version': 'V4_DYNAMIC_CONTEXT_VLM_2026-09-09',
        'event_name': 'parking_order_violation',
        'business_definition': 'v3.0_user_confirmed',
        'algorithm_revision': 'V4_DYNAMIC_CONTEXT_VLM',
        'candidate_id': 'V4_R0_GLOBAL_TARGET_CONTEXT',
        'source_type': 'AIGC',
        'reference_basis': 'AI_VISUAL_REVIEWED_PROVISIONAL',
        'human_gold': False,
        'dataset_root': str(DATA),
        'allowed_split': 'DEV', 'val_access_allowed': False, 'holdout_access_allowed': False,
        'split_csv_sha256': sha_file(SPLIT), 'media_mapping_sha256': sha_file(MAPPING),
        'detector_cache_path': str(CACHE), 'detector_cache_sha256': sha_file(CACHE),
        'pilot_seed': SEED, 'pilot_count': 60, 'requested_group_counts': REQUESTED,
        'target_batch_size': 3, 'max_client_concurrency': 2, 'max_physical_requests': 1000,
        'ollama_base_url': 'http://192.168.20.62:11434', 'model': 'qwen3.5:4b',
        'api_generate': 'http://192.168.20.62:11434/api/generate',
        'smoke_max_before_pilot': 2, 'semantic_retries': 0, 'transport_retries': 1,
        'preprocess': {
            'panorama_max_long_edge': 1024, 'crop_max_long_edge': 768, 'jpeg_quality': 90,
            'crop_expand': {'left_right_bbox_width': 0.5, 'top_bbox_height': 0.25, 'bottom_bbox_height': 0.75},
            'full_vehicle_context': True, 'artificial_bay_lines': False, 'ground_band_only': False,
            'manual_roi': False,
        },
        'detector': {
            'cache_only': True, 'allowed_classes': ['car', 'bus', 'truck'],
            'raw_cache_source': 'V2_DEV_NEW_LOCAL_YOLO11N',
            'dedup': {'method': 'class_agnostic_high_overlap_fixed_nms', 'iou_threshold': 0.80, 'keep': 'highest_confidence_then_class_name_then_raw_index'},
            'raw_detection_id': 'cache_row_index:global_detection_index',
        },
        'output_schema_fields': ['target_id','vehicle_valid','evidence_sufficient','road_or_drive_aisle','occupies_two_bays','in_one_bay_or_designated_area','minor_line_or_nose_tail_only','normal_gate_queue','evidence'],
        'decision_contract': 'contracts/decision_rules.md',
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'freeze_notes': 'Group prefixes stratify selection only; no group or filename is included in model input.',
    }
    (V4/'contracts/run_contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    (V4/'contracts/selection_shortages.json').write_text(json.dumps({'shortages': shortages, 'status': 'none' if not shortages else 'shortage'}, indent=2)+'\n')
    print(json.dumps({'dev': len(dev), 'forbidden': len(val_holdout), 'pilot': len(selected), 'group_counts': {k: sum(x['group_prefix']==k for x in selected) for k in REQUESTED}, 'shortages': shortages, 'split_sha256': sha_file(SPLIT), 'mapping_sha256': sha_file(MAPPING), 'cache_sha256': sha_file(CACHE)}, indent=2))

if __name__ == '__main__': main()
