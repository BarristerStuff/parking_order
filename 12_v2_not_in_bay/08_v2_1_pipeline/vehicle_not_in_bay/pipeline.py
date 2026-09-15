import base64,io,hashlib,json
from PIL import Image
from .select import select
from .view_a import make
from .rules import apply
from .ollama_client import OllamaClient
ROOT=__import__('pathlib').Path(__file__).resolve().parents[1];Q1=(ROOT/'prompts/q1.txt').read_bytes();Q3=(ROOT/'prompts/q3.txt').read_bytes()
def run(image,out,endpoint='http://192.168.20.62:11434',model='qwen3.5:4b',ledger=None,detector_fn=None):
 assert hashlib.sha256(Q1).hexdigest().startswith('76151fc7') and hashlib.sha256(Q3).hexdigest().startswith('5cc5e33a')
 im=Image.open(image);w,h=im.size;ds=detector_fn(image) if detector_fn else __import__('vehicle_not_in_bay.detector',fromlist=['detect']).detect(image);sel=select(ds,w,h);c=OllamaClient(endpoint,model,ledger);vs=[];total=0
 for rank,d in enumerate(sel,1):
  p=io.BytesIO();make(image,d['bbox'],p) if False else None
  z=make(image,d['bbox'],ROOT/'tmp_view.jpg'); b=io.BytesIO();z.save(b,'JPEG',quality=90); b64=base64.b64encode(b.getvalue()).decode();q1,l1=c.ask(Q1.decode(),b64,image.stem,rank);total+=l1;q3=None;l3=0
  if q1=='C':q3,l3=c.ask(Q3.decode(),b64,image.stem,rank);total+=l3
  vs.append({'rank':rank,'bbox':d['bbox'],'q1':q1,'q3':q3,'decision':None,'latency':l1+l3})
 frame,g=apply(vs);z={'media_id':image.stem,'frame_decision':frame,'vehicles':vs,'gate_queue_vehicles':g,'request_count':sum(1+(v['q1']=='C') for v in vs),'total_latency_seconds':total,'pipeline_version':'v2.1','q1_sha':hashlib.sha256(Q1).hexdigest(),'q3_sha':hashlib.sha256(Q3).hexdigest()};json.dump(z,open(out,'w'),indent=2);return z
