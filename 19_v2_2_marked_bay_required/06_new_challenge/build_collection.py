import csv, hashlib
from pathlib import Path
root=Path(__file__).parent
spec=[('P22_01','positive',30,'Unmarked curbside or roadside parking; show curb/road edge or one roadside line but no marked bay.'),('P22_02','positive',15,'Vehicle stopped on open pavement or driving aisle, with no marked bay around it.'),('P22_03','positive',15,'Vehicle clearly spans substantial parts of two marked parking bays.'),('P22_04','positive',15,'Vehicle clearly outside all established marked parking bays.'),('N22_01','negative',20,'Vehicle clearly belongs within one marked parking bay.'),('N22_02','negative',15,'Faded or partial painted markings still clearly establish one bay around the vehicle.'),('N22_03','negative',15,'Minor line touch, slight tire crossing, bumper overhang, or mild angle while overall in one bay.'),('N22_04','negative',10,'Strong perspective makes lines look crossed, but vehicle is clearly normal in one bay.'),('N22_05','negative',10,'Large vehicle near boundary but clearly compliant within one bay.'),('N22_06','negative',5,'Normal gate/barrier queue heading toward checkpoint.'),('U22_01','uncertain',10,'Markings heavily occluded; cannot determine whether one marked bay exists.'),('U22_02','uncertain',10,'Night, blur, or vehicle cutoff prevents reliable bay judgment.'),('U22_03','uncertain',10,'Roadside marking and parking context remain ambiguous.')]
rows=[]
for group,label,n,prompt in spec:
 for i in range(1,n+1):
  rows.append({'image_id':f'{group}_{i:03d}','scenario_group':group,'gt':label,'source_type':'ai_generated','generation_model':'TBD','generation_batch':'V22_20260916','prompt_group':group,'seed':str(20260916+i),'date':'2026-09-16','prompt':prompt})
# deterministic group-preserving split, round-robin within each group
splits={}
for group,label,n,prompt in spec:
 for i in range(1,n+1): splits[f'{group}_{i:03d}']=['DEV','VAL','HOLDOUT'][(i-1)%3]
with (root/'V2_2_180_PROMPT_MANIFEST.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0])+['split']);w.writeheader()
 for r in rows:w.writerow({**r,'split':splits[r['image_id']]})
with (root/'V2_2_180_IMAGE_COLLECTION_PLAN.md').open('w') as f:
 f.write('# v2.2 180-image collection plan\n\nStatus: **PLAN_ONLY; images unavailable**. No model evaluation may use this manifest until images are generated/acquired, visually reviewed, and challenge GT/split manifests are frozen with hashes.\n\nSeed: `20260916_V22_FINAL_CHALLENGE`. Total 180: positive 75, negative 75, uncertain 30. Scenario groups are kept within one split by deterministic assignment; generation intent is not GT. All positive images and boundary negatives N22_02/N22_03/N22_06 require visual review; unresolved items enter human review queue.\n\nThe CSV contains one complete prompt row per planned image, provenance placeholders (`generation_model=TBD` until generation), stable seed, date, and split.\n')
