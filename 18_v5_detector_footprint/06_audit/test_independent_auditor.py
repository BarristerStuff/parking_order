import importlib.util, pathlib, unittest, random
p=pathlib.Path(__file__).with_name('audit_v5_p0.py')
s=importlib.util.spec_from_file_location('independent_auditor',p);a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class MatchTests(unittest.TestCase):
 def test_empty(self):self.assertEqual(a.match([],[]),([],[],[]))
 def test_threshold_inclusive(self):self.assertEqual(a.match([[0,0,2,1]],[[0,0,1,1]])[0][0]['iou'],.5)
 def test_below_threshold(self):self.assertEqual(a.match([[0,0,2,1]],[[0,0,.999,1]])[0],[])
 def test_tie(self):
  box=[0,0,1,1];m,ur,ud=a.match([box,box],[box,box]);self.assertEqual([(v['reference_index'],v['detection_index']) for v in m],[(0,0),(1,1)]);self.assertEqual(ur+ud,[])
 def test_global_descending(self):
  m,_,_=a.match([[0,0,10,10],[0,0,9,10]],[[0,0,9,10],[0,0,10,10]])
  self.assertEqual([(v['reference_index'],v['detection_index']) for v in m],[(0,1),(1,0)])
 def test_invalid(self):
  for b in [[0,0,float('nan'),1],[2,0,1,1]]:
   with self.assertRaises(ValueError):a.match([b],[[0,0,1,1]])
 def test_random_iou_bounds(self):
  rng=random.Random(18)
  for _ in range(1000):
   def b():
    x,y,w,h=[rng.random()*10 for _ in range(4)];return [x,y,x+w,y+h]
   x,y=b(),b();v=a.iou(x,y);self.assertGreaterEqual(v,0);self.assertLessEqual(v,1);self.assertEqual(v,a.iou(y,x))
if __name__=='__main__':unittest.main()
