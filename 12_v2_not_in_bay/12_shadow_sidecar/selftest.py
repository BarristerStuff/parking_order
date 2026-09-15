import sys,json,cv2,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));from shadow_sidecar import ShadowSidecar
imgs=[]
for p in list(Path('/home/yanbo/net_vlm_xunjian_dataset/00_raw/ai_generated/images').rglob('IMG_007320.png'))+list(Path('/home/yanbo/net_vlm_xunjian_dataset/00_raw/ai_generated/images').rglob('IMG_007533.png'))+list(Path('/home/yanbo/net_vlm_xunjian_dataset/00_raw/ai_generated/images').rglob('IMG_007550.png')):imgs.append(p)
side=ShadowSidecar(Path(__file__).parent/'selftest_outputs',ledger=Path(__file__).parent/'selftest_outputs/ledger.jsonl')
for i,p in enumerate(imgs[:3]):
 side.last=0
 rgb=cv2.imread(str(p));rgb=cv2.cvtColor(rgb,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2];yuv=cv2.cvtColor(rgb,cv2.COLOR_RGB2YUV_I420).tobytes();r=side.process_packet({'i420':yuv,'width':w,'height':h,'topic':'selftest','packet_id':str(i),'timestamp_ms':i});print(json.dumps({'media_id':r.get('media_id'),'frame_decision':r.get('frame_decision'),'requests':r.get('request_count'),'error':r.get('error'),'frame_path':r.get('frame_path')}))
print('ledger_rows',sum(1 for _ in open(side.output/'ledger.jsonl')))
