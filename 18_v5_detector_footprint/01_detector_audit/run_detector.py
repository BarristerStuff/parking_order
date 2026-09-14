import os,sys,pathlib,json,csv,time,hashlib,socket,shutil
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).resolve().parent; ROOT=O.parent; BASE=ROOT.parent; S=pathlib.Path('/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/runtime_snapshot')
for k,v in {'PYTHONDONTWRITEBYTECODE':'1','YOLO_AUTOINSTALL':'false','YOLO_CONFIG_DIR':str(O/'runtime/config'),'ULTRALYTICS_CONFIG_DIR':str(O/'runtime/config'),'MPLCONFIGDIR':str(O/'runtime/mpl'),'XDG_CACHE_HOME':str(O/'runtime/cache'),'TORCH_HOME':str(O/'runtime/torch'),'TMPDIR':str(O/'runtime/tmp'),'HOME':str(O/'runtime/home')}.items():os.environ[k]=v
for p in ['config','mpl','cache','torch','tmp','home']: (O/'runtime'/p).mkdir(parents=True,exist_ok=True)
def blocked(*a,**k):raise RuntimeError('NETWORK_FORBIDDEN')
socket.create_connection=blocked;socket.socket.connect=blocked
sys.path.insert(0,str(S/'ultralytics'))
from matching import iou,greedy_match

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(p,x):pathlib.Path(p).write_text(json.dumps(x,indent=2)+'\n')
def loadl(p):return [json.loads(l) for l in pathlib.Path(p).read_text().splitlines()]
def checked_image(row):
    p=pathlib.Path(row['absolute_path']);assert row['image_id']==p.stem and sha(p)==row['image_sha256']
    from PIL import Image
    return Image.open(p).convert('RGB')

