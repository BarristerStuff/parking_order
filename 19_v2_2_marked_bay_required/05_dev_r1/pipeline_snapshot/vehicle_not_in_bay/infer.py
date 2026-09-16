"""CLI for single-image and image-list inference."""
import argparse,json
from pathlib import Path
from .config import load_config
from .detector import detect
from .ollama_client import OllamaClient
from .pipeline import infer_path
p=argparse.ArgumentParser();p.add_argument('--image');p.add_argument('--out');p.add_argument('--image-list');p.add_argument('--out-dir');a=p.parse_args();cfg=load_config();client=OllamaClient(cfg['endpoint'],cfg['model'],config=cfg);paths=[Path(a.image)] if a.image else [Path(x) for x in Path(a.image_list).read_text().splitlines()]
for x in paths:
 z=infer_path(x,client,detect);out=Path(a.out) if a.image else Path(a.out_dir)/(x.stem+'.json');out.write_text(json.dumps(z,indent=2)+'\n')
