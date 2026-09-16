#!/usr/bin/env python3
"""Independent EVAL runner. Intentionally refuses to run unless calibration produced a safe frozen winner."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
w=json.loads((root/'03_calibration/calibration_winner.json').read_text())
if w.get('calibration_gate')!='PASS' or not w.get('winner'):
 print('BLOCKED: calibration produced no safe geometry rule; EVAL must not be accessed.',file=sys.stderr)
 raise SystemExit(2)
raise SystemExit('A safe winner exists; implement/run only under a future authorized continuation.')
