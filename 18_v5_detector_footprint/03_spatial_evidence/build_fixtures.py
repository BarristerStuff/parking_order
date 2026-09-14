"""Analytic rectangles. No real/AIGC pixels, no per-image ROI, no reference labels."""
from pathlib import Path
import json,copy,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
def rect(x1,y1,x2,y2):return [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
def make(name,expected,**kw):
 v={'image_id':'SYNTH_'+name,'vehicle_id':'v1','coordinate_space':'image','image_size':[200,100],'source_sha256':hashlib.sha256(('analytic:'+name).encode()).hexdigest(),'footprint_source':'ground_contact','ground_contact_status':'validated','ground_contact_polygon_image':rect(20,20,100,80)}
 r={'image_id':v['image_id'],'source_sha256':v['source_sha256'],'coordinate_space':'image','image_size':[200,100],'validation_status':'SYNTHETIC_UNIT_TEST_ONLY','scope':'SYNTHETIC_UNIT_TEST_ONLY','areas':{'road':[],'parking_area':[],'gate_queue':[]},'bays':[],'adjacent_pairs':[]}
 c={'normal_gate_queue':'no','boundary_relation':'inside'}
 return {'case_id':name,'scope':'SYNTHETIC_UNIT_TEST_ONLY','vehicle':v,'roi':r,'context':c,'expected':expected}
rows=[]
a=make('road','positive_road');a['roi']['areas']['road']=[rect(0,0,199,99)];rows.append(a)
a=make('two_adjacent_bays','positive_two_bays');a['roi']['bays']=[{'bay_id':'a','polygon':rect(0,0,60,99)},{'bay_id':'b','polygon':rect(60,0,199,99)}];a['roi']['adjacent_pairs']=[['a','b']];rows.append(a)
a=make('single_line_touch','negative_line_touch_or_minor_overrun');a['roi']['bays']=[{'bay_id':'a','polygon':rect(0,0,100,99)},{'bay_id':'b','polygon':rect(100,0,199,99)}];a['roi']['adjacent_pairs']=[['a','b']];a['context']['boundary_relation']='minor_side';rows.append(a)
a=make('nose_tail','negative_nose_tail_overhang');a['roi']['bays']=[{'bay_id':'a','polygon':rect(0,0,94,99)}];a['context']['boundary_relation']='nose_tail';rows.append(a)
a=make('in_bay','negative_in_bay');a['roi']['bays']=[{'bay_id':'a','polygon':rect(0,0,199,99)}];rows.append(a)
a=make('gate_queue','negative_gate_queue');a['roi']['areas']['road']=[rect(0,0,199,99)];a['roi']['areas']['gate_queue']=[rect(0,0,199,99)];a['context']['normal_gate_queue']='yes';rows.append(a)
a=make('uncertain','uncertain');a['roi']=None;rows.append(a)
a=make('coordinate_mismatch','uncertain');a['roi']['coordinate_space']='bev';rows.append(a)
a=make('bbox_only','uncertain');a['vehicle']['footprint_source']='bbox_lower';a['vehicle']['ground_contact_status']='proxy';a['vehicle']['bbox_lower_polygon_image']=a['vehicle'].pop('ground_contact_polygon_image');a['roi']['areas']['road']=[rect(0,0,199,99)];rows.append(a)
a=make('non_adjacent_bays','uncertain');a['roi']['bays']=copy.deepcopy(rows[1]['roi']['bays']);rows.append(a)
p=ROOT/'03_spatial_evidence/synthetic_fixtures.json'
if p.exists():raise SystemExit('REFUSE_OVERWRITE_FIXTURES')
p.write_text(json.dumps({'scope':'SYNTHETIC_UNIT_TEST_ONLY','not_generated_images':True,'geometry_validation_basis':'analytically_defined_rectangles_not_camera_groundtruth','cases':rows,'aggregate_case':{'case_id':'multi_vehicle_or','members':['road','in_bay','uncertain'],'expected':'positive'}},indent=2)+'\n')
freeze_files=[p,ROOT/'04_rule_engine/rule_config.json',ROOT/'04_rule_engine/synthetic_core.py',ROOT/'04_rule_engine/space_rule.py']
(ROOT/'03_spatial_evidence/fixture_freeze.json').write_text(json.dumps({'frozen_at':time.time(),'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in freeze_files}},indent=2)+'\n')
