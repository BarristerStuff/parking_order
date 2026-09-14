import sys,unittest,importlib.util
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'01_detector_audit'))
from matching import iou,greedy_match
from test_matching_core import MatchingCore
class MatchingIntegration(unittest.TestCase):
 def test_duplicate_candidates_one_reference_only(self):
  matched,ur,ud=greedy_match([[0,0,10,10]],[[0,0,10,10],[0,0,10,10]])
  self.assertEqual(len(matched),1);self.assertEqual(len(ud),1);self.assertEqual(ur,[])
 def test_unmatched_not_miss(self):
  matched,ur,ud=greedy_match([[0,0,10,10]],[[30,30,40,40]])
  self.assertEqual(matched,[]);self.assertEqual(ur,[0]);self.assertEqual(ud,[0])
  self.assertTrue(all(isinstance(x,int) for x in ur+ud)) # indices, not fabricated classifications
 def test_label_blind_interface(self):
  import inspect
  self.assertEqual(list(inspect.signature(greedy_match).parameters),['references','detections','minimum_iou'])
  # Matching accepts coordinate arrays only; no label/group/context argument.
 def test_partial_overlap(self):
  self.assertAlmostEqual(iou([0,0,10,10],[5,0,15,10]),1/3)
if __name__=='__main__':unittest.main()
