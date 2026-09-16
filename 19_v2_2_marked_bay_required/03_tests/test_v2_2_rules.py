import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "02_pipeline"))
from vehicle_not_in_bay.rules import vehicle_decision, apply
class V22Rules(unittest.TestCase):
 def test_truth_table(self):
  self.assertEqual(vehicle_decision("A"), "in_bay"); self.assertEqual(vehicle_decision("A","B"), "in_bay")
  self.assertEqual(vehicle_decision("D"), "uncertain"); self.assertEqual(vehicle_decision("D","A"), "uncertain")
  for q1 in ("B","C"):
   self.assertEqual(vehicle_decision(q1,"A"), "gate_queue")
   for q3 in ("B","C"): self.assertEqual(vehicle_decision(q1,q3), "outside_or_multibay")
   self.assertEqual(vehicle_decision(q1,"D"), "uncertain"); self.assertEqual(vehicle_decision(q1), "uncertain")
 def test_frame_priority_and_queue(self):
  vs=[{"q1":"A"},{"q1":"B","q3":"A"}]; self.assertEqual(apply(vs)[0],"negative"); self.assertEqual(len(apply(vs)[1]),1)
  self.assertEqual(apply([{"q1":"A"},{"q1":"C","q3":"D"}])[0],"uncertain")
  self.assertEqual(apply([{"q1":"A"},{"q1":"C","q3":"C"}])[0],"positive")
  self.assertEqual(apply([])[0],"uncertain")
if __name__ == '__main__': unittest.main()
