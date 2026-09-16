"""Pixel-level View A regression against frozen VAL images."""
import io,json
from pathlib import Path
import numpy as np
from PIL import Image
from vehicle_not_in_bay.config import load_config
from vehicle_not_in_bay.view_a import render
B=Path(__file__).resolve().parents[1];cfg=load_config();rows=list(map(json.loads,open(B.parent/'06_v2_1_outside_only/val_predictions.jsonl')))[0:3]
imgs={p.stem:p for p in Path('/home/yanbo/net_vlm_xunjian_dataset/00_raw/ai_generated/images').rglob('*') if p.suffix.lower() in {'.png','.jpg','.jpeg'}}
for r in rows:
 v=r['vehicle_results'][0];got=render(Image.open(imgs[r['media_id']]).convert('RGB'),v['bbox'],cfg);b=io.BytesIO();got.save(b,'JPEG',quality=cfg['view_a']['jpeg_quality']);got=Image.open(io.BytesIO(b.getvalue())).convert('RGB');frozen=Image.open(v['view_a']['path']).convert('RGB');assert got.size==frozen.size
 mse=float(np.mean((np.asarray(got).astype('float32')-np.asarray(frozen).astype('float32'))**2));assert mse<1,mse
print('PASS view_a_regression 3 images MSE<1')
