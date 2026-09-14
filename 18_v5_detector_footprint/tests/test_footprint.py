import sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'02_footprint_audit'))
from footprint import process_target
from test_footprint_methods import FootprintTests
from test_audit_integrity import AuditIntegrity
class FootprintSafety(unittest.TestCase):
 def test_ground_never_created_from_proxy(self):
  for extra in ({},{'ground_contact_status':'validated'},{'ground_contact_polygon':[[1,1],[2,1],[2,2]]}):
   target={'image_id':'SYNTH_PROXY','vehicle_id':'v','bbox_xyxy':[10,10,90,90],'mask_contours_image':[[[10,10],[90,10],[90,90],[10,90]]],**extra}
   for row in process_target(target,100,100):
    self.assertIsNone(row['ground_contact_polygon']);self.assertNotEqual(row['status'],'validated')
 def test_method_count_fixed(self):
  from footprint import METHODS
  self.assertEqual(len(METHODS),2)
if __name__=='__main__':unittest.main()
