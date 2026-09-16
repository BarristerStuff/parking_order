import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'02_pipeline'))
from vehicle_not_in_bay.rules import vehicle_decision,frame_decision
assert vehicle_decision('YES','NO','B')[0]=='positive'
assert vehicle_decision('NO','YES','C')[0]=='positive'
assert vehicle_decision('YES','NO','A')==('negative','gate_queue')
assert vehicle_decision('NO','NO')==('negative',None)
assert vehicle_decision('UNCERTAIN','NO')==('uncertain',None)
assert frame_decision([{'decision':'negative'},{'decision':'uncertain'}])=='uncertain'
assert frame_decision([{'decision':'negative'},{'decision':'positive'}])=='positive'
print('PASS v2.3 rules truth table')
