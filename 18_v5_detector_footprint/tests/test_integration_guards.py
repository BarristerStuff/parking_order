import sys,json,unittest,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'05_evaluation'))
from detector_footprint_eval import validate_footprint_rows
class IntegrationGuards(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=[json.loads(x) for x in (R/'02_footprint_audit/footprint_outputs.jsonl').read_text().splitlines()]
  cls.targets=[json.loads(x) for x in (R/'01_detector_audit/r1_targets.jsonl').read_text().splitlines()]
  cls.fm=json.loads((R/'02_footprint_audit/footprint_metrics.json').read_text())
 def test_actual_bound_source(self):validate_footprint_rows(self.rows,self.targets,self.fm)
 def test_stale_alias_rejected(self):
  rows=copy.deepcopy(self.rows);rows[0]['ground_contact_status']='validated'
  with self.assertRaises(ValueError):validate_footprint_rows(rows,self.targets,self.fm)
 def test_wrong_row_source_rejected(self):
  rows=copy.deepcopy(self.rows);rows[0]['input_sha256']='wrong'
  with self.assertRaises(ValueError):validate_footprint_rows(rows,self.targets,self.fm)
 def test_wrong_bbox_rejected(self):
  rows=copy.deepcopy(self.rows);rows[0]['bbox_xyxy']=[0,0,1,1]
  with self.assertRaises(ValueError):validate_footprint_rows(rows,self.targets,self.fm)
 def test_ground_injection_rejected(self):
  rows=copy.deepcopy(self.rows);rows[0]['ground_contact_polygon']=[[1,1],[2,1],[2,2]]
  with self.assertRaises(ValueError):validate_footprint_rows(rows,self.targets,self.fm)
 def test_omitted_method_rejected(self):
  with self.assertRaises(ValueError):validate_footprint_rows(self.rows[:-1],self.targets,self.fm)
if __name__=='__main__':unittest.main()
