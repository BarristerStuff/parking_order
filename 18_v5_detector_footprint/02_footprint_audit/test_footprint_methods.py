import math, unittest
from footprint import process_target, polygon_quality, clip_bottom, METHODS
class FootprintTests(unittest.TestCase):
    def target(self,**kw):
        t=dict(image_id='synthetic',vehicle_id='s1',bbox_xyxy=[10,10,90,90],mask_contours_image=[[[10,10],[90,10],[90,90],[10,90]]]);t.update(kw);return t
    def test_two_only_and_null_ground(self):
        rows=process_target(self.target(),100,100)
        self.assertEqual([r['method'] for r in rows],list(METHODS))
        for r in rows:
            self.assertEqual(r['status'],'proxy');self.assertIsNone(r['ground_contact_polygon']);self.assertIsNone(r['footprintIoU'])
        self.assertEqual(rows[0]['contact_band_polygon'],[[90.,74.],[90.,90.],[10.,90.],[10.,74.]])
    def test_nan_bbox(self):
        self.assertTrue(all(r['status']=='failed' for r in process_target(self.target(bbox_xyxy=[10,10,math.nan,90]),100,100)))
    def test_nonpositive_bbox(self):
        self.assertEqual(process_target(self.target(bbox_xyxy=[90,10,10,90]),100,100)[1]['status'],'failed')
    def test_self_intersection(self):
        _,issues=polygon_quality([[10,10],[90,90],[10,90],[90,10]],100,100)
        self.assertIn('self_intersection_or_nonadjacent_touch',issues)
    def test_nonfinite_mask(self):
        _,issues=polygon_quality([[0,0],[1,0],[1,math.inf]],100,100);self.assertIn('nonfinite_polygon',issues)
    def test_multiple_contours(self):
        t=self.target();t['mask_contours_image']*=2;r=process_target(t,100,100)[0]
        self.assertEqual(r['status'],'uncertain');self.assertIsNone(r['ground_contact_candidate'])
    def test_inconsistent_not_clear(self):
        r=process_target(self.target(bbox_xyxy=[40,40,60,60]),100,100)[0]
        self.assertEqual(r['status'],'uncertain');self.assertIn('mask_outside_bbox',r['reasons'])
    def test_out_of_bounds(self):
        r=process_target(self.target(bbox_xyxy=[-1,10,90,90]),100,100)
        self.assertTrue(all(x['status']=='failed' for x in r))
    def test_truncation(self):
        r=process_target(self.target(bbox_xyxy=[0,10,90,90]),100,100)
        self.assertTrue(all(x['status']=='uncertain' for x in r))
    def test_disconnected_band(self):
        # upside-down U, bottom strip has two physically separate legs
        p=[[10,10],[90,10],[90,90],[70,90],[70,30],[30,30],[30,90],[10,90]]
        band,issues=clip_bottom(p,74);self.assertIsNone(band);self.assertIn('band_may_be_disconnected',issues)
    def test_missing_mask(self):
        r=process_target(self.target(mask_contours_image=[]),100,100)
        self.assertEqual(r[0]['status'],'failed');self.assertEqual(r[1]['status'],'proxy')
    def test_unknown_provenance(self):
        t=self.target();t['mask_polygon_image']=t.pop('mask_contours_image')[0]
        self.assertEqual(process_target(t,100,100)[0]['status'],'uncertain')
    def test_labels_cannot_change_output(self):
        a=self.target();b=self.target(labels={'road':True,'two_bays':True})
        self.assertEqual(process_target(a,100,100),process_target(b,100,100))
    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError): process_target(self.target(),math.inf,100)
if __name__=='__main__': unittest.main()
