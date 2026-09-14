import sys
sys.dont_write_bytecode=True
import unittest
from matching import iou,greedy_match
class MatchingCore(unittest.TestCase):
 def test_identical(self):self.assertEqual(iou([0,0,2,2],[0,0,2,2]),1)
 def test_empty(self):self.assertEqual(greedy_match([],[]),([],[],[]))
 def test_threshold_inclusive(self):self.assertEqual(len(greedy_match([[0,0,2,1]],[[0,0,1,1]])[0]),1)
 def test_below(self):self.assertEqual(greedy_match([[0,0,3,1]],[[0,0,1,1]])[1],[0])
 def test_ties(self):
  m,r,d=greedy_match([[0,0,1,1]]*2,[[0,0,1,1]]*2)
  self.assertEqual([(x['reference_index'],x['detection_index']) for x in m],[(0,0),(1,1)])
 def test_global_descending(self):
  m,r,d=greedy_match([[0,0,2,1],[0,0,1,1]],[[0,0,1,1]])
  self.assertEqual(m[0]['reference_index'],1);self.assertEqual(r,[0])
 def test_zero_area(self):self.assertEqual(iou([0,0,0,0],[0,0,0,0]),0)
if __name__=='__main__':unittest.main()
