import unittest,copy
from space_rule import *
def rect(a,b,c,d):return [[a,b],[c,b],[c,d],[a,d]]
class TestRules(unittest.TestCase):
 def setUp(self):
  self.v={'coordinate_space':'image','footprint_source':'ground_contact','ground_contact_status':'validated','ground_contact_polygon_image':rect(10,10,90,90)}
  self.v.update(image_id='unit',source_sha256='unit-fixture-not-media',image_size=[100,100])
  self.roi={'image_id':'unit','source_sha256':'unit-fixture-not-media','validation_status':'SYNTHETIC_UNIT_TEST_ONLY','coordinate_space':'image','image_size':[100,100],'areas':{'road':[rect(0,0,99,99)],'gate_queue':[],'parking_area':[]},'bays':[],'adjacent_pairs':[]}
 def e(self):return build_spatial_evidence(self.v,self.roi)
 def test_road(self):self.assertEqual(decide_from_spatial_evidence(self.e(),{'normal_gate_queue':'no'})['label'],'positive_road')
 def test_queue(self):
  e=self.e();e['gate_queue_overlap_ratio']=1
  self.assertEqual(decide_from_spatial_evidence(e,{'normal_gate_queue':'yes'})['label'],'negative_gate_queue')
 def test_unclear_queue(self):self.assertFalse(decide_from_spatial_evidence(self.e(),{})['alert'])
 def test_bbox(self):
  e=self.e();e['footprint_source']='bbox_lower';self.assertEqual(decide_from_spatial_evidence(e,{'normal_gate_queue':'no'})['label'],'uncertain')
 def test_body_mask(self):
  e=self.e();e['ground_contact_validated']=False;self.assertFalse(decide_from_spatial_evidence(e,{'normal_gate_queue':'no'})['alert'])
 def test_missing(self):self.assertEqual(build_spatial_evidence(self.v,None)['road_overlap_ratio'],None)
 def test_space(self):
  self.roi['coordinate_space']='bev';self.assertEqual(self.e()['evidence_status'],'failed')
 def test_union(self):
  self.roi['areas']['road']*=2;self.assertEqual(self.e()['road_overlap_ratio'],1)
 def test_two(self):
  self.roi['areas']['road']=[];self.roi['bays']=[{'bay_id':'a','polygon':rect(0,0,50,99)},{'bay_id':'b','polygon':rect(50,0,99,99)}];self.roi['adjacent_pairs']=[['a','b']]
  self.assertEqual(decide_from_spatial_evidence(self.e(),{'normal_gate_queue':'no'})['label'],'positive_two_bays')
  self.roi['adjacent_pairs']=[];self.assertEqual(decide_from_spatial_evidence(self.e(),{'normal_gate_queue':'no'})['label'],'uncertain')
 def test_nan(self):
  e=self.e();e['road_overlap_ratio']=float('nan');self.assertFalse(decide_from_spatial_evidence(e,{'normal_gate_queue':'no'})['alert'])
 def test_conflict(self):
  e=self.e();e['best_bay_ratio']=.95;self.assertEqual(decide_from_spatial_evidence(e,{'normal_gate_queue':'no'})['reason_code'],'RULE_CONFLICT')
 def test_negative_subtypes(self):
  e=self.e();e.update(road_overlap_ratio=0,best_bay_ratio=.9,second_bay_ratio=.05)
  for side,label in [('inside','negative_in_bay'),('minor_side','negative_line_touch_or_minor_overrun'),('nose_tail','negative_nose_tail_overhang')]:self.assertEqual(decide_from_spatial_evidence(e,{'normal_gate_queue':'no','boundary_relation':side})['label'],label)
 def test_invalid_polygon(self):
  for p in [rect(0,0,0,0),[[0,0],[90,90],[0,90],[90,0]],rect(-1,0,90,90)]:
   self.v['ground_contact_polygon_image']=p;self.assertEqual(self.e()['evidence_status'],'failed')
 def test_aggregate(self):
  for labels,expected in [([], 'ignore'),(['ignore'],'ignore'),(['negative_in_bay'],'negative'),(['uncertain','negative_in_bay'],'uncertain'),(['uncertain','positive_two_bays'],'positive')]:self.assertEqual(aggregate_image_decision([{'label':x} for x in labels],detector_complete=True)['label'],expected)
 def test_stale_validated_flag(self):
  self.v.update(footprint_source='segmentation_mask',ground_contact_polygon_image=None,mask_polygon_image=rect(10,10,90,90))
  self.assertFalse(decide_from_spatial_evidence(self.e(),{'normal_gate_queue':'no'})['alert'])
 def test_wrong_roi_identity(self):
  self.roi['image_id']='other';self.assertEqual(self.e()['evidence_status'],'failed')
 def test_wrong_roi_size(self):
  self.roi['image_size']=[200,200];self.assertEqual(self.e()['evidence_status'],'failed')
 def test_unvalidated_roi(self):
  self.roi['validation_status']='unreviewed';self.assertEqual(self.e()['evidence_status'],'failed')
 def test_empty_detection_uncertain(self):
  self.assertEqual(aggregate_image_decision([])['label'],'uncertain')
if __name__=='__main__':unittest.main()
