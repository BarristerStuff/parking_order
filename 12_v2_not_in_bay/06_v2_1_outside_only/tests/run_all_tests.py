#!/usr/bin/env python3
from pathlib import Path
import csv,json,hashlib,sys
O=Path(__file__).resolve().parents[1]; R=O.parents[2]
def sha(p):
 h=hashlib.sha256(p.read_bytes()).hexdigest();return h
def test_freeze():
 assert sha(O/'q1_prompt.txt')=='76151fc7f028c8274fd6c1a49158452a5b491d272b98effd463d8df2ba3b2eed'
 c=json.loads((O/'v2_1_val_config.json').read_text());assert c['allowed_split']=='VAL' and not c['holdout_access_allowed'] and not c['q2_enabled'] and c['max_workers']==2
 assert c['detector']['checkpoint_sha256']==sha(Path(c['detector']['checkpoint']))
def test_allowlist():
 a=list(csv.DictReader(open(O/'val_allowlist.csv')));assert len(a)==80 and {x['split'] for x in a}=={'VAL'} and len({x['media_id'] for x in a})==80
 assert all('HOLDOUT' not in x['image_path'] for x in a)
def test_predictions():
 p=[json.loads(x) for x in (O/'val_predictions.jsonl').read_text().splitlines()];assert len(p)==80 and len({x['media_id'] for x in p})==80
 assert sum(x['request_count'] for x in p)==95
 assert all(v.get('q2') is None for x in p for v in x['vehicle_results']) if any('q2' in v for x in p for v in x['vehicle_results']) else True
 assert all(x['model_label'] in {'positive','negative','uncertain'} for x in p)
def test_metrics():
 m=json.loads((O/'metrics.json').read_text());v=m['val'];assert v['recall']['numerator']==8 and v['recall']['denominator']==8
 assert v['negative_fpr']['numerator']==0 and v['negative_fpr']['denominator']==48
 assert v['hn01_fpr']['denominator']==6 and v['p03_alert_rate']['denominator']==6 and v['p05_alert_rate']['denominator']==4
def test_old_hashes():
 exp={'01_gt_and_split/v2_0_gt.csv':'321f0994006d2451352f0c48d73911749f6a471d24c16f25808bbf30c31bd353','01_gt_and_split/v2_split.csv':'f531aaff35d3940dd17bd57e1f9825903177dcd91d2f7e41d2a598a5a0cfdb24','03_debug/v2_dev_vehicle_detections.jsonl':'5685faa7c450e598f0e964445178a49bbcdb1d1e6e8fd5688fbdb807188385f9','05_vlm_dev_r1/predictions.jsonl':'2e98a2659a91df8ec4ec23ae2d5a337fb43f850f6ddc6a5679959026ebeabe75'}
 for rel,h in exp.items(): assert sha(O.parent/rel)==h,(rel,sha(O.parent/rel))
for fn in [test_freeze,test_allowlist,test_predictions,test_metrics,test_old_hashes]:
 fn();print('PASS',fn.__name__)
print('ALL_TESTS_PASS 5/5')
