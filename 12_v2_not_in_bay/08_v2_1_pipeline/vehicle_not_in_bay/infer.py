import argparse
from .pipeline import run
from .detector import detect
p=argparse.ArgumentParser();p.add_argument('--image');p.add_argument('--out');p.add_argument('--image-list');p.add_argument('--out-dir');a=p.parse_args()
if a.image:run(__import__('pathlib').Path(a.image),__import__('pathlib').Path(a.out))
else:
 from pathlib import Path
 for x in Path(a.image_list).read_text().splitlines():run(Path(x),Path(a.out_dir)/(Path(x).stem+'.json'))
