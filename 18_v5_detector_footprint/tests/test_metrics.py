from pathlib import Path
import sys,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'05_evaluation'))
from metrics_utils import rate,require_coverage_gate
class Metrics(unittest.TestCase):
 def test_undefined_is_null(self):self.assertIsNone(rate(0,0)['ratio']);self.assertIsNone(rate(0,0)['wilson95'])
 def test_zero_is_not_certainty(self):self.assertGreater(rate(0,10)['wilson95'][1],0)
 def test_invalid_support(self):
  for k,n in [(1,0),(-1,1),(True,1),(1.5,3)]:
   with self.assertRaises(ValueError):rate(k,n)
 def test_missing_gate_fails(self):self.assertFalse(require_coverage_gate({}, {'overall':.9})['passed'])
 def test_one_subgroup_fails(self):self.assertFalse(require_coverage_gate({'overall':rate(95,100),'road':rate(8,10)},{'overall':.9,'road':.9})['passed'])
 def test_exact_threshold(self):self.assertTrue(require_coverage_gate({'overall':rate(9,10)},{'overall':.9})['passed'])
if __name__=='__main__':unittest.main()
