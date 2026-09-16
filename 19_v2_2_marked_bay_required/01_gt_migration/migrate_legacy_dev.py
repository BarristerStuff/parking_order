import csv
from pathlib import Path
src=Path('12_v2_not_in_bay/01_gt_and_split/v2_0_gt.csv')
out=Path('19_v2_2_marked_bay_required/01_gt_migration/legacy_dev_v2_2_shadow_gt.csv')
review=Path('19_v2_2_marked_bay_required/01_gt_migration/migration_review.csv')
positive={'p01-outside-legal-bay-clear':'positive','p03-span-two-bays':'positive'}
negative={'n01-standard-inside-bay':'negative','n03-diagonal-bay-correct':'negative','n04-parallel-bay-correct':'negative','n05-multiple-all-correct':'negative','n06-special-marked-space-geometry-correct':'negative','hn01-gate-queue':'negative','hn02-faded-lines-but-confirmably-inside':'negative','hn03-perspective-looks-like-crossing':'negative','hn04-large-vehicle-compliant':'negative','hn05-adjacent-vehicle-occludes-lines':'negative','hn06-shadows-cracks-curbs-mimic-lines':'negative'}
review_groups={'p02-cross-single-boundary-line','p04-angled-footprint-outside','p05-multi-vehicle-at-least-one-violation','p06-nose-or-tail-intrudes-aisle'}
rows=list(csv.DictReader(src.open()))
fields=['media_id','group_key','legacy_v2_gt','v2_2_gt','migration_status','basis']
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in rows:
  g=r['group_key']
  if g in positive: gt,status,basis=positive[g],'mapped_high_confidence','unmarked_or_multi_bay'
  elif g in negative: gt,status,basis=negative[g],'mapped_high_confidence','clearly_inside_or_gate_exempt'
  elif g.startswith('u') or g in review_groups: gt,status,basis='uncertain','needs_human_review','v2_2_boundary_requires_visual_review'
  else: gt,status,basis='uncertain','needs_human_review','unmapped_group'
  w.writerow({**{k:r.get(k,'') for k in ['media_id','group_key','legacy_v2_gt']},'legacy_v2_gt':r['v2_gt'],'v2_2_gt':gt,'migration_status':status,'basis':basis})
with review.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['media_id','group_key','legacy_v2_gt','proposed_v2_2_gt','review_status','review_notes']);w.writeheader()
 for r in rows:
  if r['group_key'] in review_groups:
   w.writerow({'media_id':r['media_id'],'group_key':r['group_key'],'legacy_v2_gt':r['v2_gt'],'proposed_v2_2_gt':'','review_status':'needs_human_review','review_notes':''})
