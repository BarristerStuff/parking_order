import json,sys,unittest,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'04_rule_engine'))
from space_rule import build_spatial_evidence,decide_from_spatial_evidence,aggregate_image_decision
class Synthetic(unittest.TestCase):
 def test_all_fixture_cases(self):
  f=json.loads((R/'03_spatial_evidence/synthetic_fixtures.json').read_text())
  for c in f['cases']:
   with self.subTest(case=c['case_id']):
    d=decide_from_spatial_evidence(build_spatial_evidence(c['vehicle'],c['roi']),c['context']);self.assertEqual(d['label'],c['expected']);self.assertEqual(d['alert'],c['expected'].startswith('positive_'))
 def test_no_real_pilot_entry(self):
  c=json.loads((R/'03_spatial_evidence/synthetic_fixtures.json').read_text())['cases'][0];c['vehicle']['image_id']='IMG_007521'
  d=decide_from_spatial_evidence(build_spatial_evidence(c['vehicle'],c['roi']),c['context']);self.assertEqual(d['label'],'uncertain');self.assertFalse(d['alert'])
 def test_stale_ground_status(self):
  c=json.loads((R/'03_spatial_evidence/synthetic_fixtures.json').read_text())['cases'][0];c['vehicle']['visible_mask_polygon']=c['vehicle'].pop('ground_contact_polygon_image');c['vehicle']['mask_polygon_image']=c['vehicle']['visible_mask_polygon'];c['vehicle']['footprint_source']='segmentation_mask'
  self.assertFalse(decide_from_spatial_evidence(build_spatial_evidence(c['vehicle'],c['roi']),c['context'])['alert'])
 def test_missing_and_empty_safe(self):
  self.assertEqual(aggregate_image_decision([])['label'],'uncertain');self.assertEqual(aggregate_image_decision([],detector_complete=True)['label'],'ignore')
 def test_multivehicle_or(self):
  d=aggregate_image_decision([{'label':'uncertain'},{'label':'positive_two_bays'}]);self.assertTrue(d['alert'])
if __name__=='__main__':unittest.main()
