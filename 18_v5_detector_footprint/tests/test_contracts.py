"""Standard-library contract checks; no source pixels/model calls."""
import csv,json,hashlib,unittest,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def csvrows(path):return list(csv.DictReader(path.read_text().splitlines()))
class Contracts(unittest.TestCase):
 def test_allowlist_only_frozen_dev(self):
  allow=csvrows(R/'contracts/allowlist.csv');pilot=csvrows(R/'contracts/pilot_manifest.csv');bad={x['media_id'] for x in csvrows(R/'contracts/forbidden_split_metadata.csv')}
  self.assertEqual(len(allow),60);self.assertEqual(len({x['image_id'] for x in allow}),60);self.assertFalse(bad & {x['image_id'] for x in allow});self.assertTrue(all(x['split']=='DEV' for x in pilot));self.assertEqual({(x['image_id'],x['absolute_path'],x['image_sha256']) for x in allow},{(x['media_id'],x['absolute_path'],x['image_sha256']) for x in pilot})
 def test_contract_freeze(self):
  freeze=json.loads((R/'contracts/preregistration_freeze.json').read_text())
  for p,h in freeze['files'].items():self.assertEqual(hashlib.sha256((R/'contracts'/p).read_bytes()).hexdigest(),h)
 def test_reference_unchanged(self):
  v=R.parent/'16_v4_dynamic_vlm/reference';f=json.loads((v/'REFERENCE_FREEZE.json').read_text())
  for p,h in f['files'].items():self.assertEqual(hashlib.sha256((v/p).read_bytes()).hexdigest(),h)
 def test_no_vlm_authorization(self):
  c=json.loads((R/'contracts/run_contract.json').read_text());self.assertIs(c['vlm_prohibited'],True);self.assertEqual(c['physical_remote_model_requests'],0)
 def test_no_synthetic_as_pilot_metrics(self):
  m=json.loads((R/'04_rule_engine/rule_metrics.json').read_text());self.assertFalse(m['formal_pilot_rules_executed'])
  for key in ['road_recall','two_bay_recall','negative_fpr','gate_queue_fpr','uncertain_rate']:self.assertIsNone(m[key])
 def test_fixed_candidate_and_method_limits(self):
  c=json.loads((R/'contracts/run_contract.json').read_text());self.assertEqual(c['max_detector_candidates'],2);self.assertEqual(c['r1_allowed_changed_main_factors'],1);self.assertEqual(c['max_footprint_methods'],2);self.assertFalse(c['ground_contact_proxy_can_alert'])
if __name__=='__main__':unittest.main()