def main(run):
    import torch,numpy as np,cv2
    from ultralytics import YOLOE
    import ultralytics
    from PIL import ImageDraw
    frozen=json.loads((ROOT/'contracts/preregistration_freeze.json').read_text())
    for f,h in frozen['files'].items():assert sha(ROOT/'contracts'/f)==h
    rows=list(csv.DictReader((ROOT/'contracts/allowlist.csv').open())); assert len(rows)==60 and len({r['image_id'] for r in rows})==60
    manifest=list(csv.DictReader((ROOT/'contracts/pilot_manifest.csv').open())); assert all(r['split']=='DEV' for r in manifest)
    assert {r['media_id'] for r in manifest}=={r['image_id'] for r in rows}
    shutil.copyfile(ROOT/'contracts/allowlist.csv',O/'allowlist.csv')
    prior=BASE/'17_v5_spatial_evidence_vlm'; pre=json.loads((prior/'01_footprint/runtime_preflight.json').read_text())
    weights=pathlib.Path(pre['weights']);encoder=S/'models/mobileclip2_b.ts';assert sha(weights)==pre['weights_sha256'] and sha(encoder)==pre['encoder_sha256']
    config={'model':'YOLOE26m','classes':['car','truck','bus'] if run=='r0' else ['car','truck','bus','pickup truck','van'],'imgsz':640,'conf':.25,'iou':.7,'max_det':50,'retina_masks':True,'device':'cpu','torch_threads':4,'dedup_iou':.8,'weights_sha256':sha(weights),'encoder_sha256':sha(encoder)}
    assert not (O/f'{run}_raw_outputs.jsonl').exists()
    if run=='r1':assert (O/'r1_rationale.json').exists()
    dump(O/f'{run}_config.json',config)
    dump(O/f'{run}_freeze.json',{'frozen_at_unix':time.time(),'config_sha256':sha(O/f'{run}_config.json'),'source_sha256':sha(__file__),'matching_source_sha256':sha(O/'matching.py'),'contract_sha256':sha(ROOT/'contracts/run_contract.json'),'reference_sha256':sha(prior/'reference/reference_instances.jsonl'),'adapted_inputs_sha256':sha(BASE/'16_v4_dynamic_vlm/inputs/pilot/adapted_inputs.jsonl'),'prior_source_sha256':sha(prior/'01_footprint/run_segmentation.py')})
    refs=loadl(prior/'reference/reference_instances.jsonl'); adapted={x['media_id']:x for x in loadl(BASE/'16_v4_dynamic_vlm/inputs/pilot/adapted_inputs.jsonl')}
    torch.set_num_threads(4); link=O/'runtime/mobileclip2_b.ts'
    if not link.exists():link.symlink_to(encoder)
    os.chdir(O/'runtime'); model=YOLOE(str(weights)); classes=config['classes'];model.set_classes(classes,model.get_text_pe(classes))
    (O/'detection_overlays'/run).mkdir(parents=True,exist_ok=True)
    dump(O/f'{run}_runtime.json',{'started_at_unix':time.time(),'torch':torch.__version__,'ultralytics':ultralytics.__version__,'cuda_available':torch.cuda.is_available(),'network':'blocked','python':sys.executable})
    with (O/f'{run}_raw_outputs.jsonl').open('x') as rawf,(O/f'{run}_targets.jsonl').open('x') as tf,(O/f'{run}_matching.jsonl').open('x') as mf,(O/f'{run}_log.jsonl').open('x') as lf:
      for row in rows:
        im=checked_image(row); w,h=im.size;t=time.time(); image_id=row['image_id']
        assert adapted[image_id]['source_path']==row['absolute_path'] and adapted[image_id]['image_sha256']==row['image_sha256'] and adapted[image_id]['split']=='DEV'
        result=model.predict(np.array(im)[:,:,::-1],conf=.25,imgsz=640,iou=.7,max_det=50,verbose=False,retina_masks=True,device='cpu')[0]
        raw=[]
        for j,b in enumerate(result.boxes):raw.append({'raw_detection_id':f'raw_{j+1:04d}','bbox_xyxy':b.xyxy[0].tolist(),'confidence':float(b.conf[0]),'class_id':int(b.cls[0]),'class_name':classes[int(b.cls[0])],'mask_polygon_image':result.masks.xy[j].tolist() if result.masks is not None else []})
        kept=[];supp=[]
        for d in sorted(raw,key=lambda x:-x['confidence']):
          hit=next((k for k in kept if iou(k['bbox_xyxy'],d['bbox_xyxy'])>.8),None)
          if hit:supp.append({'raw_detection_id':d['raw_detection_id'],'suppressed_by':hit['raw_detection_id'],'dedup_reason':'class_agnostic_iou_gt_0.80'})
          else:kept.append(d)
        kept.sort(key=lambda d:d['raw_detection_id'])
        targets=[]
        for j,d in enumerate(kept):
          poly=d['mask_polygon_image']; valid=len(poly)>=3 and all(0<=x<=w and 0<=y<=h for x,y in poly);area=float(cv2.contourArea(np.array(poly,dtype=np.float32))) if valid else 0
          targets.append(dict(d,image_id=image_id,vehicle_id=f'S{j+1:03d}',target_id=f'S{j+1:03d}',run=run,source_size=[w,h],source_sha256=row['image_sha256'],detector_confidence=d['confidence'],coordinate_space='image',mask_area=area,mask_status='ok' if valid and area>0 else 'failed',suppressed_detection_ids=[s['raw_detection_id'] for s in supp if s['suppressed_by']==d['raw_detection_id']]))
        rr=[];old={x['target_id']:x for x in adapted[image_id]['kept_targets']}
        for r in refs:
          if r['media_id']==image_id:
            assert r['image_sha256']==row['image_sha256'];rr.append(dict(r,bbox_xyxy=old[r['target_id']]['bbox']))
        matches,ur,ud=greedy_match([r['bbox_xyxy'] for r in rr],[d['bbox_xyxy'] for d in targets])
        record={'run':run,'image_id':image_id,'references':rr,'detections':targets,'matches':matches,'unmatched_reference_indices':ur,'unmatched_detection_indices':ud,'suppressed':supp,'visual_status':'not_reviewed'}
        rawf.write(json.dumps({'run':run,'image_id':image_id,'source_size':[w,h],'source_sha256':row['image_sha256'],'detections':raw,'suppressed':supp})+'\n')
        for d in targets:tf.write(json.dumps(d)+'\n')
        mf.write(json.dumps(record)+'\n');lf.write(json.dumps({'image_id':image_id,'seconds':time.time()-t,'raw':len(raw),'kept':len(kept),'matches':len(matches),'status':'ok'})+'\n')
        for f in (rawf,tf,mf,lf):f.flush()
        draw=ImageDraw.Draw(im)
        for r in rr:draw.rectangle(r['bbox_xyxy'],outline='yellow',width=4);draw.text((r['bbox_xyxy'][0],r['bbox_xyxy'][1]),r['target_id'],fill='yellow',stroke_width=1)
        for d in targets:draw.rectangle(d['bbox_xyxy'],outline='cyan',width=3);draw.text((d['bbox_xyxy'][0],d['bbox_xyxy'][3]-20),d['target_id'],fill='cyan',stroke_width=1)
        im.save(O/'detection_overlays'/run/f'{image_id}.jpg');print(run,image_id,len(rr),len(targets),len(matches),flush=True)
    dump(O/f'{run}_completion.json',{'completed_at_unix':time.time(),'images':60,'local_detector_calls':60})
if __name__=='__main__':main(sys.argv[1])
