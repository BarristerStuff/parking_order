import json, unittest
from pathlib import Path
from footprint import ROOT, METHODS, digest, freeze_contract, process_target, polygon_quality, area
class AuditIntegrity(unittest.TestCase):
    def test_frozen_code_hash(self):
        c=freeze_contract();self.assertEqual(c['code_sha256'],digest(ROOT/'footprint.py'))
    def test_final_unique_denominators_and_source(self):
        rows=[json.loads(l) for l in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
        m=json.loads((ROOT/'footprint_metrics.json').read_text())
        source=Path(m['source']); targets=[json.loads(l) for l in source.read_text().splitlines()]
        self.assertEqual(source.name,'r1_targets.jsonl');self.assertEqual(m['source_sha256'],digest(source))
        self.assertEqual(len(rows),2*len(targets));self.assertEqual(m['method_rows'],len(rows))
        keys={(t['image_id'],t['vehicle_id']) for t in targets};self.assertEqual(len(keys),m['unique_vehicles'])
        for method in METHODS:
            subset=[r for r in rows if r['method']==method]
            self.assertEqual({(r['image_id'],r['vehicle_id']) for r in subset},keys)
            self.assertEqual(len(subset),len(keys))
        for r in rows:
            self.assertEqual(r['scope'],'DIAGNOSTIC_ONLY');self.assertIsNone(r['ground_contact_polygon']);self.assertIsNone(r['footprintIoU']);self.assertFalse(r['ground_validated'])
            self.assertEqual(r['input_sha256'],m['source_sha256']);self.assertEqual(r['data_role'],'latest_completed_R1_diagnostic_NOT_winner')
    def test_schema_aliases_and_numeric_topology_separation(self):
        rows=[json.loads(l) for l in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
        m=json.loads((ROOT/'footprint_metrics.json').read_text())
        targets={(t['image_id'],t['vehicle_id']):t for t in map(json.loads,Path(m['source']).read_text().splitlines())}
        for r in rows:
            self.assertTrue({'bbox_xyxy','footprint_source','ground_contact_status','quality','evidence'}.issubset(r))
            self.assertEqual(r['bbox_xyxy'],targets[(r['image_id'],r['vehicle_id'])]['bbox_xyxy'])
            self.assertEqual(r['ground_contact_status'],r['status'])
            self.assertEqual(r['quality']['visual'],r['visual_review'])
            self.assertEqual(r['evidence']['algorithmic_reasons'],r['reasons'])
            self.assertIn(r['footprint_source'],('mask_bottom_band','bbox_lower_proxy'))
        self.assertEqual(m['mask_numeric_validity']['joint_numeric_valid'],221)
        self.assertEqual(m['stricter_polygon_topology_validity']['exported_polygon_rejected'],36)
        self.assertEqual(m['stricter_polygon_topology_validity']['component_provenance_unavailable'],221)
    def test_reference_denominators_geometric_only(self):
        m=json.loads((ROOT/'footprint_metrics.json').read_text())['reference_evaluation']
        self.assertEqual(m['association_status'],'geometric_association_only');self.assertFalse(m['confirmed_matches'])
        for group in m['groups'].values():
            for c in group.values():
                self.assertEqual(c['available']+c['unavailable'],c['denominator'])
                self.assertEqual(c['available_unreviewed']+c['qualitatively_valid']+c['available_reviewed_not_qualitatively_valid'],c['available'])
    def test_visual_counts_actual_log(self):
        reviews=json.loads((ROOT/'visual_review_log.json').read_text())['reviews']
        rows=[json.loads(l) for l in (ROOT/'footprint_outputs.jsonl').read_text().splitlines()]
        self.assertEqual(sum(r['visual_review']['status']!='unreviewed' for r in rows),2*len(reviews))
        for review in reviews:
            for path in review['evidence']: self.assertTrue(Path(path).is_file())
    def test_mask_out_of_bounds_and_degenerate(self):
        for p in ([[[-1,2],[5,2],[5,6]]], [[[1,1],[2,2],[3,3]]]):
            r=process_target(dict(image_id='synthetic',vehicle_id='s',bbox_xyxy=[1,1,9,9],mask_contours_image=p),10,10)[0]
            self.assertEqual(r['status'],'failed');self.assertIsNone(r['ground_contact_candidate'])
    def test_fragment_extent_and_reported_fragment(self):
        t=dict(image_id='s',vehicle_id='s',bbox_xyxy=[1,1,99,99],mask_contours_image=[[[10,10],[20,10],[20,20],[10,20]]])
        a=process_target(t,100,100)[0];self.assertEqual(a['status'],'uncertain');self.assertIn('mask_bbox_extent_inconsistent',a['reasons'])
        t['mask_contour_count']=2;a=process_target(t,100,100)[0];self.assertIsNone(a['ground_contact_candidate'])
    def test_band_subset_and_area(self):
        t=dict(image_id='s',vehicle_id='s',bbox_xyxy=[10,10,90,90],mask_contours_image=[[[10,10],[90,10],[80,90],[20,90]]])
        a=process_target(t,100,100)[0];p=a['contact_band_polygon']
        self.assertLess(area(p),area(a['visible_mask_polygon']))
        self.assertTrue(all(74<=y<=90 and 10<=x<=90 for x,y in p))
if __name__=='__main__':unittest.main()
