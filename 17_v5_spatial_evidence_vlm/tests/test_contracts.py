import unittest,pathlib,json,csv,hashlib,sys
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'06_audit'));sys.path.insert(0,str(R/'05_evaluation'))
from check_p0_gate import assess
from evaluate_p0 import rate
class Contracts(unittest.TestCase):
 def test_freeze(self):
  f=json.loads((R/'reference/reference_freeze.json').read_text())
  self.assertNotIn('reference_freeze.json',f['files'])
  for k,v in f['files'].items():self.assertEqual(hashlib.sha256((R/'reference'/k).read_bytes()).hexdigest(),v)
 def test_allowlist(self):
  rows=list(csv.DictReader((R/'contracts/input_allowlist.csv').read_text().splitlines()));pilot=list(csv.DictReader((R/'contracts/pilot_manifest.csv').read_text().splitlines()));forbidden={x['media_id'] for x in csv.DictReader((R/'contracts/forbidden_split_metadata.csv').read_text().splitlines())}
  self.assertEqual(len(rows),60);self.assertEqual(len({x['image_id'] for x in rows}),60);self.assertFalse(forbidden & {x['image_id'] for x in rows});self.assertTrue(all(x['split']=='DEV' for x in pilot))
 def test_gate_blocks(self):
  g=assess();self.assertFalse(g['vlm_authorized']);self.assertFalse(g['rules_pilot_authorized']);self.assertEqual(g['coverage'],0)
 def test_zero_denominator(self):self.assertIsNone(rate(0,0)['ratio']);self.assertIsNone(rate(0,0)['wilson95'])
 def test_no_fake_classifier(self):
  m=json.loads((R/'05_evaluation/p0_metrics.json').read_text());self.assertEqual(m['physical_vlm_requests'],0)
  for k,v in m['classification_metrics'].items():
   if k!='status':self.assertIsNone(v)
 def test_missing_evidence(self):
  es=[json.loads(x) for x in (R/'02_spatial_evidence/spatial_evidence.jsonl').read_text().splitlines()]
  self.assertEqual(len(es),195);self.assertTrue(all(x['road_overlap_ratio'] is None and x['evidence_status']=='uncertain' for x in es))
if __name__=='__main__':unittest.main()
