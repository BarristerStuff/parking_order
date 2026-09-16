#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
x=json.loads((root/'04_relation_rasters/raster_determinism.json').read_text())
assert x['sample_count']==20 and x['matching_count']==20 and x['pass'] is True
print('20/20 deterministic relation rasters: PASS')
