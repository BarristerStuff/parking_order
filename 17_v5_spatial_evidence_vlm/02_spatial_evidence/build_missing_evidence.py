"""Run only the missing-evidence safety path; not P1 successful spatial measurement."""
import json,sys,pathlib
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'03_rule_engine'))
from space_rule import build_spatial_evidence
rows=[json.loads(x) for x in (R/'01_footprint/footprint_outputs.jsonl').read_text().splitlines()]
es=[build_spatial_evidence(x,None) for x in rows]
(R/'02_spatial_evidence/spatial_evidence.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in es))
(R/'02_spatial_evidence/evidence_metrics.json').write_text(json.dumps({'status':'MISSING_EVIDENCE_SAFETY_PATH_ONLY','target_records':len(es),'clear_evidence':0,'unavailable_roi':len(es),'rules_pilot':'NOT_EXECUTED','not_formal_accuracy':True},indent=2)+'\n')
