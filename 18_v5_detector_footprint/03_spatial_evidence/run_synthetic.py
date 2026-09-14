from pathlib import Path
import json,sys,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'04_rule_engine'))
from space_rule import build_spatial_evidence,decide_from_spatial_evidence,aggregate_image_decision

def run():
 freeze=json.loads((ROOT/'03_spatial_evidence/fixture_freeze.json').read_text())
 for p,h in freeze['files'].items():
  if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise RuntimeError('FIXTURE_FREEZE_MISMATCH')
 fixture=json.loads((ROOT/'03_spatial_evidence/synthetic_fixtures.json').read_text());evidence=[];pred=[]
 for case in fixture['cases']:
  e=build_spatial_evidence(case['vehicle'],case['roi']);d=decide_from_spatial_evidence(e,case['context'])
  evidence.append({'case_id':case['case_id'],'scope':'SYNTHETIC_UNIT_TEST_ONLY','evidence':e})
  pred.append({'case_id':case['case_id'],'scope':'SYNTHETIC_UNIT_TEST_ONLY','decision':d,'expected':case['expected'],'test_passed':d['label']==case['expected'] and (d['label']!='uncertain' or not d['alert'])})
 agg=fixture['aggregate_case'];members=[p['decision'] for p in pred if p['case_id'] in agg['members']];d=aggregate_image_decision(members,detector_complete=True)
 pred.append({'case_id':agg['case_id'],'scope':'SYNTHETIC_UNIT_TEST_ONLY','decision':d,'expected':agg['expected'],'test_passed':d['label']==agg['expected']})
 (ROOT/'03_spatial_evidence/evidence_outputs.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in evidence))
 (ROOT/'04_rule_engine/rule_predictions.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in pred))
 result={'scope':'SYNTHETIC_UNIT_TEST_ONLY_NOT_CLASSIFICATION_ACCURACY','test_pass_count':sum(x['test_passed'] for x in pred),'test_count':len(pred),'formal_pilot_rules_executed':False,'road_recall':None,'two_bay_recall':None,'negative_fpr':None,'gate_queue_fpr':None,'uncertain_rate':None,'spatial_evidence_formal_evaluation':'BLOCKED_NO_TRUSTED_GEOMETRY'}
 (ROOT/'04_rule_engine/rule_metrics.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 r=run();print(json.dumps(r,indent=2));raise SystemExit(r['test_pass_count']!=r['test_count'])
