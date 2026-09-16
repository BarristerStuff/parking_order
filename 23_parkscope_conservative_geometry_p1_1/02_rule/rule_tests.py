#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conservative_geometry_rule import decide_target, fuse_frame
CFG={'line_elongation_min':3.5,'line_max_thickness_ratio':.25,'parallel_angle_max':25,'separator_center_margin':.25,'bracket_max_distance_ratio':1.0,'area_support_min':.5}
def comp(**kw):
 d={'instance_index':'1','elongation':'1','thickness_ratio':'1','line_crosses_central_ground_span':'False','distance_to_bottom_center_normalized':'9','orientation_deg':'0','signed_normal_offset':'0','overlap_with_ground_proxy':'0','bottom_center_inside_area':'False'}; d.update({k:str(v) for k,v in kw.items()}); return d
sep=comp(elongation=5,thickness_ratio=.1,line_crosses_central_ground_span=True,distance_to_bottom_center_normalized=.1,signed_normal_offset=.1)
line_l=comp(instance_index=2,elongation=5,thickness_ratio=.1,orientation_deg=5,signed_normal_offset=-.3)
line_r=comp(instance_index=3,elongation=5,thickness_ratio=.1,orientation_deg=8,signed_normal_offset=.3)
area=comp(instance_index=4,overlap_with_ground_proxy=.8)
assert decide_target('ANCHOR_INVALID',[],CFG)[0]=='UNCERTAIN_ANCHOR'
assert decide_target('ANCHOR_VALID',[sep],CFG)[0]=='POSITIVE_MULTIBAY'
assert decide_target('ANCHOR_VALID',[line_l,line_r],CFG)[0]=='NEGATIVE_IN_BAY'
assert decide_target('ANCHOR_VALID',[sep,area],CFG)[0]=='UNCERTAIN_CONFLICT'
assert decide_target('ANCHOR_VALID',[],CFG)[0]=='UNCERTAIN_NO_EVIDENCE'
assert decide_target('ANCHOR_VALID',[comp()],CFG)[0]=='UNCERTAIN_NO_EVIDENCE'
assert fuse_frame(['POSITIVE_MULTIBAY','NEGATIVE_IN_BAY'])=='positive'
assert fuse_frame(['NEGATIVE_IN_BAY','NEGATIVE_IN_BAY'])=='negative'
assert fuse_frame(['NEGATIVE_IN_BAY','UNCERTAIN_NO_EVIDENCE'])=='uncertain'
print('9 tests passed')
