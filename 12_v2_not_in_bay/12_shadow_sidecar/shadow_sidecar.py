"""Non-alerting MQTT sidecar for v2.1.1 shadow observation."""
import os,json,time,hashlib,io,shutil,logging
from pathlib import Path
from PIL import Image
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'08_v2_1_pipeline'));sys.path.insert(0,'/home/yanbo/net_vlm_yanboversion/vlm')
from vehicle_not_in_bay.pipeline import infer_image
from vehicle_not_in_bay.detector import detect
from vehicle_not_in_bay.ollama_client import OllamaClient
MIN_INTERVAL=10.0
class ShadowSidecar:
 def __init__(self,output_dir,endpoint='http://192.168.20.62:11434',ledger=None):
  self.output=Path(output_dir);self.frames=self.output/'frames';self.output.mkdir(parents=True,exist_ok=True);self.frames.mkdir(exist_ok=True);self.last=0;self.dropped=0;self.client=OllamaClient(endpoint,'qwen3.5:4b',ledger=ledger,config=json.load(open(ROOT/'08_v2_1_pipeline/config.json')))
 def process_packet(self,packet):
  now=time.time()
  if now-self.last<MIN_INTERVAL:self.dropped+=1;return {'dropped':True,'reason':'throttled'}
  self.last=now; raw=packet['i420'];w=int(packet['width']);h=int(packet['height']); media_id=f"{packet.get('topic','frame').replace('/','_')}_{packet.get('packet_id','na')}_{packet.get('timestamp_ms',int(now*1000))}"; sha=hashlib.sha256(raw).hexdigest()
  try:
   import cv2,numpy as np
   bgr=cv2.cvtColor(np.frombuffer(raw,dtype=np.uint8).reshape((h*3//2,w)),cv2.COLOR_YUV2BGR_I420); rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
   if packet.get('stereo_view')=='right':rgb=rgb[:,rgb.shape[1]//2:]
   if packet.get('rotate_180',True):rgb=np.ascontiguousarray(rgb[::-1,::-1])
   result=infer_image(Image.fromarray(rgb),media_id,self.client,detect); result['input_sha256']=sha;result['total_latency']=result.get('total_latency_seconds',0);result['error']=None
   if result['vehicles'] and shutil.disk_usage(self.output).free>=15*1024**3:
    im=Image.fromarray(rgb);im.save(self.frames/(media_id+'.jpg'),quality=90);result['frame_path']=str(self.frames/(media_id+'.jpg'))
   elif result['vehicles']:result['storage_warning']='free_space_below_15G'
  except Exception as exc: result={'media_id':media_id,'input_sha256':sha,'frame_decision':'uncertain','vehicles':[],'gate_queue_vehicles':[],'request_count':0,'total_latency':0,'detector_latency':0,'pipeline_version':'v2.1.1','q1_sha':None,'q3_sha':None,'error':str(exc)}
  with open(self.output/'shadow_predictions.jsonl','a') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush()
  self._enforce_cap();return result
 def _enforce_cap(self):
  files=sorted([p for p in self.frames.glob('*') if p.is_file()],key=lambda p:p.stat().st_mtime)
  while sum(p.stat().st_size for p in files)>5*1024**3:
   files.pop(0).unlink();files=files[1:]
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--host',default=os.getenv('SHADOW_MQTT_HOST','127.0.0.1'));p.add_argument('--port',type=int,default=1883);p.add_argument('--topic',default='agora/yuv/frame');p.add_argument('--output-dir',default=str(Path(__file__).parent/'outputs'));p.add_argument('--ledger',default=str(Path(__file__).parent/'outputs/shadow_request_ledger.jsonl'));a=p.parse_args()
 import paho.mqtt.client as mqtt
 side=ShadowSidecar(a.output_dir,ledger=a.ledger);latest=[None]
 def on_message(c,u,m):
  try: latest[0]=json.loads(m.payload)
  except Exception: logging.exception('invalid payload')
 c=mqtt.Client();c.on_message=on_message;c.connect(a.host,a.port,60);c.subscribe(a.topic);c.loop_start()
 try:
  while True:
   if latest[0] is not None: side.process_packet(latest.pop(0))
   time.sleep(.1)
 except KeyboardInterrupt:pass
if __name__=='__main__':main()
