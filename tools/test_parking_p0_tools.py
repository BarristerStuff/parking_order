#!/usr/bin/env python3
import base64
import importlib.util
import io
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path('/home/yanbo/net_vlm_parking_optimization/tools')

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

run=load('run_parking_p0', 'run_parking_p0.py')
analyze=load('analyze_parking_p0', 'analyze_parking_p0.py')

assert run.parse_model_response('{"label":"1","reason":"r","evidence":"e"}')["model_label"] == '1'
assert run.parse_model_response('```json\n{"label":"uncertain","reason":"r","evidence":"e"}\n```')["model_label"] == 'uncertain'
assert run.LANCZOS_RESAMPLE is not None
with tempfile.TemporaryDirectory() as tmpdir:
    source = Path(tmpdir) / 'source.png'
    Image.new('RGB', (10, 5), (255, 255, 255)).save(source)
    encoded = run.preprocess_image(source, {'preprocess': {'canvas_width': 448, 'canvas_height': 336, 'letterbox_color': [0, 0, 0], 'jpeg_quality': 70}})
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as rendered:
        assert rendered.size == (448, 336)
try:
    run.parse_model_response('{"label":"yes","reason":"r","evidence":"e"}')
except ValueError:
    pass
else:
    raise AssertionError('invalid label accepted')
rows=[
 {'gt_label':'1','model_label':'1','status':'ok'},
 {'gt_label':'1','model_label':'0','status':'ok'},
 {'gt_label':'0','model_label':'1','status':'ok'},
 {'gt_label':'0','model_label':'0','status':'ok'},
 {'gt_label':'0','model_label':'uncertain','status':'ok'},
 {'gt_label':'uncertain','model_label':'1','status':'ok'},
 {'gt_label':'1','model_label':'','status':'parse_failure'},
]
c=analyze.confusion(rows)
assert c == {'TP':1,'FP':1,'TN':1,'FN':1}, c
m=analyze.binary_metrics(c)
assert m['precision']==0.5 and m['recall']==0.5 and m['specificity']==0.5 and m['balanced_accuracy']==0.5
assert analyze.percentile([1,2,3,4],0.95)==3.8499999999999996
print('P0_TOOL_TESTS_OK')
