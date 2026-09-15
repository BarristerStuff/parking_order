"""CPU YOLO vehicle detector with one lazily cached model instance."""
from pathlib import Path
import hashlib, time
_MODEL=None; _MODEL_PATH=None
def _model(config):
 global _MODEL,_MODEL_PATH
 path=(Path(__file__).resolve().parents[1]/config['detector']['checkpoint']).resolve()
 if hashlib.sha256(path.read_bytes()).hexdigest()!=config['detector']['checkpoint_sha256']: raise RuntimeError('detector checkpoint hash mismatch')
 if _MODEL is None or _MODEL_PATH!=str(path):
  try:
   from ultralytics import YOLO
  except ModuleNotFoundError:
   import sys
   sys.path.insert(0, '/home/yanbo/net_vlm_yanboversion/vlm')
   from ultralytics import YOLO
  _MODEL=YOLO(str(path)); _MODEL_PATH=str(path)
 return _MODEL
def detect(image, config=None):
 from .config import load_config
 config=config or load_config(); t=time.perf_counter(); model=_model(config); spec=config['detector']; classes={int(k):v for k,v in spec['classes'].items()}
 source=image
 if not isinstance(image,(str,Path)):
  import numpy as np
  source=np.asarray(image)
 result=model.predict(source,conf=spec['conf'],imgsz=spec['imgsz'],device=spec['device'],verbose=False)[0]; out=[]
 for b,c,cl in zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),result.boxes.cls.tolist()):
  if int(cl) in classes: out.append({'bbox':b,'class_id':int(cl),'class_name':classes[int(cl)],'confidence':float(c)})
 return out,time.perf_counter()-t
